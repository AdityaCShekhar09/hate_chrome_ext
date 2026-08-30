FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt

COPY backend/toxicity.h5 backend/vocabulary.json ./
COPY backend/app.py ./
COPY openapi.yaml /app/openapi.yaml

EXPOSE 5050

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5050/health')"

CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "1", "--timeout", "120", "app:app"]
