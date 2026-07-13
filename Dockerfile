FROM python:3.12-slim

WORKDIR /app

# Install requirements first so Docker caches this layer
# (only reinstalls if requirements.txt actually changes)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}