FROM python:3.11-slim
ARG INSTALL_ML=false
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libzbar0 libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt backend/requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_ML" = "true" ]; then pip install --no-cache-dir -r requirements-ml.txt; fi
COPY backend/ ./
COPY scripts/ ./scripts/
COPY rulepacks/ ./rulepacks/
ENV PYTHONPATH=/app
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
