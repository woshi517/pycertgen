from fastapi import FastAPI, Body
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uuid
import os
import imgkit
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Thread pool untuk blocking operations
executor = ThreadPoolExecutor(max_workers=2)


class HtmlRequest(BaseModel):
    html: str
    viewport_width: int
    viewport_height: int


def generate_image_blocking(html: str, filepath: str, width: int, height: int):
    """Blocking image generation function"""
    logger.info(f"Starting image generation for {filepath}")

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

    logger.info(f"Image generation completed for {filepath}")


@app.post("/html-to-image")
async def html_to_image(req: HtmlRequest):
    try:
        filename = f"{uuid.uuid4()}.png"
        filepath = f"static/{filename}"

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
        return JSONResponse({"url": f"http://localhost:8000/static/{filename}"})

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/static/{filename}")
async def get_image(filename: str):
    file_path = os.path.join("static", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="image/png")
    return JSONResponse({"error": "File not found"}, status_code=404)

@app.get("/")
async def root():
    return {"message": "Welcome to the HTML to Image API"}