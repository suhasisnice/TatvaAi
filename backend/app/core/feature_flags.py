from app.core.config import settings


def enabled(name: str) -> bool:
    return bool(getattr(settings, f"feature_{name.lower()}", False))
