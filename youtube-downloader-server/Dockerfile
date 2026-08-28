FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# yt-dlpがYouTubeのJS認証チャレンジ（Bot判定回避）を解決するためにDenoランタイムを必要とする
RUN curl -fsSL https://deno.land/install.sh | sh \
    && ln -s /root/.deno/bin/deno /usr/local/bin/deno

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 重要: jobs辞書・semaphoreをインメモリで保持する設計のため、プロセスは必ず1つで起動すること。
# --workers を2以上にすると、ワーカープロセスごとに別々のjobs/semaphoreが持たれてしまい、
# 進捗ポーリングやダウンロード枠の制御が壊れる。並列度は --threads で確保する。
CMD gunicorn --workers 1 --threads 8 --bind 0.0.0.0:${PORT:-5000} --timeout 1800 app:app
