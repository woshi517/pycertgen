# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Install system dependencies including wkhtmltopdf
RUN apt-get update && apt-get install -y \
    wget \
    xz-utils \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libfontconfig1 \
    libfreetype6 \
    libxrender1 \
    libx11-6 \
    libxext6 \
    libxcb1 \
    libxau6 \
    libxdmcp6 \
    && rm -rf /var/lib/apt/lists/*

# Download and install wkhtmltopdf
RUN wget https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/0.12.6/wkhtmltox_0.12.6-1.buster_amd64.deb \
    && dpkg -i wkhtmltox_0.12.6-1.buster_amd64.deb || apt-get -f install -y \
    && rm wkhtmltox_0.12.6-1.buster_amd64.deb

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create static directory for generated images
RUN mkdir -p static

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]