"""
Video generation model interface.

Usage:
    from src.models import get_model, register_model

    model = get_model("kling")
    result = model.generate(prompt="...", image="path/to/image.jpg")
"""
from typing import Dict, Type

from .base import BaseVideoModel
from .text.wan import WanModel
from .text.kling import KlingModel
from .text.seedance import SeedanceModel
from .camera.example_model import PreviewCameraModel
from .action.example_model import PreviewActionModel

MODEL_REGISTRY: Dict[str, Type[BaseVideoModel]] = {
    "wan": WanModel,
    "kling": KlingModel,
    "seedance": SeedanceModel,
    "camera_preview": PreviewCameraModel,
    "action_preview": PreviewActionModel,
}


def register_model(name: str, cls: Type[BaseVideoModel]):
    """Register a new model class."""
    MODEL_REGISTRY[name.lower()] = cls


_model_cache: Dict[str, BaseVideoModel] = {}


def get_model(name: str, **kwargs) -> BaseVideoModel:
    """Get a model instance (singleton per name)."""
    name = name.lower()
    if name not in MODEL_REGISTRY:
        available = ", ".join(sorted(MODEL_REGISTRY.keys()))
        raise ValueError(f"Unknown model: {name}. Available: {available}")
    if name not in _model_cache:
        _model_cache[name] = MODEL_REGISTRY[name](**kwargs)
    return _model_cache[name]


def list_models() -> list:
    """List all registered model names."""
    return sorted(MODEL_REGISTRY.keys())


__all__ = ["BaseVideoModel", "get_model", "register_model", "list_models"]
