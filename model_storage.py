"""
AURALITH — Model storage & cached inference session.

Downloads BestModel.onnx from Vercel Blob into a temp directory on cold start,
and caches the onnxruntime InferenceSession at module scope so warm containers
reuse it across requests with no reload cost.
"""

import os
import tempfile
import threading
from pathlib import Path

import onnxruntime as ort
import requests

# Use cross-platform temp directory (resolves to /tmp in Vercel/Linux and local Windows Temp dir)
_MODEL_LOCAL_PATH = Path(tempfile.gettempdir()) / "BestModel.onnx"
_session: ort.InferenceSession | None = None
_session_lock = threading.Lock()


def _download_model_if_needed() -> Path:
    if _MODEL_LOCAL_PATH.exists():
        # Ensure the file is not empty or partially downloaded
        if _MODEL_LOCAL_PATH.stat().st_size > 10 * 1024 * 1024:
            return _MODEL_LOCAL_PATH

    model_url = os.environ.get("MODEL_BLOB_URL")
    if not model_url:
        raise RuntimeError(
            "MODEL_BLOB_URL environment variable is not set. "
            "Upload BestModel.onnx to Vercel Blob and set this variable "
            "to the resulting public URL."
        )

    # Ensure parent directories exist
    _MODEL_LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading model from {model_url} to {_MODEL_LOCAL_PATH}...")
    # Stream to disk rather than loading the full 119MB into memory first.
    with requests.get(model_url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        temp_file = _MODEL_LOCAL_PATH.with_suffix(".tmp")
        with open(temp_file, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8 * 1024 * 1024):
                f.write(chunk)
        # Atomically rename to target path on successful download
        temp_file.replace(_MODEL_LOCAL_PATH)

    print("Model downloaded successfully.")
    return _MODEL_LOCAL_PATH


def get_session() -> ort.InferenceSession:
    """
    Returns a cached InferenceSession, creating it on first call within this
    container's lifetime. Thread-safe in case of concurrent first requests
    hitting a freshly-warmed container.
    """
    global _session

    if _session is not None:
        return _session

    with _session_lock:
        # Re-check inside the lock in case another thread won the race.
        if _session is not None:
            return _session

        model_path = _download_model_if_needed()

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        _session = ort.InferenceSession(
            str(model_path),
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )

    return _session
