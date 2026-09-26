# Optional self-hosted Ollama. Build from the repo root:
#   docker build -f infra/ollama/Dockerfile -t travel-ollama .
# Mount persistent storage at /root/.ollama, then pull llama3.2:3b and embeddinggemma.
FROM ollama/ollama:latest

ENV OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_KEEP_ALIVE=10m

EXPOSE 11434

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
    CMD ollama list >/dev/null 2>&1 || exit 1

CMD ["serve"]
