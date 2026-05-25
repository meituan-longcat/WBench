"""
Generic API client for text-conditioned video generation.

Supports async submit → poll → download pattern used by most video APIs.
"""
import base64
import logging
import os
import time
from typing import Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)


class APIVideoClient:
    """
    Generic video generation API client.

    Subclass and override _submit / _poll / _parse_result for specific APIs.
    Or use directly with a compatible OpenAI-style endpoint.
    """

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        headers: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
        timeout: int = 600,
        poll_interval: int = 10,
    ):
        self.base_url = base_url or os.environ.get("VIDEO_API_URL", "")
        self.api_key = api_key or os.environ.get("VIDEO_API_KEY", "")
        self.timeout = timeout
        self.poll_interval = poll_interval

        self.session = requests.Session()
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

        self.headers = headers or {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def encode_image(image_path: str) -> str:
        """Encode local image to base64 string."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def generate(
        self,
        model_name: str,
        prompt: str,
        image: Optional[str] = None,
        duration: float = 5.0,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Submit a generation task, poll for result, download video.

        Args:
            model_name: API model identifier
            prompt: Text prompt
            image: Path to conditioning image (for I2V)
            duration: Video duration in seconds

        Returns:
            {"code": 0, "video_path": "..."} or {"code": -1, "error": "..."}
        """
        # Submit task
        task_id = self._submit(model_name, prompt, image, duration, **kwargs)
        if not task_id:
            return {"code": -1, "error": "Task submission failed"}

        # Poll for completion
        video_url = self._poll(task_id)
        if not video_url:
            return {"code": -1, "error": f"Generation failed or timed out: {task_id}"}

        # Download
        cache_dir = os.path.join("video_cache", model_name.replace("/", "_"))
        os.makedirs(cache_dir, exist_ok=True)
        output_path = os.path.join(cache_dir, f"{task_id}.mp4")
        if self._download(video_url, output_path):
            return {"code": 0, "video_path": output_path}
        return {"code": -1, "error": f"Download failed: {video_url}"}

    def _submit(self, model_name: str, prompt: str, image: Optional[str],
                duration: float, **kwargs) -> Optional[str]:
        """Submit generation task. Override for custom APIs."""
        payload = {
            "model": model_name,
            "prompt": prompt,
            "duration": duration,
        }
        if image and os.path.exists(image):
            payload["image"] = self.encode_image(image)
        payload.update(kwargs)

        try:
            resp = self.session.post(
                f"{self.base_url}/v1/video/generate",
                headers=self.headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            task_id = data.get("task_id") or data.get("id") or data.get("data", {}).get("task_id")
            if task_id:
                logger.info(f"Task submitted: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"Submit failed: {e}")
            return None

    def _poll(self, task_id: str) -> Optional[str]:
        """Poll task status until complete. Returns video URL."""
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            try:
                resp = self.session.get(
                    f"{self.base_url}/v1/video/status/{task_id}",
                    headers=self.headers,
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()

                status = data.get("status", "")
                if status in ("succeed", "completed", "done"):
                    return data.get("video_url") or data.get("url") or data.get("result", {}).get("url")
                elif status in ("failed", "error"):
                    logger.error(f"Task failed: {task_id}: {data.get('error', '')}")
                    return None

                time.sleep(self.poll_interval)
            except Exception as e:
                logger.warning(f"Poll error: {e}")
                time.sleep(self.poll_interval)

        logger.error(f"Task timed out: {task_id}")
        return None

    def _download(self, url: str, output_path: str) -> bool:
        """Download video from URL."""
        try:
            resp = self.session.get(url, stream=True, timeout=120)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
