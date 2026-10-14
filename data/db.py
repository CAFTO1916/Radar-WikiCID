import sqlite3
import os

# Ruta donde se guardará la base de datos dentro de la carpeta data
DB_PATH = os.path.join(os.path.dirname(__file__), "radar.db")

def get_connection():
    """Crea y retorna una conexión a la base de datos SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permite acceder a las columnas por nombre
    return conn

def init_db():
    """
    Inicializa las tablas necesarias para persistir las decisiones, 
    la bitácora de auditoría y las empresas aprobadas.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Tabla de Auditoría / Historial de Decisiones Humana
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bitacora_decisiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_oportunidad TEXT NOT NULL,
            empresa TEXT NOT NULL,
            estado TEXT NOT NULL,
            fecha TEXT NOT NULL,
            responsable TEXT NOT NULL,
            comentario TEXT,
            trend_score REAL,
            evidencia TEXT
        )
    """)

    # 2. Tabla de Empresas Aprobadas (Catálogo Final Master)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS empresas_aprobadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL UNIQUE,
            cluster TEXT NOT NULL,
            tecnologia TEXT NOT NULL,
            descripcion TEXT,
            trend_score REAL,
            fecha_aprobacion TEXT NOT NULL,
            responsable TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print("✓ Base de datos local inicializada correctamente en radar.db")

if __name__ == "__main__":
    init_db()