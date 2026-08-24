# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Hugging Face Spaces uses port 7860
EXPOSE 7860

# Run with gunicorn on port 7860 (HF Spaces default)
CMD exec gunicorn --bind 0.0.0.0:7860 --workers 1 --threads 8 --timeout 0 app:app
