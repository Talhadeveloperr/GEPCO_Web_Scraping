FROM python:3.10-slim

# Install system dependencies needed for headless Google Chrome
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    unzip \
    gnupg \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgdk-pixbuf-2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libnss3 \
    libxss1 \
    libasound2 \
    fonts-liberation \
    xdg-utils \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install official stable Chrome
RUN curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable || true \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

# Run using gunicorn bound to Render's required port
# Force 1 lightweight process worker with a single thread and long lifecycle timeouts
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "1", "--threads", "1", "--timeout", "180", "app:app"]