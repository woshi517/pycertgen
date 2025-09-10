from fastapi import FastAPI, Body, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator, Field
import uuid
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import time
from datetime import datetime, timedelta
from weasyprint import HTML, CSS
import hashlib

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

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

# Template cache for compiled templates
template_cache = {}

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

class HtmlRequest(BaseModel):
    html: str = Field(..., max_length=100000)  # Limit to 100KB
    viewport_width: int = Field(..., ge=1, le=5000)  # Between 1 and 5000
    viewport_height: int = Field(..., ge=1, le=5000)  # Between 1 and 5000

    @validator('html')
    def html_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('HTML content cannot be empty')
        return v

def generate_image_blocking(html: str, filepath: str, width: int, height: int):
    """Blocking image generation function using WeasyPrint"""
    logger.info(f"Starting image generation for {filepath}")

    try:
        # Create CSS for viewport sizing
        css = CSS(string=f'''
            @page {{
                size: {width}px {height}px;
                margin: 0;
            }}
            body {{
                margin: 0;
                padding: 0;
            }}
        ''')

        # Use template caching
        html_hash = hashlib.md5(html.encode()).hexdigest()
        if html_hash in template_cache:
            document = template_cache[html_hash]
        else:
            document = HTML(string=html)
            template_cache[html_hash] = document
            
        # Generate PNG directly
        document.write_png(filepath, stylesheets=[css])
        
        logger.info(f"Image generation completed for {filepath}")
    except Exception as e:
        logger.error(f"Failed to generate image: {str(e)}")
        raise

def generate_pdf_blocking(html: str, filepath: str, width: int, height: int):
    """Blocking PDF generation function using WeasyPrint"""
    logger.info(f"Starting PDF generation for {filepath}")

    try:
        # Create CSS for page sizing
        css = CSS(string=f'''
            @page {{
                size: {width}px {height}px;
                margin: 0;
            }}
            body {{
                margin: 0;
                padding: 0;
            }}
        ''')

        # Use template caching
        html_hash = hashlib.md5(html.encode()).hexdigest()
        if html_hash in template_cache:
            document = template_cache[html_hash]
        else:
            document = HTML(string=html)
            template_cache[html_hash] = document
            
        # Generate PDF directly
        document.write_pdf(filepath, stylesheets=[css])
        
        logger.info(f"PDF generation completed for {filepath}")
    except Exception as e:
        logger.error(f"Failed to generate PDF: {str(e)}")
        raise

@app.post("/html-to-image")
async def html_to_image(req: HtmlRequest):
    # Run cleanup before generating new image
    cleanup_old_files()
    
    filename = f"{uuid.uuid4()}.png"
    filepath = f"static/{filename}"
    
    try:
        logger.info(f"Received request, generating {filename}")

        # Run WeasyPrint in thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            executor,
            generate_image_blocking,
            req.html,
            filepath,
            req.viewport_width,
            req.viewport_height,
        )

        logger.info(f"Returning response for {filename}")
        # Use environment variable for base URL, fallback to default
        base_url = os.getenv("BASE_URL", "https://pycertgen-production.up.railway.app")
        return JSONResponse({"url": f"{base_url}/static/{filename}"})

    except Exception as e:
        logger.error(f"Error generating image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate image: {str(e)}")

@app.post("/html-to-pdf")
async def html_to_pdf(req: HtmlRequest):
    # Run cleanup before generating new PDF
    cleanup_old_files()
    
    filename = f"{uuid.uuid4()}.pdf"
    filepath = f"static/{filename}"
    
    try:
        logger.info(f"Received request, generating {filename}")

        # Run WeasyPrint in thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            executor,
            generate_pdf_blocking,
            req.html,
            filepath,
            req.viewport_width,
            req.viewport_height,
        )

        logger.info(f"Returning response for {filename}")
        # Use environment variable for base URL, fallback to default
        base_url = os.getenv("BASE_URL", "https://pycertgen-production.up.railway.app")
        return JSONResponse({"url": f"{base_url}/static/{filename}"})

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

@app.get("/")
async def root():
    return {"message": "Welcome to the HTML to Image/PDF API"}