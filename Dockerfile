FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl netcat-traditional build-essential \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY app ./app
COPY migrations ./migrations

ENV PYTHONUNBUFFERED=1

# Default command overridden by compose services
CMD ["bash", "-lc", "python -c 'print(\"image ready\")'"]
