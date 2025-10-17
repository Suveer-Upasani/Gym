# Use a lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required by OpenCV and MediaPipe
RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 \
    libxcb-render0 libxcb-shape0 libxcb-xfixes0 \
    ffmpeg libgtk-3-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy dependency list
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Ensure required directories exist
RUN mkdir -p data static templates

# Expose Flask port
EXPOSE 5005

# Start the Flask app with Gunicorn for production
CMD ["gunicorn", "-b", "0.0.0.0:5005", "app:app"]
