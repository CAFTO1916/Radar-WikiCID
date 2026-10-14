import json
import os
from datetime import datetime

PATH_HISTORIAL = os.path.join(os.path.dirname(__file__), "../data/historial_trend.json")

def cargar_historial():
    if os.path.exists(PATH_HISTORIAL):
        with open(PATH_HISTORIAL, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def calcular_dimensiones_automaticas(company_ref):
    """
    Calcula Velocidad, Independencia, Persistencia y Alcance 
    utilizando el historial de eventos en historial_trend.json
    """
    data = cargar_historial()
    empresas = data.get("companies", [])
    
    # Buscar la empresa en el historial
    empresa_data = next((c for c in empresas if c["company_ref"] == company_ref), None)
    
    if not empresa_data:
        # Si es una empresa totalmente nueva (ej. HelixGrid o SynapseFabric sin historial previo)
        return {"velocidad": 25, "independencia": 25, "persistencia": 12.5, "alcance": 25}

    eventos = empresa_data.get("historical_events", [])
    
    # 1. Velocidad (Eventos en ventana)
    cant_eventos = len(eventos)
    if cant_eventos == 0: velocidad = 0
    elif cant_eventos == 1: velocidad = 25
    elif cant_eventos == 2: velocidad = 50
    elif cant_eventos == 3: velocidad = 75
    else: velocidad = 100

    # 2. Independencia de evidencia (Fuentes independientes)
    fuentes_indep = sum(1 for e in eventos if e.get("independent_source", False))
    if fuentes_indep == 0: independencia = 0
    elif fuentes_indep == 1: independencia = 25
    elif fuentes_indep == 2: independencia = 50
    elif fuentes_indep == 3: independencia = 75
    else: independencia = 100

    # 3. Persistencia (Semanas activas / 8 * 100)
    semanas_unicas = len(set(e.get("week") for e in eventos if "week" in e))
    persistencia = min(100.0, round((semanas_unicas / 8.0) * 100, 1))

    # 4. Alcance (Sectores distintos)
    sectores_unicos = len(set(e.get("sector") for e in eventos if "sector" in e))
    if sectores_unicos == 0: alcance = 0
    elif sectores_unicos == 1: alcance = 25
    elif sectores_unicos == 2: alcance = 50
    elif sectores_unicos == 3: alcance = 75
    else: alcance = 100

    return {
        "velocidad": velocidad,
        "independencia": independencia,
        "persistencia": persistencia,
        "alcance": alcance
    }

def calcular_trend_score_total(dims_auto, human_inputs):
    """
    Suma ponderada combinando las 4 dimensiones automáticas con los 2 inputs humanos:
    Score = (Velocidad * 0.25) + (Materialidad * 0.25) + (Independencia * 0.15) +
            (Adopción * 0.15) + (Persistencia * 0.10) + (Alcance * 0.10)
    """
    mat = human_inputs.get("materialidad", 0)
    adop = human_inputs.get("adopcion", 0)
    
    score = (
        (dims_auto.get("velocidad", 0) * 0.25) +
        (mat * 0.25) +
        (dims_auto.get("independencia", 0) * 0.15) +
        (adop * 0.15) +
        (dims_auto.get("persistencia", 0) * 0.10) +
        (dims_auto.get("alcance", 0) * 0.10)
    )
    return round(score, 1)