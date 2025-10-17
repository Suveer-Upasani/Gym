# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy the rest of the app
COPY . .

# Expose a fixed port (for Docker; app uses dynamic $PORT)
EXPOSE 5005

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Gunicorn directly, Railway injects $PORT
ENTRYPOINT ["gunicorn", "-w", "4", "-b", "0.0.0.0:${PORT:-5005}", "app:app"]
