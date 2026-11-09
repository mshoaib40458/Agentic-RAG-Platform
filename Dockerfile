FROM python:3.11-slim

# Create non-root user (UID 1000) for Hugging Face Spaces compatibility
RUN useradd -m -u 1000 user

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend files
COPY --chown=user:user backend/ /app/

# Install python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Create required directories and set permissions
RUN mkdir -p /app/data/storage/qdrant /app/data/storage/uploads && \
    chown -R user:user /app

USER user

# Hugging Face Spaces expects traffic on port 7860
ENV PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 7860"]

