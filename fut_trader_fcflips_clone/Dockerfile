FROM python:3.11-slim

WORKDIR /app
COPY . .

# Install Chrome dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget unzip curl gnupg ca-certificates \
    fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libcups2 libdbus-1-3 libnspr4 libnss3 libx11-xcb1 \
    libxcomposite1 libxdamage1 libxrandr2 xdg-utils libgbm1 libvulkan1 && \
    rm -rf /var/lib/apt/lists/*

# Install latest Chrome
RUN wget -q -O chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt install -y ./chrome.deb && rm chrome.deb

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bot.py"]
