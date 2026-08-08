FROM python:3.11-slim

# Install ffmpeg for video/audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create downloads directory
RUN mkdir -p downloads

# Expose web UI port
EXPOSE 8080

# Default: run web UI
CMD ["python", "cli.py", "--web", "--host", "0.0.0.0", "--port", "8080"]
