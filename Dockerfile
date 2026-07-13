FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# UID 1000 coincide con el usuario típico del host: evita que los
# archivos que el contenedor escribe en el volumen de desarrollo
# (__pycache__, migraciones generadas, etc.) queden root-owned.
RUN useradd --uid 1000 --create-home appuser
COPY --chown=appuser:appuser . .
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]