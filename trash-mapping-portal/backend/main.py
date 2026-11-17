import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from photo_analyzer import analyze_photo
from google_storage import save_submission, get_map_rows, RAW_TAB, PROCESSED_TAB

load_dotenv()

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "15")) * 1024 * 1024
MAX_BATCH_FILES = int(os.getenv("MAX_BATCH_FILES", "20"))
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/tiff", "image/webp"}

limiter = Limiter(key_func=get_remote_address, default_limits=["60/hour"])
app = FastAPI(title="Trash & Damage Mapping API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Trash & Damage Mapping API"}


@app.post("/api/upload")
@limiter.limit("20/hour")
async def upload_photo(request: Request, file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image type. Please upload a supported image file.")

    image_bytes = await file.read(MAX_FILE_SIZE + 1)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"Each photo must be {MAX_FILE_SIZE // (1024 * 1024)} MB or smaller.")

    try:
        metadata = analyze_photo(image_bytes)
    except Exception:
        raise HTTPException(status_code=400, detail="The file could not be read as a valid image.")

    try:
        stored = save_submission(
            image_bytes=image_bytes,
            filename=file.filename or "photo",
            mime_type=file.content_type,
            metadata=metadata
        )
    except Exception as exc:
        # Avoid returning credentials or internal stack traces to public clients.
        print(f"Storage error: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=503, detail="The photo was analyzed but could not be saved. Please try again later.")

    return {
        "filename": file.filename or "photo",
        "has_gps": metadata["latitude"] is not None and metadata["longitude"] is not None,
        **metadata,
        **stored,
    }


@app.get("/api/reports/raw")
@limiter.limit("60/minute")
def raw_reports(request: Request):
    try:
        return {"reports": get_map_rows(RAW_TAB)}
    except Exception as exc:
        print(f"Raw map read error: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=503, detail="Could not retrieve raw reports.")


@app.get("/api/reports/processed")
@limiter.limit("60/minute")
def processed_reports(request: Request):
    try:
        return {"reports": get_map_rows(PROCESSED_TAB)}
    except Exception as exc:
        print(f"Processed map read error: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=503, detail="Could not retrieve processed reports.")
