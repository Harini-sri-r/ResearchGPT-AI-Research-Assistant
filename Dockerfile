FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence-transformers \
    EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2 \
    OLLAMA_BASE_URL=http://localhost:11434 \
    OLLAMA_MODEL=llama3 \
    OLLAMA_TIMEOUT_SECONDS=120 \
    OLLAMA_TEMPERATURE=0.2 \
    OLLAMA_TOP_P=0.95 \
    OLLAMA_NUM_PREDICT=2048 \
    NLTK_DATA=/usr/local/share/nltk_data

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip

# Install CPU-only PyTorch
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

# Install the remaining packages
RUN pip install -r requirements.txt

# Download NLTK data
RUN python -m nltk.downloader -d /usr/local/share/nltk_data punkt punkt_tab stopwords

# Download the embedding model at build time so uploads do not fetch it during a request
RUN mkdir -p /app/.cache/huggingface /app/.cache/sentence-transformers \
    && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/papers /app/chromadb \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=5)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
