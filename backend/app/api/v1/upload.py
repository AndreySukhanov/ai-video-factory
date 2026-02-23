"""
API for uploading images for episode generation
"""
import os
import io
import uuid
import shutil
import httpx
from PIL import Image
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from app.core.security import resolve_upload_file_path

router = APIRouter()

# Configure upload directory
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Allowed image extensions
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_IMAGE_DIMENSION = 1280  # Max dimension for compression
CATBOX_API_URL = "https://catbox.moe/user/api.php"


async def upload_to_catbox(content: bytes, filename: str) -> str:
    """Upload image to catbox.moe for external access by Replicate"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"fileToUpload": (filename, content)}
            data = {"reqtype": "fileupload"}
            response = await client.post(CATBOX_API_URL, files=files, data=data)
            if response.status_code == 200 and response.text.startswith("https://"):
                return response.text.strip()
    except Exception as e:
        print(f"[UPLOAD] Catbox upload failed: {e}")
    return None


def compress_image(content: bytes, max_size: int = MAX_IMAGE_DIMENSION) -> bytes:
    """Compress and resize image for faster upload"""
    try:
        img = Image.open(io.BytesIO(content))

        # Resize if too large
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # Convert to RGB if needed (remove alpha)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')

        # Save as JPEG with compression
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        return output.getvalue()
    except Exception as e:
        print(f"[UPLOAD] Compression failed: {e}")
        return content


@router.post("/image")
async def upload_image(file: UploadFile = File(...)):
    """
    Upload an image file for use as a reference in video generation.
    
    Returns:
        JSON with the URL of the uploaded image
    """
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)} MB"
        )
    
    # Generate unique filename
    unique_id = uuid.uuid4().hex[:12]
    filename = f"{unique_id}{file_ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    # Compress image for faster upload
    compressed_content = compress_image(content)
    compressed_filename = f"{unique_id}.jpg"  # Always save as JPEG after compression
    compressed_filepath = os.path.join(UPLOAD_DIR, compressed_filename)

    # Save compressed file locally
    try:
        with open(compressed_filepath, "wb") as f:
            f.write(compressed_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # Upload to catbox for external access (Replicate needs public URL)
    external_url = await upload_to_catbox(compressed_content, compressed_filename)

    # Return URLs
    local_url = f"/uploads/{compressed_filename}"

    return JSONResponse({
        "success": True,
        "filename": compressed_filename,
        "url": external_url or local_url,  # Prefer catbox URL for Replicate
        "local_url": local_url,
        "external_url": external_url,
        "size": len(compressed_content),
        "original_size": len(content)
    })


@router.delete("/image/{filename}")
async def delete_image(filename: str):
    """Delete an uploaded image"""
    try:
        filepath = resolve_upload_file_path(UPLOAD_DIR, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        os.remove(filepath)
        return {"success": True, "message": "File deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
