FROM ghcr.io/home-assistant/base:latest

RUN apk add --no-cache \
    chromium \
    chromium-chromedriver \
    xvfb \
    x11vnc \
    openbox \
    novnc \
    websockify \
    python3 \
    py3-pip \
    ttf-dejavu \
    font-noto-cjk \
    && pip3 install --no-cache-dir --break-system-packages selenium==4.35.0 requests==2.32.5

COPY run.sh /run.sh
COPY bot.py /bot.py
RUN chmod +x /run.sh

CMD ["/run.sh"]
