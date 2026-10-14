import streamlit as st
import pandas as pd
import json
import time
import re
from datetime import datetime

# Importar nuestros módulos de Core y Agentes
import core.deduplication as dedup
import core.company_matcher as matcher
import core.cluster_rules as cluster_rules
import core.trend_calculator as trend_calc
import agents.extractor_agent as extractor

# ==========================================
# CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(page_title="Radar WikiCID", layout="wide")

# Inicializar variables en el estado de la sesión (Session State)
if "noticias_cargadas" not in st.session_state:
    st.session_state.noticias_cargadas = None
if "resultados_procesamiento" not in st.session_state:
    st.session_state.resultados_procesamiento = []
if "bandeja_revision" not in st.session_state:
    st.session_state.bandeja_revision = []
if "historial_decisiones" not in st.session_state:
    st.session_state.historial_decisiones = []
if "empresas_aprobadas" not in st.session_state:
    st.session_state.empresas_aprobadas = []
if "noticias_historial_hash" not in st.session_state:
    st.session_state.noticias_historial_hash = [] # Para memoria de duplicados
if "comentario_key" not in st.session_state:
    st.session_state.comentario_key = 0

# ==========================================
# ORQUESTADOR PRINCIPAL (El "Cerebro")
# ==========================================

def enmascarar_entidades(texto, empresas_detectadas):
    """Reemplaza los nombres de las empresas por la etiqueta [EMPRESA] para no confundir al clasificador."""
    texto_limpio = texto
    
    # Limpiamos valores nulos y ordenamos por longitud (para reemplazar "Asteria Systems" antes que "Asteria")
    empresas_validas = [emp for emp in empresas_detectadas if emp and emp != "Desconocida"]
    empresas_validas = sorted(empresas_validas, key=len, reverse=True)
    
    for empresa in empresas_validas:
        texto_limpio = re.sub(re.escape(empresa), '[EMPRESA]', texto_limpio, flags=re.IGNORECASE)
        
    return texto_limpio

def procesar_noticia_real(noticia):
    """
    Orquesta el flujo: 1. Desduplicación -> 2. Extracción IA -> 3. Match Empresa -> 
    4. Match Cluster -> 5. Trend Score -> 6. Empaquetado a Bandeja.
    """
    id_noticia = noticia.get("article_id", "Desconocido")
    titulo = noticia.get("title", "Sin título")
    texto = noticia.get("content", "")
    
    # 1. Desduplicación Estricta (Reglas - URL o Hash)
    es_duplicada, motivo_dup = dedup.evaluar_duplicidad_noticia(noticia, st.session_state.noticias_historial_hash)
    if es_duplicada:
        return "Duplicada", "Media", "Descartar (Duplicado)", None
    
    # Guardar en memoria para futuras comparaciones
    noticia["hash"] = dedup.obtener_hash_texto(texto)
    st.session_state.noticias_historial_hash.append(noticia)

    # 2. Extracción Semántica (Agente IA)
    extraccion = extractor.extraer_informacion_semantica(texto)
    
    if not extraccion["contiene_senal_relevante"]:
        return "Irrelevante", extraccion["nivel_confianza"], "Descartar", None

   # 3. Match de Empresa (Reglas)
    match_empresa = matcher.buscar_empresa_en_texto(texto)
    
    nombre_empresa = "Desconocida"
    ref_empresa = "NEW"
    alerta_empresa = ""
    requiere_revision_urgente = False
    
    if match_empresa:
        nombre_empresa = match_empresa["canonical_name"]
        ref_empresa = match_empresa["company_id"]
        
        # NUEVO Y MEJORADO: Detección B2B basada en el TÍTULO
        empresas_llm = extraccion.get("empresas_relacionadas", [])
        
        # 1. Obtenemos qué otras empresas detectó la IA
        otras_empresas = [
            emp for emp in empresas_llm 
            if emp.lower().strip() not in nombre_empresa.lower()
        ]
        
        # 2. Filtramos: Solo nos importan si esa empresa APARECE EN EL TÍTULO
        empresas_en_titulo = [
            emp for emp in otras_empresas
            if emp.lower().strip() in titulo.lower()
        ]
        
        # Si hay otras empresas y están en el título, levantamos la alerta B2B
        if empresas_en_titulo:
            empresas_extra = ", ".join(empresas_en_titulo)
            alerta_empresa = f"⚠️ Ambigüedad: El catálogo identificó a '{nombre_empresa}', pero el titular menciona a '{empresas_extra}'. Validar quién es el adoptante real."
            requiere_revision_urgente = True
            
        # Alertas propias del matcher (como alias ambiguos)
        if match_empresa.get("requiere_revision"):
            if alerta_empresa:
                alerta_empresa += f" | ⚠️ Alerta de Identidad: {match_empresa['motivo']}"
            else:
                alerta_empresa = f"⚠️ Alerta de Identidad: {match_empresa['motivo']}"
            requiere_revision_urgente = True
            
    else:
        # Si no la encuentra en el catálogo, toma la primera que extrajo el LLM
        if extraccion["empresas_relacionadas"]:
            nombre_empresa = extraccion["empresas_relacionadas"][0]
            alerta_empresa = "⚠️ Empresa no registrada en el catálogo oficial."
            requiere_revision_urgente = True

    # 4. Match de Cluster Tecnológico (Reglas)

    todas_las_empresas = [nombre_empresa] + extraccion.get("empresas_relacionadas", [])
    texto_para_cluster = enmascarar_entidades(texto, todas_las_empresas)
    
    # Obtenemos el ID del cluster si hace match
    id_cluster_determinista = cluster_rules.clasificar_cluster_determinista(texto_para_cluster)
    
    # Definir las variables que usará el diccionario
    tecnologia_detectada = extraccion.get("tecnologia_detectada", "No identificada")
    
    if id_cluster_determinista:
        cluster_final = id_cluster_determinista
        estado_cluster = "Asignado por catálogo"
    else:
        # Si falla el determinista, tomamos la sugerencia semántica
        cluster_final = f"Propuesta sugerida basada en: {tecnologia_detectada}"
        estado_cluster = "Requiere validación (Cluster Nuevo)"
        requiere_revision_urgente = True

    # 5. Cálculo del Trend Score Automático (Reglas)
    dims_auto = trend_calc.calcular_dimensiones_automaticas(ref_empresa)

    # 6. Empaquetar para la Bandeja de Revisión Humana
    estado_final = "Requiere revisión" if requiere_revision_urgente else "Procesada"
    accion_sugerida = "Revisar" if requiere_revision_urgente else "Validar métricas humanas"
    
    oportunidad = {
        "id_oportunidad": f"OPP-{id_noticia}",
        "empresa": nombre_empresa,
        "evento": extraccion.get("evento_identificado", titulo),
        "senal_resumen": extraccion.get("resumen", "Sin resumen"),
        "tecnologia": tecnologia_detectada,
        "cluster": cluster_final, 
        "cluster_estado": estado_cluster,
        "confianza": extraccion.get("nivel_confianza", "Baja"),
        "fuentes": [noticia.get("source", "Desconocida")],
        "urls": [noticia.get("url", "")],
        "objetivos_negocio": extraccion.get("impacto_negocio", []),
        "alertas": alerta_empresa,
        "dimensiones_auto": dims_auto,
        "human_inputs": {"materialidad": 0, "adopcion": 0},
        "estado_revision": "Pendiente"
    }

    return estado_final, extraccion.get("nivel_confianza", "Baja"), accion_sugerida, oportunidad

# ==========================================
# INTERFAZ GRÁFICA
# ==========================================
st.title("Mini Radar de WikiCID")
tab1, tab2, tab3 = st.tabs(["Procesamiento de noticias", "Bandeja de revisión", "Aprobación y búsqueda"])

# ------------------------------------------
# PESTAÑA 1: CARGA Y PROCESAMIENTO
# ------------------------------------------
with tab1:
    st.header("Ingrese el conjunto de noticias")
    
    # Alineación vertical de los elementos
    col1, col2 = st.columns([3.5, 1], vertical_alignment="bottom")
    
    with col1:
        # Se añade un key para poder reiniciar el uploader fácilmente
        if "uploader_key" not in st.session_state:
            st.session_state.uploader_key = 0
            
        archivo_subido = st.file_uploader(
            "Arrastra y suelta el archivo JSON aquí", 
            type=["json"], 
            key=f"uploader_{st.session_state.uploader_key}"
        )
        if archivo_subido is not None:
            try:
                st.session_state.noticias_cargadas = json.load(archivo_subido)
                st.success(f"Archivo cargado correctamente. Contiene {len(st.session_state.noticias_cargadas.get('articles', []))} noticias.")
            except Exception as e:
                st.error(f"Error al leer el archivo JSON: {e}")

    with col2:
        btn_procesar = st.button("Procesar", use_container_width=True, type="primary")
        btn_limpiar = st.button("Limpiar", use_container_width=True)

    if btn_limpiar:
        st.session_state.noticias_cargadas = None
        st.session_state.resultados_procesamiento = []
        st.session_state.bandeja_revision = []
        st.session_state.noticias_historial_hash = []
        st.session_state.uploader_key += 1 # Reinicia el uploader
        st.rerun()

    if btn_procesar:
        if st.session_state.noticias_cargadas and "articles" in st.session_state.noticias_cargadas:
            noticias = st.session_state.noticias_cargadas["articles"]
            st.session_state.resultados_procesamiento = []
            st.session_state.bandeja_revision = [] # Limpiar la bandeja en cada nueva ejecución
            
            my_bar = st.progress(0, text="Procesando noticias a través del LLM y reglas...")
            
            for i, noticia in enumerate(noticias):
                id_noticia = noticia.get("article_id", "Desconocido")
                titulo = noticia.get("title", "Sin título")
                
                try:
                    # >>> LLAMADA AL ORQUESTADOR<<<
                    estado, confianza, accion, oportunidad = procesar_noticia_real(noticia)
                    
                    # Si genera una oportunidad, la enviamos a la bandeja 2
                    if oportunidad:
                        st.session_state.bandeja_revision.append(oportunidad)
                        
                    # Extraer los datos detallados para las nuevas columnas
                    evento = titulo
                    empresa = oportunidad["empresa"] if oportunidad else "N/A"
                    tecnologia = oportunidad["tecnologia"] if oportunidad else "N/A"
                    
                    # Para la evidencia, mostramos la URL si está disponible
                    if oportunidad and oportunidad.get("urls") and oportunidad["urls"][0]:
                        evidencia = oportunidad["urls"][0]
                    else:
                        evidencia = noticia.get("url", noticia.get("source", "N/A"))
                        
                    impacto = ", ".join(oportunidad["objetivos_negocio"]) if oportunidad else "N/A"
                    
                    # Construir el motivo detallado (incluyendo alertas si las hay)
                    motivo_final = accion
                    if oportunidad and oportunidad.get("alertas"):
                        motivo_final = f"{accion} ({oportunidad['alertas']})"
                        
                except Exception as e:
                    estado = "Error"
                    confianza = "Baja"
                    evento = titulo
                    empresa = "N/A"
                    tecnologia = "N/A"
                    evidencia = noticia.get("url", "N/A")
                    impacto = "N/A"
                    motivo_final = f"Error de ejecución: {e}"
                    print(f"Error procesando {id_noticia}: {e}")
                
                # Actualización del diccionario con las nuevas columnas solicitadas
                st.session_state.resultados_procesamiento.append({
                    "ID": id_noticia,
                    "Empresa(s)": empresa,
                    "Evento identificado": evento,
                    "Tecnología detectada": tecnologia,
                    "Evidencia utilizada (url)": evidencia,
                    "Impacto de negocio": impacto,
                    "Nivel de confianza": confianza,
                    "Estado": estado,
                    "Motivo de clasificación": motivo_final
                })
                
                my_bar.progress((i + 1) / len(noticias))
                time.sleep(1.5) # Respetar el límite de tokens (TPM) de la API
            
            my_bar.empty()
            st.success("Procesamiento completado.")
        else:
            st.warning("Por favor, cargue un archivo JSON válido primero.")

    if st.session_state.resultados_procesamiento:
        st.subheader("Resultados del Procesamiento")
        df_resultados = pd.DataFrame(st.session_state.resultados_procesamiento)
        
        def color_estados(val):
            color = 'black'
            if val == 'Procesada': color = 'green'
            elif val == 'Error': color = 'red'
            elif val in ['Irrelevante', 'Duplicada']: color = 'gray'
            elif val == 'Requiere revisión': color = 'orange'
            return f'color: {color}'
            
        st.dataframe(
            df_resultados.style.map(color_estados, subset=['Estado']), 
            use_container_width=True, 
            hide_index=True
        )

# ------------------------------------------
# PESTAÑA 2: BANDEJA DE REVISIÓN HUMANA
# ------------------------------------------
with tab2:
    st.header("Bandeja de revisión humana")
    pendientes = [item for item in st.session_state.bandeja_revision if item["estado_revision"] == "Pendiente"]

    if not pendientes:
        st.info("🎉 No hay casos pendientes en la bandeja de revisión.")
    else:
        opciones_expediente = [f"{item['id_oportunidad']} - {item['empresa']}" for item in pendientes]
        expediente_sel = st.selectbox("Seleccione el caso a revisar:", opciones_expediente)
        idx_actual = opciones_expediente.index(expediente_sel)
        caso = pendientes[idx_actual]

        es_cluster_nuevo = "Nuevo" in caso['cluster_estado'] or "Requiere validación" in caso['cluster_estado']
        cumple_regla_cluster = True

        if es_cluster_nuevo:
            noticias_mismo_cluster = [
                {"empresa": item["empresa"], "title": item["evento"]} 
                for item in st.session_state.bandeja_revision 
                if item["cluster"] == caso["cluster"]
            ]
            validacion = cluster_rules.evaluar_propuesta_nuevo_cluster(noticias_mismo_cluster)
            cumple_regla_cluster = validacion["cumple_regla_nuevo_cluster"]

        st.divider()
        col_izq, col_der = st.columns([1.8, 1.2])

        with col_izq:
            st.subheader(f"🏢 Empresa: {caso['empresa']}")
            st.markdown(f"**Evento identificado:** {caso['evento']}")
            st.markdown(f"**Resumen de la señal:** {caso['senal_resumen']}")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Tecnología:** `{caso['tecnologia']}`")
                st.markdown(f"**Nivel de Confianza:** `{caso['confianza']}`")
            with c2:
                if es_cluster_nuevo:
                    st.info(f"🧠 **Recomendación IA (Nuevo Cluster):**\n\n{caso['cluster']}")
                    if cumple_regla_cluster:
                            st.success(f"✅ **Estatus:** Regla cumplida para crear cluster.")
                    else:
                        st.warning(f"⚠️ **Estatus:** No se cumplen condiciones para crear un nuevo cluster. Si se aprueba, se guardará como N/A.")
                else:
                    st.markdown(f"**Cluster:** {caso['cluster']}")
                    st.caption(f"Estatus del Cluster: {caso['cluster_estado']}")
                    
            st.markdown("**Objetivos de negocio impactados:**")
            st.write(", ".join([f"• {obj}" for obj in caso["objetivos_negocio"]]))
            st.markdown("**Evidencias y Fuentes:**")
            for fuente, url in zip(caso["fuentes"], caso["urls"]):
                st.markdown(f"- [{fuente}]({url})")
            if caso["alertas"]:
                st.warning(f" {caso['alertas']}")

        with col_der:
            st.subheader("📊 Evaluación del Trend Score")
            valores_permitidos = [0, 25, 50, 75, 100]
            mat_val = st.select_slider("Materialidad (25% - Humano)", options=valores_permitidos, value=caso["human_inputs"]["materialidad"])
            adop_val = st.select_slider("Adopción comprobada (15% - Humano)", options=valores_permitidos, value=caso["human_inputs"]["adopcion"])

            caso["human_inputs"]["materialidad"] = mat_val
            caso["human_inputs"]["adopcion"] = adop_val

            score_final = trend_calc.calcular_trend_score_total(caso["dimensiones_auto"], caso["human_inputs"])
            st.metric(label="Trend Score Calculado", value=f"{score_final} / 100", delta="≥ 70 Califica a Trend" if score_final >= 70 else "Bajo el umbral")

            with st.expander("Ver desglose de dimensiones"):
                st.write(f"- **Velocidad (25% - Auto):** {caso['dimensiones_auto']['velocidad']}")
                st.write(f"- **Materialidad (25% - Humano):** {mat_val}")
                st.write(f"- **Independencia (15% - Auto):** {caso['dimensiones_auto']['independencia']}")
                st.write(f"- **Adopción (15% - Humano):** {adop_val}")
                st.write(f"- **Persistencia (10% - Auto):** {caso['dimensiones_auto']['persistencia']}")
                st.write(f"- **Alcance (10% - Auto):** {caso['dimensiones_auto']['alcance']}")

            st.divider()
            st.markdown("### Decisiones del Revisor")
            responsable = st.text_input("Responsable", value="Analista CID")

            #Enlazar el text_area al session_state mediante el parámetro 'key'
            comentario = st.text_area("Motivo de la decisión", key=f"comentario_{st.session_state.comentario_key}")

            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                if st.button("✅ Aprobar", type="primary", use_container_width=True):
                    if not comentario: 
                        st.error("Falta comentario.")
                    else:
                        # 1. Determinar Cluster según regla
                        cluster_para_guardar = caso["cluster"]
                        if es_cluster_nuevo and not cumple_regla_cluster:
                            cluster_para_guardar = "N/A"

                        # 2. EVALUAR REGLAS DE TREND Y CANDIDATA
                        objetivos_list = caso.get("objetivos_negocio", [])
                        objetivos_str = ", ".join(objetivos_list) if isinstance(objetivos_list, list) else str(objetivos_list)
                        
                        es_candidata = len(objetivos_list) > 0
                        es_trend = score_final >= 70

                        # Clasificación final según la regla: Empresa Trend + Empresa Candidata = Oportunidad
                        if es_trend and es_candidata:
                            clasificacion_op = "🔥 Oportunidad Trend"
                        elif es_candidata:
                            clasificacion_op = "💡 Candidata (Score < 70)"
                        elif es_trend:
                            clasificacion_op = "📊 Trend (Sin Objetivos)"
                        else:
                            clasificacion_op = "⚪ No Califica"

                        # 3. Guardar en Historial de Decisiones
                        st.session_state.historial_decisiones.append({
                            "id_oportunidad": caso["id_oportunidad"], 
                            "empresa": caso["empresa"], 
                            "estado": "Aprobada", 
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), 
                            "responsable": responsable, 
                            "comentario": comentario, 
                            "trend_score": score_final
                        })
                        
                        # 4. Guardar en Catálogo de Empresas Aprobadas con los nuevos campos
                        st.session_state.empresas_aprobadas.append({
                            "Empresa": caso["empresa"], 
                            "Cluster": cluster_para_guardar, 
                            "Tecnología": caso["tecnologia"], 
                            "Descripción": caso["senal_resumen"], 
                            "Objetivos de Negocio": objetivos_str if objetivos_str else "Sin especificar",
                            "Trend Score": score_final,
                            "¿Es Trend?": "✅ Sí" if es_trend else "❌ No",
                            "¿Es Candidata?": "✅ Sí" if es_candidata else "❌ No",
                            "Clasificación Oportunidad": clasificacion_op,
                            "Fecha Aprobación": datetime.now().strftime("%Y-%m-%d"), 
                            "Responsable": responsable
                        })
                        
                        caso["estado_revision"] = "Aprobada"
                        st.session_state.comentario_key += 1 
                        st.rerun()

            with col_b2:
                if st.button("❌ Rechazar", use_container_width=True):
                    if not comentario: 
                        st.error("Falta comentario.")
                    else:
                        st.session_state.historial_decisiones.append({
                            "id_oportunidad": caso["id_oportunidad"], 
                            "empresa": caso["empresa"], 
                            "estado": "Descartada", 
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), 
                            "responsable": responsable, 
                            "comentario": comentario, 
                            "trend_score": score_final
                        })
                        caso["estado_revision"] = "Descartada"
                        st.session_state.comentario_key += 1
                        st.rerun()

            with col_b3:
                if st.button("🔍 Info", use_container_width=True):
                    if not comentario: 
                        st.error("Falta comentario.")
                    else:
                        st.session_state.historial_decisiones.append({
                            "id_oportunidad": caso["id_oportunidad"], 
                            "empresa": caso["empresa"], 
                            "estado": "Revisión Adicional", 
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), 
                            "responsable": responsable, 
                            "comentario": comentario, 
                            "trend_score": score_final
                        })
                        st.session_state.comentario_key += 1
                        st.rerun()

    if st.session_state.historial_decisiones:
        st.divider()
        st.subheader("📜 Bitácora de Auditoría")
        st.dataframe(pd.DataFrame(st.session_state.historial_decisiones), use_container_width=True, hide_index=True)

# ------------------------------------------
# PESTAÑA 3: EMPRESAS APROBADAS Y BÚSQUEDA
# ------------------------------------------
with tab3:
    st.header("Catálogo de Empresas Aprobadas")
    if not st.session_state.empresas_aprobadas:
        st.info("Aún no hay empresas en el catálogo de aprobadas.")
    else:
        query_busqueda = st.text_input("🔍 Buscar por Nombre, Tecnología, Cluster, Descripción u Objetivos:")
        df_aprobadas = pd.DataFrame(st.session_state.empresas_aprobadas)

        if query_busqueda:
            term = query_busqueda.lower()
            mask = (
                df_aprobadas["Empresa"].str.lower().str.contains(term, na=False) | 
                df_aprobadas["Tecnología"].str.lower().str.contains(term, na=False) | 
                df_aprobadas["Cluster"].str.lower().str.contains(term, na=False) | 
                df_aprobadas["Descripción"].str.lower().str.contains(term, na=False) |
                df_aprobadas["Objetivos de Negocio"].str.lower().str.contains(term, na=False) |
                df_aprobadas["Clasificación Oportunidad"].str.lower().str.contains(term, na=False)
            )
            df_filtrado = df_aprobadas[mask]
        else:
            df_filtrado = df_aprobadas

        st.markdown(f"**Total de empresas en catálogo:** `{len(df_filtrado)}` / `{len(df_aprobadas)}`")
        
        st.dataframe(
            df_filtrado, 
            column_config={
                "Trend Score": st.column_config.ProgressColumn(
                    "Trend Score", 
                    format="%.1f", 
                    min_value=0, 
                    max_value=100
                ),
                "Clasificación Oportunidad": st.column_config.TextColumn(
                    "Clasificación",
                    help="🔥 Oportunidad Trend = Empresa Trend (≥70) + Empresa Candidata (Con objetivos de negocio)"
                )
            }, 
            use_container_width=True, 
            hide_index=True
        )