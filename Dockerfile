FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ACEEST_DATABASE=/app/instance/aceest_fitness.db

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home appuser \
    && mkdir -p /app/instance \
    && chown -R appuser:appuser /app
COPY --chown=appuser:appuser . .
USER appuser
EXPOSE 5000
CMD ["python", "app.py"]
