# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app


RUN sed -i 's|http://deb.debian.org|http://ftp.ru.debian.org|g' /etc/apt/sources.list.d/debian.sources

# Cистемные зависимости
RUN apt update && apt install -y build-essential libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt ./

# Устанавливаем зависимости
RUN pip install --upgrade pip && pip install -r requirements.txt --no-cache-dir

# Копируем приложение
COPY ./app ./app
COPY ./alembic ./alembic
COPY alembic.ini ./
COPY .env ./

# Команда запуска
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 