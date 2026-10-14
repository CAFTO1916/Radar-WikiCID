# Mini Radar WikiCID

El **Mini Radar de WikiCID** es una aplicación web interactiva construida con [Streamlit](https://streamlit.io/) para la inteligencia tecnológica. Su objetivo es procesar lotes de noticias de mercado, extraer señales relevantes mediante Inteligencia Artificial (LLMs), y evaluar el impacto de negocio de nuevas tecnologías mediante un flujo de revisión humana (*Human-in-the-loop*).

## Características Principales

* **Procesamiento de Noticias:** Carga de archivos JSON con artículos y noticias tecnológicas.

* **Desduplicación Estricta:** Filtrado automático de noticias repetidas mediante evaluación de URLs y Hashes.

* **Extracción Semántica con LLMs:** Integración con la API de **Groq** (openai/gpt-oss-20b) para extraer empresas, eventos, tecnologías e impacto de negocio.

* **Clasificación Determinista:** Asignación automática a clusters tecnológicos y catálogos de empresas mediante reglas estrictas.

* **Bandeja de Revisión Humana:** Interfaz para que analistas validen la información, ajusten el *Trend Score* y aprueben las oportunidades.

* **Reglas de Negocio Inteligentes:** Validación automática para la creación de nuevos clusters tecnológicos (mínimo 2 empresas y 2 eventos).

* **Catálogo de Aprobadas:** Buscador avanzado y catalogación automática de empresas como "💡 Candidata" o "🔥 Oportunidad Trend".

## Requisitos Previos

* **Python 3.10 o superior** (si se ejecuta localmente).

* **Docker y Docker Desktop** (si se ejecuta mediante contenedores).

* **Groq API Key:** Una clave válida de Groq para el agente de extracción semántica.

## Configuración del Entorno

Para que la extracción semántica funcione correctamente, necesitas configurar tu llave de la API de Groq. El sistema está preparado para leerla desde los secretos de Streamlit de manera segura.
*(NOTA: esta configuracion solo se raliza si no se encuntra la carpeta `.streamlit` en el programa).*

1. En la raíz del proyecto, crea una carpeta llamada `.streamlit` (asegúrate de incluir el punto inicial).

2. Dentro de esa carpeta, crea un archivo llamado `secrets.toml`.

3. Agrega tu clave de API de la siguiente manera:

```
GROQ_API_KEY = "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"

```
## Ejecución Local (Python)

1. **Clonar el repositorio:**

   ```
   git clone https://github.com/CAFTO1916/Radar-WikiCID.git
   cd "Radar-WikiCID"
   
   ```

2. **(Opcional pero recomendado) Crear un entorno virtual:**

   ```
   python -m venv env
   # En Windows:
   .\env\Scripts\activate
   # En Mac/Linux:
   source env/bin/activate
   
   ```

3. **Instalar las dependencias:**

   ```
   pip install -r requirements.txt
   
   ```

4. **Ejecutar la aplicación:**

   ```
   streamlit run app.py
   
   ```

   La aplicación se abrirá automáticamente en tu navegador en `http://localhost:8501`.

## Ejecución con Docker

Si prefieres ejecutar el proyecto en un entorno aislado sin instalar dependencias de Python localmente, puedes usar Docker. **Asegúrate de que tu archivo `.dockerignore` NO incluya la carpeta `.streamlit/`** para que el contenedor pueda leer tu API Key.

1. **Construir la imagen de Docker:**

   ```
   docker build -t radar-wikicid .
   
   ```

2. **Ejecutar el contenedor:**

   ```
   docker run -p 8501:8501 radar-wikicid
   
   ```

3. **Acceder a la aplicación:**
   Abre tu navegador web e ingresa a `http://localhost:8501`.

## 📂 Estructura del Proyecto

```
Radar-WikiCID/
├── .streamlit/
│   └── secrets.toml            # Credenciales de API
├── agents/
│   └── extractor_agent.py      # Agente LLM para extracción semántica (Groq)
├── core/
│   ├── cluster_rules.py        # Reglas de negocio para clusters
│   ├── company_matcher.py      # Identificación de empresas en catálogo
│   ├── deduplication.py        # Lógica de desduplicación de noticias
│   └── trend_calculator.py     # Cálculo algorítmico del Trend Score
├── data/                       # Archivos JSON de catálogos base
├── app.py                      # Orquestador principal y UI (Streamlit)
├── README.md                   # Documentación principal del proyecto
├── requirements.txt            # Dependencias de Python
├── Dockerfile                  # Instrucciones de construcción para Docker
├── .dockerignore               # Archivos excluidos del contenedor
└── .gitignore                  # Archivos excluidos del repositorio Git



```