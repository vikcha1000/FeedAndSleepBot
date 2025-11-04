FROM python:3.12-slim

WORKDIR /app

# Копируем requirements.txt первым для кэширования
COPY ./requirements.txt requirements.txt

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt


# Копируем остальные файлы
COPY . .
CMD ["python", "bot.py"]