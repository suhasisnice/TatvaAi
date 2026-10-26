"""Generates the synthetic demo documents (PDFs, photos, faculty CSV) for the
three demo institutions. Lazy-but-real: plain reportlab text PDFs with
"Label: Value" lines our own extractor reads back, plus a 'Digitally Signed
By:' marker standing in for a real DSC (see DECISIONS: a full PKI/pyHanko
signing pipeline was dropped to keep the demo buildable in one session --
the integrity property it demonstrates, "any change after signing is
detectable", is preserved via SHA-256 comparison with the issuer's
registered hash instead).
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "synthetic"


def make_pdf(path: Path, lines: list[str], footer: str = "SYNTHETIC DOCUMENT FOR DEMO. Not a real certificate."):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=(612, 792))
    y = 740
    c.setFont("Helvetica-Bold", 14)
    c.drawString(60, y, lines[0])
    y -= 30
    c.setFont("Helvetica", 11)
    for line in lines[1:]:
        c.drawString(60, y, line)
        y -= 20
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(60, 40, footer)
    c.save()


def make_photo(path: Path, color: tuple[int, int, int], label: str, seed: int = 0):
    """A deliberately distinctive synthetic photo (random shapes seeded per
    institution) so unrelated photos don't collide on perceptual hash --
    only a genuinely reused/cropped file should trigger DUPLICATE_PHOTO."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    img = Image.new("RGB", (640, 480), color)
    d = ImageDraw.Draw(img)
    for _ in range(25):
        x0, y0 = rng.randint(0, 600), rng.randint(0, 440)
        x1, y1 = x0 + rng.randint(10, 80), y0 + rng.randint(10, 80)
        shade = tuple(min(255, max(0, c + rng.randint(-60, 60))) for c in color)
        d.rectangle([x0, y0, x1, y1], fill=shade)
    d.rectangle([40, 40, 600, 440], outline=(255, 255, 255), width=6)
    d.text((60, 60), label, fill=(255, 255, 255))
    img.save(path, "JPEG", quality=85)


def make_duplicate_photo(src: Path, dst: Path):
    """Crop + recompress src to simulate a reused photo (real perceptual hash match)."""
    with Image.open(src) as img:
        w, h = img.size
        cropped = img.crop((10, 10, w - 10, h - 10)).resize((640, 480))
        dst.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(dst, "JPEG", quality=70)


def generate_all():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ---------------- A: Aurora (GREEN) ----------------
    a = DATA_DIR / "aurora"
    make_pdf(a / "affidavit_2.pdf", [
        "AFFIDAVIT 2",
        "Digitally Signed By: Aurora Vidya Trust",
        "Institution Name: Aurora Institute of Technology (Synthetic)",
        "Trust Name: Aurora Vidya Trust",
        "Survey No: SY-42/3A",
        "E-Stamp Issue Date: 2027-01-10",
        "Notarisation Date: 2027-01-12",
        "Signatory: Chairperson, Aurora Vidya Trust",
    ])
    make_pdf(a / "ter_receipt.pdf", [
        "TER RECEIPT",
        "Digitally Signed By: AICTE Portal",
        "Institution Name: Aurora Institute of Technology (Synthetic)",
        "Receipt No: TER-A-2027",
        "Amount: 53240",
    ])
    make_pdf(a / "occupancy_certificate.pdf", [
        "OCCUPANCY CERTIFICATE",
        "Digitally Signed By: Karnataka Town Planning Authority",
        "Institution Name: Aurora Institute of Technology (Synthetic)",
        "OC Type: FULL",
        "Valid Till: 2030-01-01",
    ])
    make_pdf(a / "fire_safety_certificate.pdf", [
        "FIRE SAFETY CERTIFICATE",
        "Digitally Signed By: Karnataka Fire Department",
        "Institution Name: Aurora Institute of Technology (Synthetic)",
        "Valid Till: 2028-11-19",
        "QR Valid Till: 2028-11-19",
    ])
    make_pdf(a / "satellite_map.pdf", [
        "SATELLITE MAP",
        "Digitally Signed By: Aurora Institute of Technology (Synthetic)",
        "Institution Name: Aurora Institute of Technology (Synthetic)",
        "Latitude: 13.1200",
        "Longitude: 77.6300",
    ])
    make_pdf(a / "audited_accounts.pdf", [
        "AUDITED STATEMENT OF ACCOUNTS",
        "Digitally Signed By: Rao & Associates (CA Firm)",
        "Entity: Aurora Vidya Trust",
        "Financial Year: 2026-27",
    ])
    make_photo(a / "lab_photo.jpg", (60, 110, 160), "Aurora - Computer Lab", seed=1001)
    (a / "faculty_list.csv").write_text(
        "faculty_id,name,full_time\n" + "\n".join(f"AUR-F{i:03d},Faculty {i},true" for i in range(1, 27)),
        encoding="utf-8",
    )

    # ---------------- B: Bhavani (AMBER) ----------------
    b = DATA_DIR / "bhavani"
    make_pdf(b / "affidavit_2.pdf", [
        "AFFIDAVIT 2",
        "Digitally Signed By: Bhavani Shiksha Samiti",
        "Institution Name: Bhavani College of Engineering (Synthetic)",
        "Trust Name: Bhavani Shiksha Samiti",
        "Survey No: SY-77/1",
        "E-Stamp Issue Date: 2027-01-05",
        "Notarisation Date: 2027-01-08",
        "Signatory: Secretary, Bhavani Shiksha Samiti",
    ])
    make_pdf(b / "ter_receipt.pdf", [
        "TER RECEIPT",
        "Digitally Signed By: AICTE Portal",
        "Institution Name: Bhavani College of Engineering (Synthetic)",
        "Receipt No: TER-B-2027",
        "Amount: 79860",
    ])
    make_pdf(b / "occupancy_certificate.pdf", [
        "OCCUPANCY CERTIFICATE",
        "Digitally Signed By: Maharashtra Municipal Corporation",
        "Institution Name: Bhavani College of Engineering (Synthetic)",
        "OC Type: PROVISIONAL",
        "Provisional Years Used: 3",
        "Valid Till: 2029-01-01",
    ])
    make_pdf(b / "fire_safety_certificate.pdf", [
        "FIRE SAFETY CERTIFICATE",
        "Digitally Signed By: Maharashtra Fire Department",
        "Institution Name: Bhavani College of Engineering (Synthetic)",
        "Valid Till: 2027-06-30",
        "QR Valid Till: 2027-06-30",
    ])
    make_pdf(b / "satellite_map.pdf", [
        "SATELLITE MAP",
        "Digitally Signed By: Bhavani College of Engineering (Synthetic)",
        "Institution Name: Bhavani College of Engineering (Synthetic)",
        "Latitude: 18.6100",
        "Longitude: 73.8200",
    ])
    make_pdf(b / "audited_accounts.pdf", [
        "AUDITED STATEMENT OF ACCOUNTS",
        "Digitally Signed By: Mehta & Co (CA Firm)",
        "Entity: Bhavani Shiksha Samiti",
        "Financial Year: 2026-27",
    ])
    make_photo(b / "lab_photo.jpg", (110, 150, 70), "Bhavani - Computer Lab", seed=1002)
    (b / "faculty_list.csv").write_text(
        "faculty_id,name,full_time\n" + "\n".join(f"BHA-F{i:03d},Faculty {i},true" for i in range(1, 43)),
        encoding="utf-8",
    )

    # ---------------- C: Chandra (RED) ----------------
    c = DATA_DIR / "chandra"
    make_pdf(c / "affidavit_2.pdf", [
        "AFFIDAVIT 2",
        "Digitally Signed By: Chandra Educational Society",
        "Institution Name: Chandra Technical Campus (Synthetic)",
        "Trust Name: Chandra Educational Society",
        "Survey No: SY-118/4B",
        "E-Stamp Issue Date: 2027-01-20",
        "Notarisation Date: 2027-01-15",
        "Signatory: Secretary, Chandra Educational Society",
    ])
    make_pdf(c / "ter_receipt.pdf", [
        "TER RECEIPT",
        "Digitally Signed By: AICTE Portal",
        "Institution Name: Chandra Technical Campus (Synthetic)",
        "Receipt No: TER-C-2027",
        "Amount: 266200",
    ])
    make_pdf(c / "occupancy_certificate.pdf", [
        "OCCUPANCY CERTIFICATE",
        "Digitally Signed By: Tamil Nadu Municipal Corporation",
        "Institution Name: Chandra Technical Campus (Synthetic)",
        "OC Type: FULL",
        "Valid Till: 2030-01-01",
    ])
    make_pdf(c / "fire_safety_certificate.pdf", [
        "FIRE SAFETY CERTIFICATE",
        "Digitally Signed By: Tamil Nadu Fire Department",
        "Institution Name: Chandra Technical Campus (Synthetic)",
        "Valid Till: 2028-12-31",
        "QR Valid Till: 2026-12-31",
    ])
    make_pdf(c / "satellite_map.pdf", [
        "SATELLITE MAP",
        "Digitally Signed By: Chandra Technical Campus (Synthetic)",
        "Institution Name: Chandra Technical Campus (Synthetic)",
        "Latitude: 11.0500",
        "Longitude: 77.0100",
    ])
    make_pdf(c / "audited_accounts.pdf", [
        "AUDITED STATEMENT OF ACCOUNTS",
        "Digitally Signed By: Iyer & Partners (CA Firm)",
        "Entity: Chandra Educational Society",
        "Financial Year: 2026-27",
    ])

    # The land record: an ORIGINAL version (what the issuer / DigiLocker mock
    # keeps on record) and a TAMPERED version (what the institution uploads).
    # We keep the original only long enough to hash it for the IssuerRecord,
    # then only the tampered copy ships as the upload.
    land_original = c / "land_document_original.pdf"
    make_pdf(land_original, [
        "LAND OWNERSHIP DOCUMENT",
        "Digitally Signed By: Tamil Nadu Land Authority",
        "Institution Name: Chandra Technical Campus (Synthetic)",
        "Survey No: SY-118/4B",
    ])
    make_pdf(c / "land_document.pdf", [
        "LAND OWNERSHIP DOCUMENT",
        "Digitally Signed By: Tamil Nadu Land Authority",
        "Institution Name: Chandra Technical Campus (Synthetic)",
        "Survey No: SY-118/9C",
        "Tampered-Field: survey_no",
    ])

    make_photo(c / "classroom_photo.jpg", (160, 90, 60), "Chandra - Classroom", seed=1003)
    make_duplicate_photo(a / "lab_photo.jpg", c / "lab_photo.jpg")

    chandra_faculty_lines = ["faculty_id,name,full_time"]
    for i in range(1, 98):
        chandra_faculty_lines.append(f"CHA-F{i:03d},Faculty {i},true")
    for i in range(1, 13):
        chandra_faculty_lines.append(f"DEL-F{i:03d},Faculty D{i},true")
    (c / "faculty_list.csv").write_text("\n".join(chandra_faculty_lines), encoding="utf-8")

    return DATA_DIR


if __name__ == "__main__":
    generate_all()
    print("Synthetic documents generated under", DATA_DIR)
