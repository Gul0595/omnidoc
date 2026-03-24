FROM python:3.10-slim

WORKDIR /app

# Correct path
COPY backend/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy full backend
COPY backend .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
