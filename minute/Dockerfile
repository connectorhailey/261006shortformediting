FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod -R a+rX /app && useradd --uid 10001 --create-home minute && mkdir -p /data && chown minute:minute /data
USER minute
ENV MINUTE_DATA=/data PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8000","--no-proxy-headers"]
