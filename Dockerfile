FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY config/ config/
COPY scripts/ scripts/
COPY data/processed/ data/processed/
COPY data/features/ data/features/

# 런타임 데이터 디렉토리
RUN mkdir -p data/cache data/models

EXPOSE 8000

CMD ["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
