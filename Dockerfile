# Use official Python image (Python 3.11 recommended for mediapipe compatibility)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Upgrade pip and install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy the rest of the app
COPY . .

# Expose the port (Railway sets $PORT dynamically)
EXPOSE $PORT

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=production

# Run Flask using dynamic port
CMD ["sh", "-c", "flask run --host=0.0.0.0 --port=${PORT:-5005}"]
