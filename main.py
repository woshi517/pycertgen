from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator, Field
from typing import Optional
import uuid
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from weasyprint import HTML, CSS

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
        "http://localhost:3000",         # Laravel development
        "http://127.0.0.1:3000",         # Alternative localhost
        "http://localhost:8000",         # FastAPI development
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

class HtmlRequest(BaseModel):
    html: str = Field(..., max_length=1000000)  # Limit to 1MB
    width: float = Field(..., gt=0, le=2000)  # Width in mm, required field
    height: float = Field(..., gt=0, le=2000)  # Height in mm, required field
    viewport_width: Optional[float] = Field(None, gt=0, le=2000)  # PHP sends this field
    viewport_height: Optional[float] = Field(None, gt=0, le=2000)  # PHP sends this field

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
    filename = f"{uuid.uuid4()}.pdf"
    filepath = f"static/{filename}"
    
    # Use viewport dimensions if provided (from PHP), otherwise use width/height from request
    # This ensures document size is always based on request data, with viewport taking precedence when available
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
        
        return JSONResponse({"url": cert_url})

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
    return {"message": "Welcome to the HTML to PDF API"}