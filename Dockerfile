# Entorno reproducible del proyecto.
# Los datos NO se copian a la imagen: se montan en /app/data al correr (ver compose.yml).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

# Dependencias primero, para aprovechar la caché de capas
COPY pyproject.toml constraints.txt ./
COPY src/ src/
# Instalación editable: el paquete ubica sql/, data/ y resultados/ relativo a /app
RUN pip install -c constraints.txt -e ".[test]"

COPY sql/ sql/
COPY tests/ tests/

# Usuario sin privilegios
RUN useradd --create-home --uid 1000 analista \
    && mkdir -p data resultados figuras \
    && chown -R analista /app
USER analista

CMD ["python", "-m", "antitromboticos.analisis"]
