from fastapi import FastAPI, Body, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator, Field
from typing import Optional
import uuid
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import time
from datetime import datetime, timedelta
from weasyprint import HTML, CSS
import hashlib
import sqlite3

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Database setup
def get_db_connection():
    conn = sqlite3.connect('certificates.db')
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://asbisindo.vocasia.id",  # Production domain
        "http://asbisindo.vocasia.id",   # Production domain (HTTP)
        "http://localhost:8000",         # Local development
        "http://127.0.0.1:8000",         # Alternative localhost
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Thread pool untuk blocking operations
executor = ThreadPoolExecutor(max_workers=2)

# Ensure static directory exists
os.makedirs("static", exist_ok=True)

# Template cache for compiled templates - removed since HTML objects aren't serializable
# template_cache = {}

# Cleanup old files (older than 1 hour)
def cleanup_old_files():
    try:
        current_time = time.time()
        for filename in os.listdir("static"):
            filepath = os.path.join("static", filename)
            # Skip .gitignore file
            if filename == ".gitignore":
                continue
            # Check if file is older than 1 hour
            if os.path.isfile(filepath) and (current_time - os.path.getmtime(filepath)) > 3600:
                os.remove(filepath)
                logger.info(f"Cleaned up old file: {filename}")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

class CertificateData(BaseModel):
    recipient_name: str
    course_name: str
    completion_date: str

class HtmlRequest(BaseModel):
    html: str = Field(..., max_length=1000000)  # Limit to 1MB
    width: float = Field(297.0, gt=0)  # Width in mm, default A4 landscape width
    height: float = Field(210.0, gt=0)  # Height in mm, default A4 landscape height
    viewport_width: Optional[float] = None  # PHP sends this field
    viewport_height: Optional[float] = None  # PHP sends this field
    certificate_data: Optional[CertificateData] = None

    @validator('html')
    def html_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('HTML content cannot be empty')
        return v

# PNG generation is not supported in this version of WeasyPrint
# Only PDF generation is available

def generate_pdf_blocking(html: str, filepath: str, width: float = 297.0, height: float = 210.0):
    """Blocking PDF generation function using WeasyPrint"""
    logger.info(f"Starting PDF generation for {filepath} with dimensions {width}mm x {height}mm")

    try:
        # Create CSS for page size
        css = CSS(string=f"""
            @page {{
                size: {width}mm {height}mm;
                margin: 0;
            }}
            body {{
                margin: 0;
                padding: 0;
            }}
        """)
        
        # Create HTML document and write directly to PDF with custom size
        html_doc = HTML(string=html)
        html_doc.write_pdf(filepath, stylesheets=[css])
        
        logger.info(f"PDF generation completed for {filepath}")
    except Exception as e:
        logger.error(f"Failed to generate PDF: {str(e)}")
        raise

# PNG generation is not supported in this version of WeasyPrint
# Only PDF generation is available

@app.post("/html-to-pdf")
async def html_to_pdf(req: HtmlRequest):
    # Run cleanup before generating new PDF
    #cleanup_old_files()
    
    filename = f"{uuid.uuid4()}.pdf"
    filepath = f"static/{filename}"
    
    # Insert record into database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Extract certificate data if provided
    recipient_name = ""
    course_name = ""
    completion_date = ""
    
    if req.certificate_data:
        recipient_name = req.certificate_data.recipient_name
        course_name = req.certificate_data.course_name
        completion_date = req.certificate_data.completion_date
    
    cursor.execute(
        "INSERT INTO certificates (cert_url, recipient_name, course_name, completion_date) VALUES (NULL, ?, ?, ?)",
        (recipient_name, course_name, completion_date)
    )
    cert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Use viewport_width/viewport_height if provided (from PHP), otherwise use width/height
    width = req.viewport_width if req.viewport_width is not None else req.width
    height = req.viewport_height if req.viewport_height is not None else req.height
    
    try:
        logger.info(f"Received request, generating {filename}")

        # Run WeasyPrint in thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            executor,
            generate_pdf_blocking,
            req.html,
            filepath,
            width,
            height,
        )

        logger.info(f"Returning response for {filename}")
        # Use environment variable for base URL, fallback to default
        base_url = os.getenv("BASE_URL", "https://pycertgen-production.up.railway.app")
        cert_url = f"{base_url}/static/{filename}"
        
        # Update database record with the certificate URL
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE certificates SET cert_url = ? WHERE id = ?", (cert_url, cert_id))
        conn.commit()
        conn.close()
        
        return JSONResponse({"url": cert_url, "id": cert_id})

    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

@app.get("/static/{filename}")
async def get_file(filename: str):
    file_path = os.path.join("static", filename)
    if os.path.exists(file_path):
        media_type = "application/pdf" if filename.endswith(".pdf") else "image/png"
        return FileResponse(file_path, media_type=media_type)
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/certificate/{cert_id}")
async def get_certificate(cert_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM certificates WHERE id = ?", (cert_id,))
    cert = cursor.fetchone()
    conn.close()
    
    if cert is None:
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    return {
        "id": cert["id"],
        "cert_url": cert["cert_url"],
        "recipient_name": cert["recipient_name"],
        "course_name": cert["course_name"],
        "completion_date": cert["completion_date"],
        "created_at": cert["created_at"]
    }

@app.get("/")
async def root():
    return {"message": "Welcome to the HTML to PDF API"}