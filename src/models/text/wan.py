"""
Wan 2.7 video generation model (text-conditioned, I2V).

Usage:
    from src.models.text import WanModel
    model = WanModel()
    result = model.generate(prompt="...", image="path/to/image.jpg")
"""
import os
from typing import Optional, Dict, Any

from ..base import BaseVideoModel
from .api_client import APIVideoClient
from .prompt_builder import build_turn_prompt


class WanModel(BaseVideoModel):
    """Wan 2.7 I2V model via API."""

    def __init__(self, api_url: str = "", api_key: str = ""):
        super().__init__(model_name="wan")
        self._client = APIVideoClient(
            base_url=api_url or os.environ.get("VIDEO_API_URL", ""),
            api_key=api_key or os.environ.get("VIDEO_API_KEY", ""),
        )

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": "wan2.7-i2v",
            "api_url": self._client.base_url,
            "class": "WanModel",
        }

    def generate(
        self,
        prompt: str,
        image: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        model_name = "wan2.7-i2v" if image else "wan2.7-t2v"
        return self._client.generate(
            model_name=model_name,
            prompt=prompt,
            image=image,
            duration=kwargs.get("duration", 5.0),
        )

    def _build_turn_prompt(self, case: Dict[str, Any], interaction: Dict[str, Any]) -> str:
        perspective = case.get("settings", {}).get("perspective", "first_person")
        return build_turn_prompt(case, interaction, perspective=perspective)
