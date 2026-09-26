import io
import os
import tempfile
import cv2
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check():
    """Verify health check returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"


def test_invalid_file_type():
    """Verify upload failure on unsupported format."""
    fake_file = io.BytesIO(b"dummy plain text content")
    response = client.post(
        "/api/detect/image",
        files={"file": ("test.txt", fake_file, "text/plain")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "Invalid image format" in data.get("detail", "")


def test_valid_image_upload():
    """Verify detection pipeline on a mock valid image."""
    img_byte_arr = io.BytesIO()
    image = Image.new("RGB", (100, 100), color="red")
    image.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)

    response = client.post(
        "/api/detect/image",
        files={"file": ("test.jpg", img_byte_arr, "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "image_url" in data
    assert "detections" in data


def test_valid_video_upload():
    """Verify detection pipeline on a mock valid video."""
    # Generate 3 frames in a temporary MP4 file
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_vid:
        temp_path = temp_vid.name

    out = cv2.VideoWriter(
        temp_path, cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (100, 100)
    )
    for _ in range(3):
        out.write(np.zeros((100, 100, 3), dtype=np.uint8))
    out.release()

    try:
        with open(temp_path, "rb") as f:
            video_bytes = f.read()

        response = client.post(
            "/api/detect/video",
            files={"file": ("test.mp4", io.BytesIO(video_bytes), "video/mp4")},
        )

        assert response.status_code == 200
        res_data = response.json()
        assert "video_url" in res_data
        assert "total_frames" in res_data
        assert res_data["total_frames"] == 3

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)