import os
import json
import time
from pydantic import BaseModel, Field
import streamlit as st
from typing import List, Optional

# Intentar importar Groq de manera segura
try:
    from groq import Groq
    GROQ_DISPONIBLE = True
except ImportError:
    GROQ_DISPONIBLE = False

# ==========================================
# ESQUEMAS DE EXTRACCIÓN (PYDANTIC)
# ==========================================
class ExtraccionSenal(BaseModel):
    contiene_senal_relevante: bool = Field(description="¿La noticia contiene una adopción tecnológica o señal relevante para el negocio?")
    resumen: str = Field(description="Resumen ejecutivo de la señal en máximo 2 oraciones.")
    evento_identificado: str = Field(description="El hecho concreto que ocurrió (ej. 'Despliegue de IA en 120 tiendas').")
    empresas_relacionadas: List[str] = Field(description="Lista de empresas mencionadas como proveedoras o clientes.")
    tecnologia_detectada: str = Field(description="La tecnología principal involucrada (ej. Computer Vision, Digital Twins).")
    impacto_negocio: List[str] = Field(description="Seleccionar de: ['Experiencia del cliente', 'Eficiencia operativa', 'Nuevos ingresos', 'Ninguno']")
    nivel_confianza: str = Field(description="Nivel de confianza en la extracción: 'Alta', 'Media' o 'Baja'.")
    motivo_confianza: str = Field(description="Justificación breve de por qué se asignó ese nivel de confianza.")

# ==========================================
# AGENTE EXTRACTOR
# ==========================================
def instanciar_cliente():
    """Inicializa el cliente de Groq verificando Streamlit Secrets y Variables de Entorno."""
    if not GROQ_DISPONIBLE:
        print("⚠️ Librería 'groq' no instalada. Usando modo simulado.")
        return None

    api_key = None
    
    # 1. Intentar leer desde Streamlit Secrets
    try:
        if "GROQ_API_KEY" in st.secrets:
            api_key = st.secrets["GROQ_API_KEY"]
    except Exception:
        pass

    # 2. Intentar leer desde Variables de Entorno
    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")
        
    if not api_key:
        print("⚠️ GROQ_API_KEY no encontrada. Operando en MODO SIMULADO local.")
        return None
        
    print("✅ GROQ_API_KEY detectada correctamente. Conectando a la API de Groq...")
    return Groq(api_key=api_key)

def extraer_informacion_semantica(texto_noticia: str) -> dict:
    """
    Envía el texto de la noticia al LLM para extraer entidades y contexto semántico.
    Forza la salida al esquema ExtraccionSenal.
    """
    cliente = instanciar_cliente()
    
    # MODO SIMULADO (Fallback si no hay API Key configurada para la demo local)
    if not cliente:
        return simular_extraccion_llm(texto_noticia)

    prompt_sistema = (
        "Eres un analista experto en inteligencia tecnológica. Tu tarea es extraer "
        "información estructurada de noticias de mercado y devolverla exclusivamente en un formato JSON válido. "
        "Sé objetivo y estricto. Si la noticia es sobre cambios de imagen, uniformes o temas no tecnológicos, "
        "marca 'contiene_senal_relevante' como falso.\n\n"
        "REGLAS OBLIGATORIAS PARA 'nivel_confianza':\n"
        "- Asigna 'Baja' SI: La noticia es un rumor, proviene de publicaciones anónimas/sin fuente oficial, "
        "falta URL/evidencia primaria, o el nombre de la empresa es ambiguo y carece de datos corporativos.\n"
        "- Asigna 'Media' SI: La empresa utiliza un alias comercial no registrado o la tecnología requiere un cluster nuevo, "
        "pero la fuente y el hecho sí están bien fundamentados.\n"
        "- Asigna 'Alta' SI: La fuente es oficial, la empresa está clara y hay métricas o hechos concretos comprobables.\n\n"
        "Estructura JSON requerida (usar exactamente estas llaves):\n"
        '1. "contiene_senal_relevante": (booleano)\n'
        '2. "resumen": (string)\n'
        '3. "evento_identificado": (string)\n'
        '4. "empresas_relacionadas": (lista de strings)\n'
        '5. "tecnologia_detectada": (string)\n'
        '6. "impacto_negocio": (lista de strings)\n'
        '7. "nivel_confianza": (string, "Alta", "Media" o "Baja")\n'
        '8. "motivo_confianza": (string)'
    )

    max_intentos = 3
    for intento in range(max_intentos):
        try:
            chat_completion = cliente.chat.completions.create(
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": f"Analiza esta noticia:\n\n{texto_noticia}"}
                ],
                model="openai/gpt-oss-20b",
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            respuesta_json = chat_completion.choices[0].message.content
            datos_extraidos = json.loads(respuesta_json)
            
            extraccion_validada = ExtraccionSenal(**datos_extraidos)
            return extraccion_validada.model_dump()
            
        except Exception as e:
            error_msg = str(e)
            # Si es un error de límite de velocidad (429), esperar y reintentar
            if "429" in error_msg or "rate_limit" in error_msg.lower():
                if intento < max_intentos - 1:
                    time.sleep(3)  # Pausa de 3 segundos para liberar la cuota de tokens
                    continue
            
            print(f"Error en el LLM Gateway: {e}")
            return {
                "contiene_senal_relevante": False,
                "resumen": "Error en extracción semántica por límite de tokens o formato.",
                "evento_identificado": "Error",
                "empresas_relacionadas": [],
                "tecnologia_detectada": "Desconocida",
                "impacto_negocio": [],
                "nivel_confianza": "Baja",
                "motivo_confianza": str(e)
            }

def simular_extraccion_llm(texto: str) -> dict:
    """
    Función de respaldo que simula el comportamiento del LLM si no se cuenta con internet 
    o llaves de API durante la demostración, cumpliendo con la regla de funcionar localmente sin costos.
    """
    texto_lower = texto.lower()
    
    if "uniforme" in texto_lower or "colores" in texto_lower:
        return {
            "contiene_senal_relevante": False,
            "resumen": "Noticia sobre cambio de identidad visual, sin impacto tecnológico.",
            "evento_identificado": "Cambio de uniformes",
            "empresas_relacionadas": ["Mercado Norte"],
            "tecnologia_detectada": "Ninguna",
            "impacto_negocio": ["Ninguno"],
            "nivel_confianza": "Alta",
            "motivo_confianza": "Términos explícitos de diseño no tecnológico."
        }
        
    if "gemelo digital" in texto_lower or "digital twin" in texto_lower:
        empresas = ["HelixGrid"] if "helixgrid" in texto_lower else ["SynapseFabric", "InfraCloud"]
        return {
            "contiene_senal_relevante": True,
            "resumen": "Despliegue o piloto de tecnología de simulación de infraestructura.",
            "evento_identificado": "Piloto de Gemelo Digital",
            "empresas_relacionadas": empresas,
            "tecnologia_detectada": "Digital Twins",
            "impacto_negocio": ["Eficiencia operativa"],
            "nivel_confianza": "Media",
            "motivo_confianza": "Tecnología clara, pero requiere evaluar si existe en el catálogo."
        }
        
    # Extracción por defecto para el resto de casos
    return {
        "contiene_senal_relevante": True,
        "resumen": "Adopción de plataforma tecnológica para mejora de procesos.",
        "evento_identificado": "Despliegue tecnológico",
        "empresas_relacionadas": ["Empresa Detectada"],
        "tecnologia_detectada": "Software Empresarial",
        "impacto_negocio": ["Eficiencia operativa"],
        "nivel_confianza": "Alta",
        "motivo_confianza": "Extracción simulada completada."
    }