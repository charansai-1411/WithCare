# withcare-backend/Dockerfile — FastAPI on Cloud Run
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + skill playbooks (load_skill reads /app/skills/*.md at runtime)
COPY app ./app
COPY skills ./skills

# Cloud Run provides $PORT (defaults to 8080). Bind uvicorn to it.
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
