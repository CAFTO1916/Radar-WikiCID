# Usa una imagen oficial y ligera de Python
FROM python:3.10-slim

# Define el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia e instala las dependencias primero para aprovechar la caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo el código fuente del proyecto
COPY . .

# Expone el puerto por defecto de Streamlit
EXPOSE 8501

# Comando para iniciar la aplicación permitiendo tráfico externo
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]