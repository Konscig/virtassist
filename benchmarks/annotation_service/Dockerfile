FROM ollama/ollama:latest

WORKDIR /app

RUN apt-get update && apt-get install -y python3-pip && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir --break-system-packages httpx
RUN pip3 install --no-cache-dir --break-system-packages ollama
RUN pip3 install --no-cache-dir --break-system-packages pydantic

COPY annotate_with_ollama.py /app/annotate_with_ollama.py
COPY data/confluence_urls.json /app/confluence_urls.json
COPY entrypoint.sh /app/entrypoint.sh
COPY monitor_progress.py /app/monitor_progress.py

RUN chmod +x /app/entrypoint.sh

EXPOSE 11434

CMD ["/app/entrypoint.sh"]
