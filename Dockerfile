FROM python:3.11-slim

# Install system dependencies for WeasyPrint
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libgtk-3-0 \
    libffi-dev \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create static directory
RUN mkdir -p static

# Create certificates directory for Railway persistent volume
# Note: In Railway, this will be mounted as a persistent volume at /mnt/pdfs/generated
RUN mkdir -p /mnt/pdfs/generated

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]