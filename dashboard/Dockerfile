FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard/package*.json ./dashboard/
RUN cd dashboard && npm ci --omit=dev

COPY . .
RUN mkdir -p data

WORKDIR /app/dashboard
EXPOSE 3000
CMD ["node", "server.js"]
