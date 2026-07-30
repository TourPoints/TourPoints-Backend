FROM python:3.12-slim

# 1. Definir argumentos con valor por defecto 1000
ARG USER_UID=1000
ARG USER_GID=1000

WORKDIR /app

# 2. Instalar dependencias como root (es más seguro y eficiente para las capas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Crear el grupo y usuario dinámicamente usando los argumentos
RUN groupadd --gid $USER_GID appuser \
    && useradd --uid $USER_UID --gid $USER_GID --create-home appuser

# 4. Copiar los archivos asignando la propiedad al nuevo usuario
COPY --chown=appuser:appuser . .

# 5. Cambiar al usuario no-root
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
