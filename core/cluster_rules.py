import json
import os
import re

PATH_CLUSTERS = os.path.join(os.path.dirname(__file__), "../data/clusters.json")

def cargar_clusters():
    if os.path.exists(PATH_CLUSTERS):
        with open(PATH_CLUSTERS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def clasificar_cluster_determinista(texto):
    datos = cargar_clusters()
    catalogo_clusters = datos.get("clusters", [])
    # Iteramos sobre la variable que YA existe en este archivo
    for cluster in catalogo_clusters: 
        
        # 1. Exclusiones dinámicas: Busca la palabra exacta aislada
        tiene_exclusion = False
        for exc in cluster.get("exclusions", []):
            if re.search(rf'\b{re.escape(exc)}\b', texto, re.IGNORECASE):
                tiene_exclusion = True
                break
                
        if tiene_exclusion:
            continue # Salta este cluster si encontró una exclusión
            
        # 2. Keywords dinámicas: Busca la palabra clave exacta aislada
        for kw in cluster.get("keywords", []):
            if re.search(rf'\b{re.escape(kw)}\b', texto, re.IGNORECASE):
                return cluster["cluster_id"]
                
    return None

def evaluar_propuesta_nuevo_cluster(noticias_acumuladas):
    """
    Aplica la regla de negocio para proponer un cluster nuevo:
    - Mínimo 2 empresas distintas
    - Mínimo 2 eventos independientes
    
    Recibe una lista de dicts con información de señales no clasificadas en el catálogo.
    """
    data_cat = cargar_clusters()
    policy = data_cat.get("new_cluster_policy", {})
    min_empresas = policy.get("minimum_distinct_companies", 2)
    min_eventos = policy.get("minimum_independent_events", 2)

    # Filtrar señales que no pertenecen a ningún cluster del catálogo
    empresas_detectadas = set()
    eventos_detectados = set()

    for n in noticias_acumuladas:
        empresa = n.get("empresa")
        evento = n.get("evento_id") or n.get("title")
        
        if empresa and empresa != "Desconocida":
            empresas_detectadas.add(empresa)
        if evento:
            eventos_detectados.add(evento)

    cant_empresas = len(empresas_detectadas)
    cant_eventos = len(eventos_detectados)

    cumple_regla = (cant_empresas >= min_empresas) and (cant_eventos >= min_eventos)

    return {
        "cumple_regla_nuevo_cluster": cumple_regla,
        "empresas_distintas_count": cant_empresas,
        "eventos_independientes_count": cant_eventos,
        "empresas": list(empresas_detectadas),
        "accion": "propose_for_human_review" if cumple_regla else "insufficient_evidence",
        "motivo": (
            f"Se detectaron {cant_empresas} empresas distintas y {cant_eventos} eventos independientes. "
            f"Cumple con la política (mínimo {min_empresas} empresas y {min_eventos} eventos)."
            if cumple_regla else
            f"Evidencia insuficiente. Se requieren al menos {min_empresas} empresas y {min_eventos} eventos."
        )
    }