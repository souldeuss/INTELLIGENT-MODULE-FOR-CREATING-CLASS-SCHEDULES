"""Model version registry helpers for saved DRL checkpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

_REGISTRY_FILENAME = "active_model.json"
_DEFAULT_MODEL = "actor_critic_best.pt"


def _normalize_model_name(model_name: str) -> str:
    if not model_name:
        raise ValueError("model_name must not be empty")
    return model_name if model_name.endswith(".pt") else f"{model_name}.pt"


def get_registry_path(model_dir: Path) -> Path:
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir / _REGISTRY_FILENAME


def get_active_model_name(model_dir: Path) -> str:
    """Return active model filename or fallback to default best alias."""
    registry_path = get_registry_path(model_dir)
    if not registry_path.exists():
        return _DEFAULT_MODEL

    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _DEFAULT_MODEL

    active_model = payload.get("active_model")
    if not isinstance(active_model, str) or not active_model:
        return _DEFAULT_MODEL

    return _normalize_model_name(active_model)


def set_active_model_name(model_dir: Path, model_name: str) -> Dict[str, str]:
    """Persist active model filename in registry."""
    normalized_name = _normalize_model_name(model_name)
    model_path = model_dir / normalized_name
    if not model_path.exists():
        raise FileNotFoundError(f"Model file does not exist: {model_path}")

    payload = {"active_model": normalized_name}
    registry_path = get_registry_path(model_dir)
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return payload


def list_model_versions(model_dir: Path) -> List[Dict[str, object]]:
    """List available model artifacts with active flag."""
    model_dir.mkdir(parents=True, exist_ok=True)
    active_name = get_active_model_name(model_dir)

    versions: List[Dict[str, object]] = []
    for model_path in sorted(model_dir.glob("actor_critic_*.pt"), key=lambda p: p.stat().st_mtime, reverse=True):
        versions.append(
            {
                "name": model_path.name,
                "is_active": model_path.name == active_name,
                "size_bytes": model_path.stat().st_size,
                "updated_at": model_path.stat().st_mtime,
            }
        )

    return versions
