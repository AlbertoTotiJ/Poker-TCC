# Evita arquivos .pyc e garante saída imediata no terminal
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Instala as dependências Python
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do projeto
COPY . .

CMD ["python"]

docker-compose.yml

version: "3.9"

services:

  poker:

    build: .

    container_name: poker-tcc

    working_dir: /app

    volumes:
      - .:/app

    stdin_open: true

    tty: true