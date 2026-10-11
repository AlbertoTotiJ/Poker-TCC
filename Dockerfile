FROM python:3.11-slim

# Evita arquivos .pyc e garante saída imediata no terminal
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=5000

WORKDIR /app

# Dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instala as dependências Python
COPY requirements/ requirements/

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements/base.txt
RUN pip install --no-cache-dir -r requirements/dev.txt

# Copia o restante do projeto
COPY . .

# Expõe a porta da mesa virtual web
EXPOSE 5000

# Inicializa o servidor da mesa gráfica web por padrão
CMD ["python", "scripts/play_poker_web.py", "--host", "0.0.0.0", "--port", "5000", "--no-browser"]