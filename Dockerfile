# Use uma imagem base oficial do Python 3.12
FROM python:3.12-slim

# Defina o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copie o arquivo de dependências primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instale as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copie o resto dos arquivos da sua aplicação
# Copia a pasta 'app' e a pasta 'static' para dentro do contêiner
COPY ./app /app/app
COPY ./static /app/static

# Exponha a porta que a aplicação vai rodar (Cloud Run usará a variável $PORT)
EXPOSE 8080

# Comando para iniciar a aplicação em produção com Gunicorn
# Aponta para o objeto 'app' dentro do arquivo 'app/main.py'
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "app.main:app"]
