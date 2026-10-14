import json
import os

PATH_EMPRESAS = os.path.join(os.path.dirname(__file__), "../data/empresas_existentes.json")

def cargar_empresas():
    if os.path.exists(PATH_EMPRESAS):
        with open(PATH_EMPRESAS, "r", encoding="utf-8") as f:
            return json.load(f).get("companies", [])
    return []

def buscar_empresa_en_texto(texto_noticia):
    """
    Evalúa menciones de empresas en el texto.
    Retorna: dict con empresa_id, canonical_name, match_type ('strong', 'weak', 'ambiguous') y requiere_revision.
    """
    empresas = cargar_empresas()
    texto_lower = texto_noticia.lower()

    for emp in empresas:
        canonical = emp["canonical_name"]
        aliases = emp.get("aliases", [])
        
        # Coincidencia por Nombre Canónico
        if canonical.lower() in texto_lower:
            # Caso especial de advertencia por alias/ambigüedad (ej. Atlas)
            if emp.get("identity_warning"):
                return {
                    "company_id": emp["company_id"],
                    "canonical_name": canonical,
                    "match_type": "ambiguous",
                    "requiere_revision": True,
                    "motivo": emp["identity_warning"]
                }
            return {
                "company_id": emp["company_id"],
                "canonical_name": canonical,
                "match_type": "strong",
                "requiere_revision": False,
                "motivo": "Coincidencia directa por nombre registrado."
            }

        # Coincidencia por Alias
        for alias in aliases:
            if alias.lower() in texto_lower:
                if emp.get("identity_warning"):
                    return {
                        "company_id": emp["company_id"],
                        "canonical_name": canonical,
                        "match_type": "ambiguous",
                        "requiere_revision": True,
                        "motivo": emp["identity_warning"]
                    }
                return {
                    "company_id": emp["company_id"],
                    "canonical_name": canonical,
                    "match_type": "weak",
                    "requiere_revision": False,
                    "motivo": f"Coincidencia por alias: {alias}"
                }

    return None