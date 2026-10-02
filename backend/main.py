import os
import shutil
import subprocess
import time
import uuid
import cv2
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import Response
from ultralytics import YOLO
from logger import log_request_info

app = FastAPI(title="YOLO Object Detection API")

# Allow request from frontend public domain
allowed_origins = ["http://localhost:5173"] # Default for local development

frontend_url = os.getenv("FRONTEND_URL")
if frontend_url and frontend_url.strip():
    allowed_origins.append(frontend_url.strip)

# Absolute base directory setup
BASE_DIR = os.path.dirname(os.path.realpath(__file__))

# Configure CORS for React frontend (default: http://localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static directory for serving output images/videos (Absolute Path)
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Hardware acceleration setup
DEVICE = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
print(f"Using device: {DEVICE}")

# Load YOLO model once at startup
MODEL_PATH = os.path.join(BASE_DIR, "yolov8n.pt")
MODEL = YOLO(MODEL_PATH)  # Nano model for speed and lightweight execution
MODEL.to(DEVICE)

ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/jpg"]
ALLOWED_VIDEO_TYPES = ["video/mp4"]
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit

model_loaded = True  # True if YOLO model is successfully loaded

@app.get("/ready")
def readiness_check():
    if model_loaded:
        return {"status": "ready"}
    raise HTTPException(status_code=503, detail="Model not loaded yet")

# Global exception handler for unexpected errors
@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    
    # Log thông tin request
    log_request_info(
        request_id=request_id,
        route=request.url.path,
        method=request.method,
        status_code=response.status_code,
        latency=process_time
    )
    return response

# Ignore the favicon.ico requests in logs
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/health")
def health_check():
    """Health check endpoint for containerization and monitoring."""
    return {"status": "ok", "device": DEVICE}


@app.post("/api/detect/image")
async def detect_image(file: UploadFile = File(...), conf_threshold: float = 0.25):
    """Image detection endpoint."""
    # File type validation
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format. Only JPG, JPEG, and PNG are allowed.",
        )

    # File size validation
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds the 10MB limit.",
        )

    temp_path = os.path.join(BASE_DIR, f"temp_{uuid.uuid4().hex}.jpg")
    try:
        with open(temp_path, "wb") as f:
            f.write(contents)

        start_time = time.time()
        results = MODEL.predict(source=temp_path, conf=conf_threshold, device=DEVICE)
        processing_time = round(time.time() - start_time, 3)

        result = results[0]
        boxes = result.boxes

        # Build detection metadata
        detections = []
        for box in boxes:
            cls_id = int(box.cls[0])
            name = MODEL.names[cls_id]
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()  # [xmin, ymin, xmax, ymax]
            detections.append(
                {"class": name, "confidence": round(conf, 3), "bbox": xyxy}
            )

        # Save annotated image
        output_filename = f"detected_{uuid.uuid4().hex}.jpg"
        output_path = os.path.join(UPLOAD_DIR, output_filename)
        annotated_img = result.plot()
        cv2.imwrite(output_path, annotated_img)

        return {
            "count": len(detections),
            "processing_time_sec": processing_time,
            "image_url": f"/static/outputs/{output_filename}",
            "detections": detections,
        }

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/api/detect/video")
async def detect_video(file: UploadFile = File(...), conf_threshold: float = 0.25):
    """Short video detection endpoint."""
    # File type validation
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video format. Only MP4 videos are allowed.",
        )

    # File size validation
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds the 10MB limit.",
        )

    temp_path = os.path.join(BASE_DIR, f"temp_{uuid.uuid4().hex}.mp4")
    with open(temp_path, "wb") as f:
        f.write(contents)

    raw_output_path = os.path.join(BASE_DIR, f"raw_{uuid.uuid4().hex}.mp4")
    try:
        start_time = time.time()
        cap = cv2.VideoCapture(temp_path)

        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Prepare intermediate output video writer  
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(raw_output_path, fourcc, fps, (width, height))

        class_counts = {}
        total_frames = 0
        
        # Frame skipping setup (processes every 2nd frame)
        frame_skip = 2
        last_annotated_frame = None

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            total_frames += 1

            if total_frames % frame_skip == 1 or last_annotated_frame is None:
                # Enhancement A: Explicit hardware acceleration parameter
                results = MODEL.predict(source=frame, conf=conf_threshold, device=DEVICE, verbose=False)
                last_annotated_frame = results[0].plot()

                for box in results[0].boxes:
                    name = MODEL.names[int(box.cls[0])]
                    class_counts[name] = class_counts.get(name, 0) + 1

            out.write(last_annotated_frame)

        cap.release()
        out.release()

        # Re-encode video using ffmpeg for direct web streaming
        output_filename = f"detected_{uuid.uuid4().hex}.mp4"
        output_path = os.path.join(UPLOAD_DIR, output_filename)

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", raw_output_path,
            "-vcodec", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path
        ]
        subprocess.run(ffmpeg_cmd, check=True)

        processing_time = round(time.time() - start_time, 3)

        return {
            "total_frames": total_frames,
            "processing_time_sec": processing_time,
            "video_url": f"/static/outputs/{output_filename}",
            "summary_counts": class_counts,
        }

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if os.path.exists(raw_output_path):
            os.remove(raw_output_path)