# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Set non-interactive debian frontend and python environment flags
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies required for OpenCV, Rasterio, and C-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application repository
COPY . .

# Create required runtime directories
RUN mkdir -p data/raw/uploads data/processed/reports data/processed/benchmarks models/weights

# Expose default container port (7860 matches Hugging Face Spaces standard)
EXPOSE 7860

# Launch Uvicorn ASGI server for FastAPI orchestrator API
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
