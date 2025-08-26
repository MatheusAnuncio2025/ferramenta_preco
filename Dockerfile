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
# APONTOS-CHAVE DA CORREÇÃO:
# --log-level "debug": Aumenta a verbosidade dos logs para vermos mais detalhes.
# --access-logfile "-": Envia os logs de acesso para a saída padrão (visível no Docker).
# --error-logfile "-": Envia os logs de erro para a saída padrão.
# --capture-output: Captura os prints e logs da sua aplicação e os envia para o log de erro do Gunicorn.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "--log-level", "debug", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "app.main:app"]