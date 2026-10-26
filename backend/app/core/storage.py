"""Object storage: local disk by default, MinIO when STORAGE=minio. Optional Fernet encryption at rest."""
from pathlib import Path

from app.core.config import settings


def _fernet():
    if not settings.file_encryption_key:
        return None
    from cryptography.fernet import Fernet

    return Fernet(settings.file_encryption_key.encode())


def _minio():
    from minio import Minio  # only needed when STORAGE=minio

    c = Minio(settings.minio_endpoint, settings.minio_access_key, settings.minio_secret_key, secure=False)
    if not c.bucket_exists("pramaan"):
        c.make_bucket("pramaan")
    return c


def put(key: str, data: bytes) -> None:
    f = _fernet()
    data = f.encrypt(data) if f else data
    if settings.storage == "minio":
        import io

        _minio().put_object("pramaan", key, io.BytesIO(data), len(data))
        return
    p = Path(settings.storage_dir) / key
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def get(key: str) -> bytes:
    if settings.storage == "minio":
        r = _minio().get_object("pramaan", key)
        data = r.read()
        r.close()
    else:
        data = (Path(settings.storage_dir) / key).read_bytes()
    f = _fernet()
    return f.decrypt(data) if f else data
