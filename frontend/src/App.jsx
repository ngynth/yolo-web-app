import React, { useState } from 'react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export default function App() {
  const [file, setFile] = useState(null);
  const [mediaType, setMediaType] = useState('image');
  const [confThreshold, setConfThreshold] = useState(0.25);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setResult(null);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file to upload.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    const endpoint = mediaType === 'image' 
      ? `${API_BASE}/api/detect/image?conf_threshold=${confThreshold}`
      : `${API_BASE}/api/detect/video?conf_threshold=${confThreshold}`;

    try {
      const response = await axios.post(endpoint, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || "An unexpected error occurred during detection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: "800px", margin: "0 auto", padding: "20px", fontFamily: "sans-serif" }}>
      <h1>YOLO Object Detection Web App</h1>

      {/* Fixed Media Type Form Field */}
      <div style={{ marginBottom: "15px" }}>
        <label htmlFor="media-type-select">Media Type: </label>
        <select 
          id="media-type-select"
          name="mediaType"
          value={mediaType} 
          onChange={(e) => setMediaType(e.target.value)}
        >
          <option value="image">Image (JPG, PNG)</option>
          <option value="video">Short Video (MP4)</option>
        </select>
      </div>

      {/* Fixed Confidence Threshold Form Field */}
      <div style={{ marginBottom: "15px" }}>
        <label htmlFor="conf-threshold-input">Confidence Threshold: {confThreshold}</label>
        <input 
          id="conf-threshold-input"
          name="confThreshold"
          type="range" 
          min="0.1" 
          max="0.9" 
          step="0.05" 
          value={confThreshold} 
          onChange={(e) => setConfThreshold(parseFloat(e.target.value))}
        />
      </div>

      {/* Fixed File Upload Input */}
      <div style={{ marginBottom: "15px" }}>
        <label htmlFor="file-upload-input" style={{ display: 'none' }}>Upload File</label>
        <input 
          id="file-upload-input"
          name="fileUpload"
          type="file" 
          accept={mediaType === 'image' ? 'image/*' : 'video/*'} 
          onChange={handleFileChange} 
        />
        <button onClick={handleUpload} disabled={loading || !file}>
          {loading ? "Processing..." : "Detect Objects"}
        </button>
      </div>

      {error && <div style={{ color: "red", padding: "10px", border: "1px solid red", borderRadius: "4px" }}>{error}</div>}

      {result && (
        <div style={{ marginTop: "20px" }}>
          <h2>Detection Results</h2>
          <p>Processing Time: {result.processing_time_sec} seconds</p>
          
          {mediaType === 'image' ? (
            <div>
              <p>Detected Objects Count: {result.count}</p>
              <img src={`${API_BASE}${result.image_url}`} alt="Annotated Detection" style={{ maxWidth: "100%", borderRadius: "8px" }} />
            </div>
          ) : (
            <div>
              <p>Total Processed Frames: {result.total_frames}</p>
              <video controls width="100%" src={`${API_BASE}${result.video_url}`} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
