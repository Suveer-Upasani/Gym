# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for OpenCV and MediaPipe
RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 \
    libxcb-render0 libxcb-shape0 libxcb-xfixes0 \
    ffmpeg libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy the rest of the app
COPY . .

# Create necessary directories
RUN mkdir -p data static templates

# Expose port
EXPOSE 5005

# Use a simple Python command to run the app
CMD ["python", "app.py"]
