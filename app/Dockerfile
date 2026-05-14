FROM python:3.12-slim

# Evitar archivos .pyc y logs en buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema (psycopg2, gdal para postgis, netcat para wait-for-db)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    postgresql-client \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python (desde la raíz del proyecto)
COPY requirements/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt

# Fixtures (recurso estático del proyecto).
# Se copia fuera de /app para que el bind mount `./app:/app` (dev) no las oculte.
# start-web.sh las carga desde aquí en cada arranque (idempotente).
COPY fixtures/ /seed/fixtures/

# Copiar código fuente
COPY app/ .

# Scripts de arranque ejecutables
RUN chmod +x wait-for-db.sh start-web.sh
