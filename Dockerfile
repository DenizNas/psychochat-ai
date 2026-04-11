FROM python:3.12-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Ortam değişkenlerini ayarla
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Requirements dosyasını kopyala ve bağımlılıkları yükle
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Projenin geri kalanını kopyala
COPY . /app/

# Portu dışarıya aç
EXPOSE 8000

# Uygulamayı başlat
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
