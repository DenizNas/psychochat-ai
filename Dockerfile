FROM python:3.12-slim

# 1. Set environment variables to optimize Python performance inside the container
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 2. Install any system dependencies needed for compiling extensions (like bcrypt, psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 3. Create a non-root group and user for security hardening
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# 4. Set up the working directory and create directories for persistent volumes
WORKDIR /app
RUN mkdir -p /app/data /app/uploads /app/logs && \
    chown -R appuser:appgroup /app

# 5. Copy requirements and install them securely using pip cache-friendly method
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy the rest of the application source code and adjust ownership
COPY . /app/
RUN chown -R appuser:appgroup /app

# 7. Switch to the non-root user to avoid running the container as root
USER appuser

# 8. Expose the standard backend port
EXPOSE 8001

# 9. Start the FastAPI application using Uvicorn
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8001"]
