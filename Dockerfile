FROM python:3.12-slim

WORKDIR /app

# Копируем requirements.txt первым для кэширования
COPY . .
#COPY requirements.txt /app/requirements.txt

RUN pwd && ls -la

# Устанавливаем зависимости
RUN pip install --upgrade pip \
&& pip install --no-cache-dir -r requirements.txt


# Копируем остальные файлы
#COPY . .
CMD ["python", "bot.py"]