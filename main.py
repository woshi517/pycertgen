from fastapi import FastAPI, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import os
import imgkit
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import time
from datetime import datetime, timedelta

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
    html: str
    viewport_width: int
    viewport_height: int


def generate_image_blocking(html: str, filepath: str, width: int, height: int):
    """Blocking image generation function"""
    logger.info(f"Starting image generation for {filepath}")

    try:
        imgkit.from_string(
            html,
            filepath,
            options={
                "crop-w": str(width),
                "crop-h": str(height),
                "crop-x": "0",
                "crop-y": "0",
            },
        )
    except Exception as e:
        logger.error(f"Failed to generate image: {str(e)}")
        raise

    logger.info(f"Image generation completed for {filepath}")


@app.post("/html-to-image")
async def html_to_image(req: HtmlRequest):
    # Run cleanup before generating new image
    cleanup_old_files()
    
    filename = f"{uuid.uuid4()}.png"
    filepath = f"static/{filename}"
    
    try:
        logger.info(f"Received request, generating {filename}")

        # Jalankan imgkit di thread terpisah
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
        return JSONResponse({"error": f"Failed to generate image: {str(e)}"}, status_code=500)


@app.get("/static/{filename}")
async def get_image(filename: str):
    file_path = os.path.join("static", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="image/png")
    return JSONResponse({"error": "File not found"}, status_code=404)

@app.get("/")
async def root():
    return {"message": "Welcome to the HTML to Image API"}