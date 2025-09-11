# PyCertGen - PDF Certificate Generator

A FastAPI-based service for generating PDF certificates with custom dimensions.

## Features

- Generate PDFs from HTML content with custom page dimensions
- Default A4 landscape size (297mm x 210mm)
- Store certificate metadata in SQLite database
- Serve generated certificates via URL
- Automatic cleanup of old files (older than 1 hour)

## API Endpoints

### Generate PDF Certificate

**POST** `/html-to-pdf`

Generate a PDF from HTML content with custom dimensions.

**Request Body:**
```json
{
  "html": "<html>...</html>",
  "width": 297.0,
  "height": 210.0,
  "certificate_data": {
    "recipient_name": "John Doe",
    "course_name": "Python Programming",
    "completion_date": "2023-01-15"
  }
}
```

**Response:**
```json
{
  "url": "https://your-domain.com/static/uuid.pdf",
  "id": 1
}
```

### Get Certificate Info

**GET** `/certificate/{id}`

Retrieve certificate information by ID.

**Response:**
```json
{
  "id": 1,
  "cert_url": "https://your-domain.com/static/uuid.pdf",
  "recipient_name": "John Doe",
  "course_name": "Python Programming",
  "completion_date": "2023-01-15",
  "created_at": "2023-01-15 10:30:00"
}
```

### Get Static File

**GET** `/static/{filename}`

Retrieve a generated PDF file.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## Environment Variables

- `BASE_URL`: The base URL for generated certificate links (default: "https://pycertgen-production.up.railway.app")

## Usage Example

```python
import requests

# Certificate data
data = {
    "html": "<html><body><h1>Certificate of Completion</h1><p>This certifies that John Doe completed the Python Programming course.</p></body></html>",
    "width": 297.0,
    "height": 210.0,
    "certificate_data": {
        "recipient_name": "John Doe",
        "course_name": "Python Programming",
        "completion_date": "2023-01-15"
    }
}

# Generate certificate
response = requests.post("http://localhost:8000/html-to-pdf", json=data)
result = response.json()
print(f"Certificate URL: {result['url']}")
print(f"Certificate ID: {result['id']}")
```