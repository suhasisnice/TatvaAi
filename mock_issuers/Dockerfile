FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.6 uvicorn[standard]==0.34.0
COPY mock_issuers/ ./
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
