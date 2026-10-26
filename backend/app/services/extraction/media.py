"""QR decoding and image metadata (EXIF GPS/time/camera/software + perceptual hash)."""
import io
from datetime import datetime

import imagehash
import piexif
from PIL import Image


def decode_qr(png: bytes) -> str | None:
    img = Image.open(io.BytesIO(png)).convert("RGB")
    try:
        from pyzbar.pyzbar import decode  # needs libzbar; falls back to OpenCV when unavailable

        r = decode(img)
        if r:
            return r[0].data.decode()
    except (ImportError, OSError):
        pass
    import cv2
    import numpy as np

    text, _, _ = cv2.QRCodeDetector().detectAndDecode(np.array(img))
    return text or None


def _deg(v, ref) -> float:
    d = v[0][0] / v[0][1] + v[1][0] / v[1][1] / 60 + v[2][0] / v[2][1] / 3600
    return -d if ref in (b"S", b"W") else d


def image_facts(data: bytes) -> dict:
    img = Image.open(io.BytesIO(data))
    out = {"phash": str(imagehash.phash(img.convert("RGB")))}
    try:
        ex = piexif.load(data)
    except Exception:
        return out
    g = ex.get("GPS", {})
    if piexif.GPSIFD.GPSLatitude in g and piexif.GPSIFD.GPSLongitude in g:
        out["gps_lat"] = round(_deg(g[piexif.GPSIFD.GPSLatitude], g.get(piexif.GPSIFD.GPSLatitudeRef)), 6)
        out["gps_lon"] = round(_deg(g[piexif.GPSIFD.GPSLongitude], g.get(piexif.GPSIFD.GPSLongitudeRef)), 6)
    t = ex.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
    if t:
        out["taken_at"] = datetime.strptime(t.decode(), "%Y:%m:%d %H:%M:%S").isoformat()
    z = ex.get("0th", {})
    if piexif.ImageIFD.Model in z:
        out["camera"] = f"{z.get(piexif.ImageIFD.Make, b'').decode()} {z[piexif.ImageIFD.Model].decode()}".strip()
    if piexif.ImageIFD.Software in z:
        out["software"] = z[piexif.ImageIFD.Software].decode()
    return out
