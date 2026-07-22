FROM python:3.11-slim

WORKDIR /app

# Create directories
RUN mkdir -p /app/trained_models

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5002

# Run the application
CMD ["python", "app.py"]