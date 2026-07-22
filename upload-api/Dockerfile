FROM python:3.11-slim

WORKDIR /app

# Create tmp directory with proper permissions
RUN mkdir -p /tmp && chmod 1777 /tmp

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]