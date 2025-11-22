FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set Python to unbuffered mode for real-time logging
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Cloud Run requires the container to listen on 0.0.0.0:8080
EXPOSE 8080

CMD ["gunicorn", "--bind=0.0.0.0:8080", "--workers=1", "--threads=8", "--timeout=0", "--access-logfile=-", "--error-logfile=-", "main:app"]
