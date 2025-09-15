FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências do sistema (ex.: compilar libs, se necessário)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY ./app /app/app
COPY ./static /app/static

# Cria usuário não-root (mais seguro)
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Porta default (bate com docker-compose)
EXPOSE 8080

# ====== CMD DEV (verboso) ======
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "--log-level", "debug", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "app.main:app"]

# ====== CMD PROD (enxuto) ======
#CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "2", "-b", "0.0.0.0:8080", "app.main:app"]
