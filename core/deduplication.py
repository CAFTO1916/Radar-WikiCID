import hashlib

def obtener_hash_texto(texto):
    """Genera un hash SHA-256 para detectar duplicados exactos por texto."""
    return hashlib.sha256(texto.strip().lower().encode('utf-8')).hexdigest()

def evaluar_duplicidad_noticia(noticia, noticias_procesadas):
    """
    Evalúa si la noticia actual es un duplicado estricto por URL o Hash.
    Retorna (es_duplicada, motivo)
    """
    url_actual = noticia.get("url")
    contenido_actual = noticia.get("content", "")
    hash_actual = obtener_hash_texto(contenido_actual)

    for np in noticias_procesadas:
        # 1. Duplicado exacto por URL
        if url_actual and np.get("url") == url_actual:
            return True, f"URL duplicada detectada: {url_actual}"
        
        # 2. Duplicado por Hash de contenido
        if np.get("hash") == hash_actual:
            return True, "Contenido de texto idéntico a una noticia procesada previamente."

    return False, None