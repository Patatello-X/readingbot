# استخدم صورة بايثون
FROM python:3.10-slim

# إعداد مجلد العمل
WORKDIR /app

# نسخ كل الملفات
COPY . .

# تثبيت المتطلبات
RUN pip install --no-cache-dir -r requirements.txt

# المتغيرات البيئية
ENV BOT_TOKEN=${BOT_TOKEN}
ENV OPENROUTER_API_KEY=${OPENROUTER_API_KEY}

# أمر التشغيل
CMD ["python", "bot.py"]
