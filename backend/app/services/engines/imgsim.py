"""Near-duplicate photo detection robust to crop, resize and recompression: blurred perceptual hash compared across
a few centre-crop fractions in both directions (blur removes sensor grain / JPEG noise).
# ponytail: pairwise comparison is O(photos); precompute and index hashes if the photo count grows into the thousands."""
import io

import imagehash
from PIL import Image, ImageFilter

CROPS = (0, 0.03, 0.06, 0.09)


def _prep(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("L").filter(ImageFilter.GaussianBlur(3))


def _crops(im: Image.Image):
    w, h = im.size
    for f in CROPS:
        yield im.crop((int(w * f), int(h * f), w - int(w * f), h - int(h * f)))


def photo_distance(a: bytes, b: bytes) -> int:
    """Smallest perceptual-hash Hamming distance (of 64 bits) over crop alignments; unrelated photos score >= ~14."""
    ia, ib = _prep(a), _prep(b)
    ha, hb = imagehash.phash(ia), imagehash.phash(ib)
    return int(min([imagehash.phash(c) - hb for c in _crops(ia)] + [imagehash.phash(c) - ha for c in _crops(ib)]))
