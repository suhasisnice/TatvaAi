"""Deterministic synthetic data generator (all people, institutions and documents are fictional).

Usage: python scripts/generate_synthetic.py [--seed 2026] [--out data/synthetic] [--expected data/expected_flags.json]

Writes, per institution a/b/c and year: signed PDFs, faculty.csv, EXIF photos, application.json;
plus pki/, mock_db.json (consumed by mock_issuers) and manifest.json (sha256 of every file + extraction ground truth).
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import random
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import piexif
import pymupdf
import qrcode
import yaml
from faker import Faker
from PIL import Image, ImageDraw
from pyhanko.pdf_utils import incremental_writer
from pyhanko.pdf_utils.metadata import info as info_mod
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import signers
from pyhanko.sign.signers import pdf_signer
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_test_pki import ensure_pki  # noqa: E402

AY, PREV_AY = "2027-28", "2026-27"
AY_START = date(2027, 8, 1)
WEB_BASE = "http://mock-issuers:9000/web"

# ---------------------------------------------------------------- deterministic signing plumbing
_clock = [datetime(2027, 1, 1, tzinfo=timezone.utc)]
_idseed = [b""]


class _FixedDT(datetime):
    @classmethod
    def now(cls, tz=None):
        return _clock[0] if tz is None else _clock[0].astimezone(tz)


class _OS:
    def __getattr__(self, k):
        return getattr(os, k)

    @staticmethod
    def urandom(n):
        _idseed[0] = hashlib.sha256(_idseed[0]).digest()
        return _idseed[0][:n]


pdf_signer.datetime = _FixedDT
info_mod.datetime = _FixedDT  # pyHanko stamps Info /ModDate with the wall clock
incremental_writer.os = _OS()


def sign_pdf(data: bytes, pki: Path, signer: str, when: date, tag: str) -> bytes:
    _clock[0] = datetime(when.year, when.month, when.day, 10, 0, tzinfo=timezone.utc)
    _idseed[0] = tag.encode()
    s = signers.SimpleSigner.load(pki / f"{signer}.key.pem", pki / f"{signer}.pem", ca_chain_files=(pki / "ca.pem",))
    meta = signers.PdfSignatureMetadata(field_name="Signature1", reason="Digitally signed (synthetic test DSC)", location="Synthetic")
    return signers.sign_pdf(IncrementalPdfFileWriter(io.BytesIO(data)), meta, signer=s).getvalue()


def tamper_survey(signed: bytes, old: str, new: str, tmp: Path) -> bytes:
    """Edit text AFTER signing via an incremental update, in a different font (Times)."""
    tmp.write_bytes(signed)
    d = pymupdf.open(tmp)
    pg = d[0]
    r = pg.search_for(old)[0]
    pg.add_redact_annot(r)
    pg.apply_redactions()
    pg.insert_text((r.x0, r.y1 - 2), new, fontname="tiro", fontsize=12)
    d.saveIncr()
    d.close()
    out = tmp.read_bytes()
    tmp.unlink()
    m = list(re.finditer(rb"/ID\[<([0-9A-Fa-f]{32})><([0-9A-Fa-f]{32})>\]", out))[-1]  # PyMuPDF randomises the 2nd id
    fixed = hashlib.sha256(out[: m.start(2)]).hexdigest()[:32].upper().encode()
    return out[: m.start(2)] + fixed + out[m.end(2):]


# ---------------------------------------------------------------- rendering
def qr_png(payload: str) -> io.BytesIO:
    b = io.BytesIO()
    qrcode.make(payload).save(b, format="PNG")
    b.seek(0)
    return b


def render_pdf(title: str, issuer: str, fields: list, qr: str | None = None, image: Image.Image | None = None) -> bytes:
    """fields: [(key, label, value)]. Each is drawn as 'Label:' + value on one line (anchor-extractable)."""
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4, invariant=1)
    c.setTitle(title)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, 790, title)
    c.setFont("Helvetica", 10)
    c.drawString(60, 772, issuer)
    y = 735
    for _, label, value in fields:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(60, y, f"{label}:")
        size = 12
        while size > 6 and stringWidth(str(value), "Helvetica", size) > 300:  # keep long values (addresses) on the page
            size -= 0.5
        c.setFont("Helvetica", size)
        c.drawString(250, y, str(value))
        y -= 26
    if image is not None:
        ib = io.BytesIO()
        image.save(ib, format="PNG")
        ib.seek(0)
        c.drawImage(ImageReader(ib), 60, 110, width=400, height=250)
    if qr:
        c.drawImage(ImageReader(qr_png(qr)), 450, 50, width=90, height=90)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(60, 30, "SYNTHETIC DOCUMENT FOR PROTOTYPE TESTING. Not a real certificate. All names and numbers are fictional.")
    c.save()
    # reportlab stamps ModDate with the wall clock even in invariant mode; same-length replacement keeps xref offsets valid
    return re.sub(rb"/ModDate \(D\\072\d{14}", lambda m: rb"/ModDate (D\07220000101000000", b.getvalue())


def iso(d: date) -> str:
    return d.isoformat()


# ---------------------------------------------------------------- world definition
def P(course, intake, programme="ENGINEERING_AND_TECHNOLOGY", level="UG", duration=4):
    return dict(programme=programme, level=level, course=course, intake=intake, duration=duration, divisions=math.ceil(intake / 60))


def B(name, completed, floors, footprint, declared, oc_type, oc_issue, first_seen, oc_valid="Perpetual"):
    return dict(name=name, completed=completed, floors=floors, footprint=footprint, declared=declared,
                oc_type=oc_type, oc_issue=oc_issue, first_seen=first_seen, oc_valid=oc_valid)


INST = {
    "a": dict(
        name="Aurora Institute of Technology (Synthetic)", trust="Aurora Vidya Trust (Synthetic)", state="Karnataka", st="karnataka",
        aicte="SYN-AICTE-1001", lat=13.1200, lon=77.6300, address="Plot 14, Aurora Nagar, Hosakote Road, Karnataka (Synthetic)",
        survey="SY-42/3A", village="Aurora Nagar", fac_base=100000, fac_n=26, web_fac=26,  # 26 faculty: passes 1:20 (needs 24) but fails the v2-demo 1:18 pack (needs 27)
        programmes=[P("Computer Science and Engineering", 60), P("Electronics and Communication Engineering", 60)],
        buildings=[B("Main Block", date(2012, 6, 15), 3, 2000, 6100, "FULL", date(2012, 7, 1), 2012)],
        fire=dict(issue=date(2025, 11, 20), valid=date(2028, 11, 19)),
        naac=3.22,
    ),
    "b": dict(
        name="Bhavani College of Engineering (Synthetic)", trust="Bhavani Shiksha Samiti (Synthetic)", state="Maharashtra", st="maharashtra",
        aicte="SYN-AICTE-1002", lat=18.6100, lon=73.8200, address="Survey 77, Bhavani Vihar, Talegaon Road, Maharashtra (Synthetic)",
        survey="SY-77/1", village="Bhavani Vihar", fac_base=200000, fac_n=42, web_fac=42,
        programmes=[P("Computer Science and Engineering", 60), P("Mechanical Engineering", 60), P("Civil Engineering", 60)],
        buildings=[B("Main Block", date(1990, 3, 10), 3, 1800, 5500, "FULL", date(1990, 4, 1), 2005),
                   B("New Block", date(2024, 9, 1), 3, 1500, 4600, "PROVISIONAL", date(2025, 4, 10), 2024, oc_valid="2028-04-09")],
        fire=dict(issue=date(2024, 7, 1), valid=date(2027, 6, 30)),
        naac=None,
    ),
    "c": dict(
        name="Chandra Technical Campus (Synthetic)", trust="Chandra Educational Society (Synthetic)", state="Tamil Nadu", st="tamilnadu",
        aicte="SYN-AICTE-1003", lat=11.0500, lon=77.0100, address="Block 9, Chandra Puram, Coimbatore Road, Tamil Nadu (Synthetic)",
        survey="SY-118/4B", village="Chandra Puram", fac_base=300000, fac_n=97, web_fac=85,
        programmes=[P(n, 120) for n in ("Computer Science and Engineering", "Electronics and Communication Engineering",
                                         "Mechanical Engineering", "Civil Engineering", "Electrical and Electronics Engineering")],
        buildings=[B("Main Block", date(2016, 5, 20), 4, 3000, 15500, "FULL", date(2016, 6, 15), 2016),
                   B("Block B", date(2019, 7, 1), 4, 1725, 8500, "FULL", date(2019, 8, 1), 2019),
                   B("Block C", date(2023, 6, 30), 4, 1300, 7500, "FULL", date(2023, 6, 30), 2026)],  # imagery first shows it in 2026
        fire=dict(issue=date(2025, 12, 31), valid=date(2028, 12, 31)),
        naac=None,
    ),
}
DUP_FACULTY = [f"AICTE-FAC-{900001 + i}" for i in range(12)]  # registered full-time at "D" (registry-only institution)
D_AICTE = "SYN-AICTE-1004"
OLD_YEARS = 30  # structural certificate threshold (APH Annexure-2, p. 81)


def ter_amount(cat: str, divisions: int, ay: str) -> int:
    """TER charges per APH Table 2.1 (p.13): EoA on self-disclosure is charged per division of the applied intake; +10% a year from 2024-25."""
    cfg = yaml.safe_load((ROOT / "rulepacks/config/ter_fees.yaml").read_text())
    c = cfg["categories"][cat]
    years = int(ay[:4]) - int(cfg["base_year"][:4])
    base = c["per_division"] * divisions if "per_division" in c else c["flat"]
    return round(base * (1 + cfg["escalation_pct_per_year"] / 100) ** years)


def authority(st: str, kind: str) -> str:
    return yaml.safe_load((ROOT / "rulepacks/config/issuing_authorities.yaml").read_text())["states"][st][kind]


def declared_infra(i: dict) -> dict:
    """Generous declared infrastructure so norms pass except where deliberately planted (see Annexure-3/4)."""
    div = sum(p["divisions"] for p in i["programmes"])
    dur, n = 4, len(i["programmes"])
    intake = sum(p["intake"] for p in i["programmes"])
    s_total = sum(p["intake"] * p["duration"] for p in i["programmes"])
    classrooms = math.ceil(div * dur * 0.5) + 2
    pcs = max(20, math.ceil(s_total / 10)) + 12
    bw = 100 if intake <= 300 else 300 if intake <= 600 else 500
    return dict(
        classrooms=dict(count=classrooms, area_each_m2=66),
        tutorial_rooms=dict(count=math.ceil(0.25 * classrooms) + 1, area_each_m2=33),
        labs=dict(count=4 + 2 * n * 3 + 2, area_each_m2=66),
        workshop=dict(count=1, area_each_m2=220),
        computer_centre=dict(count=1, area_each_m2=160),
        seminar_hall=dict(count=1, area_each_m2=140),
        library=dict(count=1, area_each_m2=450),
        language_lab=dict(count=1, area_each_m2=40),
        pcs=pcs, printers=math.ceil(pcs * 0.05) + 1, bandwidth_mbps=bw * 2 if bw < 500 else 1000,
    )


# ---------------------------------------------------------------- photos
def draw_photo(kind: str, seed: int) -> Image.Image:
    r = random.Random(seed)
    img = Image.new("RGB", (1024, 768), tuple(r.randint(150, 230) for _ in range(3)))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 520, 1024, 768], fill=tuple(r.randint(90, 160) for _ in range(3)))
    if kind == "classroom":
        d.rectangle([r.randint(150, 250), 60, r.randint(750, 850), r.randint(200, 260)], fill=(30, 70, 50))
        for row in range(r.randint(3, 5)):
            for col in range(r.randint(4, 7)):
                x, y = 80 + col * 130 + r.randint(-8, 8), 330 + row * 85
                d.rectangle([x, y, x + 90, y + 40], fill=tuple(r.randint(110, 180) for _ in range(3)))
    elif kind == "lab":
        for row in range(r.randint(3, 4)):
            for col in range(r.randint(5, 8)):
                x, y = 60 + col * 115 + r.randint(-5, 5), 250 + row * 125
                d.rectangle([x, y, x + 80, y + 55], fill=(20, 20, 30))
                d.rectangle([x + 25, y + 55, x + 55, y + 70], fill=(70, 70, 70))
    else:
        for col in range(r.randint(5, 8)):
            x = 40 + col * 125
            d.rectangle([x, 80, x + 95, 560], fill=tuple(r.randint(70, 140) for _ in range(3)))
            for shelf in range(6):
                d.rectangle([x + 5, 100 + shelf * 75, x + 90, 145 + shelf * 75], fill=tuple(r.randint(120, 255) for _ in range(3)))
    for _ in range(400):  # grain makes perceptual hashes of different photos clearly distinct
        x, y = r.randint(0, 1023), r.randint(0, 767)
        d.point((x, y), fill=tuple(r.randint(0, 255) for _ in range(3)))
    return img


def _rat(v: float):
    return (int(round(v * 1_000_000)), 1_000_000)


def _dms(v: float):
    v = abs(v)
    return (_rat(int(v)), _rat(int((v - int(v)) * 60)), _rat(((v - int(v)) * 60 - int((v - int(v)) * 60)) * 60))


def save_photo(img: Image.Image, path: Path, lat: float, lon: float, when: datetime, quality: int = 90) -> None:
    exif = piexif.dump({
        "0th": {piexif.ImageIFD.Make: b"SynthCam", piexif.ImageIFD.Model: b"SC-1", piexif.ImageIFD.Software: b"PramaanAI Synthetic Generator"},
        "Exif": {piexif.ExifIFD.DateTimeOriginal: when.strftime("%Y:%m:%d %H:%M:%S").encode()},
        "GPS": {piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S", piexif.GPSIFD.GPSLatitude: _dms(lat),
                piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W", piexif.GPSIFD.GPSLongitude: _dms(lon)},
    })
    img.save(path, "JPEG", quality=quality, exif=exif)


# ---------------------------------------------------------------- footprints
def footprints(i: dict) -> dict:
    feats, x0 = [], 0.0
    for b in i["buildings"]:
        w = math.sqrt(b["footprint"] * 1.5)
        h = b["footprint"] / w
        dlat, dlon = 1 / 111_320, 1 / (111_320 * math.cos(math.radians(i["lat"])))
        ring = [(x0, 0), (x0 + w, 0), (x0 + w, h), (x0, h), (x0, 0)]
        coords = [[round(i["lon"] + x * dlon, 7), round(i["lat"] + y * dlat, 7)] for x, y in ring]
        feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords]},
                      "properties": {"building": b["name"], "area_m2": b["footprint"], "floors": b["floors"], "first_seen_year": b["first_seen"]}})
        x0 += w + 25
    return {"type": "FeatureCollection", "mock": True, "imagery_start_year": 2005, "features": feats}


# ---------------------------------------------------------------- per institution / year build
class Out:
    def __init__(self, root: Path):
        self.root, self.files, self.docs = root, {}, []

    def write(self, rel: str, data: bytes) -> str:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        self.files[rel] = hashlib.sha256(data).hexdigest()
        return self.files[rel]


def build_static_docs(key: str, i: dict, plant: bool, out: Out, pki: Path, base: str, fake: Faker, mock: dict, yeardirs: list):
    """Year-independent documents: byte-identical across years unless planted (enables carry-forward)."""
    st = i["st"]
    docs = []

    clamp = lambda d: max(d + timedelta(days=1), date(2025, 3, 1))
    # ---- land document
    reg_no = f"REG-{key.upper()}-2009-0417"
    uri = f"digilocker://land/{key}/{reg_no}"
    land_fields = [("owner_name", "Owner", i["trust"]), ("survey_no", "Survey No", i["survey"]), ("village", "Village", i["village"]),
                   ("area_acres", "Area (acres)", {"a": "12.5", "b": "15.0", "c": "22.0"}[key]), ("registration_no", "Registration No", reg_no),
                   ("registration_date", "Registration Date", "2009-02-11"), ("land_use", "Land Use", "Educational"), ("digilocker_uri", "DigiLocker URI", uri)]
    tamper = None
    if plant and key == "c":
        tamper = (i["survey"], "SY-118/9C")
        land_fields_shown = [(k, l, "SY-118/9C" if k == "survey_no" else v) for k, l, v in land_fields]
    else:
        land_fields_shown = land_fields
    land_issuer = authority(st, "land_use_certificate")
    pdf = render_pdf("Land Ownership Record", land_issuer, land_fields)
    signed = sign_pdf(pdf, pki, f"auth-{st}", date(2026, 1, 10), f"{key}-land")
    mock["digilocker"][uri] = dict(uri=uri, doc_type="LAND_DOCUMENT", issuer=land_issuer, original_sha256=hashlib.sha256(signed).hexdigest(),
                                   fields={"survey_no": i["survey"], "owner_name": i["trust"], "registration_no": reg_no})
    if tamper:
        signed = tamper_survey(signed, *tamper, tmp=out.root / f"_t_{key}.pdf")
    docs.append(dict(doc_type="LAND_DOCUMENT", name="LAND_DOCUMENT", data=signed, signer=f"auth-{st}", signed_at="2026-01-10",
                     fields={k: dict(label=l, value=str(v)) for k, l, v in land_fields_shown}, planted=["MODIFIED_AFTER_SIGNING", "TAMPER_SUSPECTED", "ISSUER_MISMATCH"] if tamper else []))

    # ---- occupancy certificates (one per building)
    for n, b in enumerate(i["buildings"]):
        cert_no = f"OC-{st[:2].upper()}-{key.upper()}{n + 1}-{b['oc_issue'].year}"
        fields = [("certificate_no", "Certificate No", cert_no), ("certificate_type", "Certificate Type", b["oc_type"]),
                  ("institution_name", "Institution", i["name"]), ("building_name", "Building", b["name"]),
                  ("issue_date", "Issue Date", iso(b["oc_issue"])), ("completion_date", "Completion Date", iso(b["completed"])),
                  ("built_up_area_m2", "Built-up Area (sq m)", b["declared"]), ("floors", "Floors", b["floors"]),
                  ("survey_no", "Survey No", i["survey"]), ("valid_till", "Valid Till", b["oc_valid"]),
                  ("issuing_authority", "Issuing Authority", authority(st, "occupancy_certificate"))]
        payload = json.dumps({"t": "OC", "no": cert_no, "type": b["oc_type"], "issued": iso(b["oc_issue"])}, sort_keys=True)
        pdf = render_pdf("Occupancy Certificate" if b["oc_type"] == "FULL" else "Provisional Occupancy Certificate", authority(st, "occupancy_certificate"), fields, payload)
        planted = ["PROVISIONAL_OC_LIMIT_EXCEEDED"] if b["oc_type"] == "PROVISIONAL" else []
        data = sign_pdf(pdf, pki, f"auth-{st}", clamp(b["oc_issue"]), f"{key}-oc{n}")
        docs.append(dict(doc_type="OCCUPANCY_CERTIFICATE", name=f"OCCUPANCY_CERTIFICATE_{n + 1}", data=data, signer=f"auth-{st}",
                         signed_at=iso(clamp(b["oc_issue"])), fields={k: dict(label=l, value=str(v)) for k, l, v in fields}, planted=planted))
        mock["occupancy"].setdefault(st, {})[cert_no] = dict(certificate_no=cert_no, type=b["oc_type"], issue_date=iso(b["oc_issue"]),
                                                              building=b["name"], valid_till=b["oc_valid"], built_up_area_m2=b["declared"], status="ISSUED")
        if b["oc_type"] == "PROVISIONAL":
            mock["_prov"].append(dict(building=b["name"], certificate_no=cert_no, academic_years=["2025-26", "2026-27"]))

    # ---- structural stability (only for buildings older than 30 years at the AY start)
    for b in i["buildings"]:
        if (AY_START - b["completed"]).days / 365.25 > OLD_YEARS:
            eng = fake.name()
            fields = [("certificate_no", "Certificate No", f"SSC-{key.upper()}-2025-031"), ("institution_name", "Institution", i["name"]),
                      ("building_name", "Building", b["name"]), ("engineer_name", "Structural Engineer", eng),
                      ("engineer_reg_no", "Engineer Reg No", f"SE-{key.upper()}-88231"), ("issue_date", "Issue Date", "2025-02-14"), ("valid_till", "Valid Till", "2030-02-13")]
            data = sign_pdf(render_pdf("Structural Stability Certificate", "Registered Structural Engineer (Synthetic)", fields), pki, f"auth-{st}", date(2025, 3, 1), f"{key}-ssc")
            docs.append(dict(doc_type="STRUCTURAL_STABILITY_CERTIFICATE", name="STRUCTURAL_STABILITY_CERTIFICATE", data=data, signer=f"auth-{st}",
                             signed_at="2025-03-01", fields={k: dict(label=l, value=str(v)) for k, l, v in fields}, planted=[]))

    # ---- fire safety certificate
    f = i["fire"]
    cert_no = f"FIRE-{st[:2].upper()}-{key.upper()}-{f['issue'].year}"
    fields = [("certificate_no", "Certificate No", cert_no), ("institution_name", "Institution", i["name"]), ("issue_date", "Issue Date", iso(f["issue"])),
              ("valid_till", "Valid Till", iso(f["valid"])), ("issuing_authority", "Issuing Authority", authority(st, "fire_safety")), ("state", "State", i["state"])]
    qr_valid = date(2026, 12, 31) if plant and key == "c" else f["valid"]
    payload = json.dumps({"t": "FIRE", "no": cert_no, "issued": iso(f["issue"]), "valid_till": iso(qr_valid)}, sort_keys=True)
    data = sign_pdf(render_pdf("Fire and Life Safety Certificate", authority(st, "fire_safety"), fields, payload), pki, f"auth-{st}", clamp(f["issue"]), f"{key}-fire{int(plant)}")
    planted = ["QR_MISMATCH"] if plant and key == "c" else (["DOC_EXPIRES_BEFORE_AY"] if key == "b" else [])
    docs.append(dict(doc_type="FIRE_SAFETY_CERTIFICATE", name="FIRE_SAFETY_CERTIFICATE", data=data, signer=f"auth-{st}", signed_at=iso(clamp(f["issue"])),
                     fields={k: dict(label=l, value=str(v)) for k, l, v in fields}, planted=planted, qr_payload=payload))
    mock["fire"].setdefault(st, {})[cert_no] = dict(certificate_no=cert_no, issue_date=iso(f["issue"]), valid_till=iso(f["valid"]), status="VALID" if f["valid"] > date(2027, 1, 1) else "EXPIRED")
    return docs


def build_yearly_docs(key: str, i: dict, ay: str, plant: bool, out: Out, pki: Path, fake: Faker, mock: dict, signatory: str, notary: str, ca: dict):
    y = int(ay[:4])
    st, docs = i["st"], []

    def emit(doc_type, name, title, issuer, fields, signer, when, qr=None, image=None, planted=None):
        data = sign_pdf(render_pdf(title, issuer, fields, qr, image), pki, signer, when, f"{key}-{ay}-{name}")
        docs.append(dict(doc_type=doc_type, name=name, data=data, signer=signer, signed_at=iso(when),
                         fields={k: dict(label=l, value=str(v)) for k, l, v in fields}, planted=planted or []))

    # affidavit 2 (+ SHCIL record). C plants an e-stamp issued AFTER notarisation.
    notarised = date(y, 1, {"a": 12, "b": 16, "c": 15}[key])
    stamp_issue = date(y, 1, 20) if plant and key == "c" else notarised - timedelta(days=2)
    stamp_no = f"IN-{st[:2].upper()}{y}{ord(key) - 96:02d}000{y % 100}01"
    fields = [("institution_name", "Institution", i["name"]), ("trust_name", "Trust/Society", i["trust"]), ("address", "Address", i["address"]),
              ("state", "State", i["state"]), ("estamp_cert_no", "E-Stamp Certificate No", stamp_no), ("estamp_value", "E-Stamp Value (Rs)", "100"),
              ("estamp_issue_date", "E-Stamp Issue Date", iso(stamp_issue)), ("notarisation_date", "Notarisation Date", iso(notarised)),
              ("notary_name", "Notary", notary), ("signatory_name", "Signatory", signatory), ("signatory_designation", "Designation", "Chairperson / Secretary of the Trust")]
    emit("AFFIDAVIT_2", "AFFIDAVIT_2", "Affidavit 2 (Extension of Approval)", "Sworn before a Notary Public (Synthetic)", fields,
         f"inst-{key}", date(y, 2, 5), planted=["TIMELINE_IMPOSSIBLE"] if plant and key == "c" else [])
    mock["shcil"][stamp_no] = dict(certificate_no=stamp_no, state=i["state"], duty_type="Non-Judicial Stamp Paper", value=100, issue_date=iso(stamp_issue), status="VALID")

    # TER receipt
    amount = ter_amount("EOA", sum(p["divisions"] for p in i["programmes"]), ay)
    receipt = f"TER-{key.upper()}-{ay}"
    shown = i["name"].upper() if key == "a" else i["name"]  # case variation exercises name normalisation
    fields = [("receipt_no", "Receipt No", receipt), ("institution_name", "Institution", shown), ("aicte_id", "AICTE ID", i["aicte"]),
              ("amount", "Amount (Rs)", amount), ("payment_date", "Payment Date", iso(date(y, 2, 1))), ("academic_year", "Academic Year", ay)]
    emit("TER_RECEIPT", "TER_RECEIPT", "Technical Education Revenue (TER) Payment Receipt", "AICTE Approval Portal (MOCK)", fields, "aicte-portal", date(y, 2, 1))
    mock["_ter"][ay] = dict(receipt_no=receipt, amount=amount, payment_date=iso(date(y, 2, 1)), status="PAID")

    # satellite map
    img = Image.new("RGB", (800, 500), (196, 214, 176))
    dr = ImageDraw.Draw(img)
    dr.rectangle([0, 230, 800, 270], fill=(120, 120, 120))
    for n in range(len(i["buildings"])):
        dr.rectangle([150 + n * 170, 80, 280 + n * 170, 200], fill=(170, 160, 150))
    dr.ellipse([385, 285, 415, 315], fill=(200, 30, 30))
    fields = [("institution_name", "Institution", i["name"]), ("latitude", "Latitude", f"{i['lat']:.6f}"), ("longitude", "Longitude", f"{i['lon']:.6f}"),
              ("location_label", "Marked Location", "Main Building Entrance"), ("capture_date", "Imagery Date", iso(date(y - 1, 12, 10)))]
    emit("SATELLITE_MAP", "SATELLITE_MAP", "Satellite Map with Main Entrance Coordinates", "Map extract (synthetic imagery)", fields, f"inst-{key}", date(y, 2, 6), image=img)

    # audited accounts
    udin = f"{y % 100 - 1}{ord(key) - 96:02d}88{y % 100}1234AAAB{ord(key) - 96:02d}"
    fields = [("entity_name", "Entity", i["trust"]), ("financial_year", "Financial Year", f"{y - 2}-{str(y - 1)[2:]}"), ("udin", "UDIN", udin),
              ("ca_name", "Chartered Accountant", ca["name"]), ("firm_name", "Firm", ca["firm"]), ("firm_reg_no", "Firm Reg No", ca["reg"]),
              ("total_income", "Total Income (Rs)", 52_000_000 + 7_000_000 * (ord(key) - 96)), ("report_date", "Report Date", iso(date(y - 1, 9, 15)))]
    emit("AUDITED_ACCOUNTS", "AUDITED_ACCOUNTS", "Audited Statement of Accounts", "Independent Auditor's Report (Synthetic)", fields, "ca-firm", date(y - 1, 9, 16))
    mock["udin"][udin] = dict(udin=udin, ca_name=ca["name"], firm=ca["firm"], entity=i["trust"], financial_year=f"{y - 2}-{str(y - 1)[2:]}", status="VALID")
    return docs


def faculty_rows(key: str, i: dict, fake: Faker, dup: bool) -> list:
    n = i["fac_n"]
    prof, assoc = math.ceil(n / 9), math.ceil(2 * n / 9)
    rows = []
    for k in range(n):
        fid = f"AICTE-FAC-{i['fac_base'] + k + 1}"
        des = "Professor" if k < prof else "Associate Professor" if k < prof + assoc else "Assistant Professor"
        rows.append(dict(faculty_id=fid, name=fake.name(), designation=des, qualification="Ph.D." if des != "Assistant Professor" else "M.Tech",
                         full_time="Y", joined_date=iso(date(2012 + k % 12, 1 + k % 12, 1 + k % 27)), department=i["programmes"][k % len(i["programmes"])]["course"]))
    if dup:  # 12 extra rows already registered full-time at another institution
        for k, fid in enumerate(DUP_FACULTY):
            rows.append(dict(faculty_id=fid, name=fake.name(), designation="Assistant Professor", qualification="M.Tech", full_time="Y",
                             joined_date=iso(date(2026, 6, 1 + k)), department=i["programmes"][k % len(i["programmes"])]["course"]))
    for r in rows:
        r["national_id_hash"] = hashlib.sha256(f"SYN-NID-{r['faculty_id']}".encode()).hexdigest()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default=str(ROOT / "data/synthetic"))
    ap.add_argument("--expected", default=str(ROOT / "data/expected_flags.json"))
    a = ap.parse_args()
    out = Out(Path(a.out))
    out.root.mkdir(parents=True, exist_ok=True)
    pki = ensure_pki(out.root / "pki")
    fake = Faker("en_IN")
    fake.seed_instance(a.seed)
    random.seed(a.seed)

    mock = dict(mock=True, shcil={}, digilocker={}, udin={}, fire={}, occupancy={}, _prov=[], _ter={}, aicte_records={}, faculty_registry={},
                websites={}, footprints={}, accreditation=dict(nirf=[], nba=[], naac={}),
                portal_behaviour=dict(fire={"karnataka": 503}, occupancy={"maharashtra": "NO_API"}))
    manifest_docs, photos_meta, fac_rows = [], {}, {}

    # ---- photos: A first (C reuses A's lab photo), then B, then C
    for key in "abc":
        i = INST[key]
        sub = out.root / key
        for kind, n in (("classroom", 1), ("lab", 2), ("library", 3)):
            img = draw_photo(kind, a.seed * 10 + ord(key) * 3 + n)
            lat, lon = i["lat"] + 0.0004 * n, i["lon"] + 0.0003 * n
            # ponytail: fixed Sept 2026 dates stay plausible for the synthetic submission (2027-03-01) and for a live demo submit
            # on the real date until the end of 2029 (photo-time check: not after submission, not >3 years before); move them forward after that
            when = datetime(2026, 9, 10 + n, 11, 30)
            q = 90
            planted = []
            if key == "c" and kind == "classroom":
                lat, lon, planted = i["lat"] + 0.36, i["lon"] + 0.02, ["PHOTO_GPS_OFFSITE"]  # ~40 km away
            if key == "c" and kind == "lab":
                src = draw_photo("lab", a.seed * 10 + ord("a") * 3 + 2)  # A's lab photo, cropped + recompressed
                img = src.crop((50, 40, 974, 728)).resize((1024, 768)); q = 70; planted = ["DUPLICATE_PHOTO"]
            (sub / AY / "photos").mkdir(parents=True, exist_ok=True)
            p = sub / AY / "photos" / f"{kind}_1.jpg"
            save_photo(img, p, lat, lon, when, q)
            out.files[str(p.relative_to(out.root)).replace("\\", "/")] = hashlib.sha256(p.read_bytes()).hexdigest()
            photos_meta.setdefault(key, []).append(dict(file=f"{key}/{AY}/photos/{kind}_1.jpg", kind=kind, lat=lat, lon=lon, taken=when.isoformat(), planted=planted))
            if key in "ac":  # last year's application of A and C: same scene, photographed a year earlier
                prev = sub / PREV_AY / "photos" / f"{kind}_1.jpg"
                prev.parent.mkdir(parents=True, exist_ok=True)
                save_photo(img, prev, lat, lon, when.replace(year=when.year - 1), q)
                out.files[str(prev.relative_to(out.root)).replace("\\", "/")] = hashlib.sha256(prev.read_bytes()).hexdigest()

    # ---- documents, faculty, application.json
    for key in "abc":
        i = INST[key]
        signatory, notary = fake.name(), fake.name()
        ca = dict(name=fake.name(), firm=f"{fake.last_name()} & Associates (Synthetic)", reg=f"FRN{100000 + ord(key)}")
        fac_rows[key] = faculty_rows(key, i, fake, dup=(key == "c"))
        years = [(AY, True)] + ([(PREV_AY, False)] if key in "ac" else [])
        for ay, current in years:
            plant = current  # planted situations exist only in the AY under review
            static = build_static_docs(key, i, plant, out, pki, f"{key}/{ay}", fake, mock, [])
            yearly = build_yearly_docs(key, i, ay, plant, out, pki, fake, mock, signatory, notary, ca)
            for d in static + yearly:
                rel = f"{key}/{ay}/docs/{d['name']}.pdf"
                sha = out.write(rel, d.pop("data"))
                manifest_docs.append(dict(institution=key, academic_year=ay, file=rel, sha256=sha, **d))
            rows = fac_rows[key]
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
            w.writeheader(); w.writerows(rows)
            out.write(f"{key}/{ay}/faculty.csv", buf.getvalue().encode())
            infra = declared_infra(i)
            form = dict(
                institution=dict(name=i["name"], aicte_id=i["aicte"], slug=f"inst-{key}", state=i["state"], trust_name=i["trust"], address=i["address"],
                                 lat=i["lat"], lon=i["lon"], survey_no=i["survey"]),
                category="EOA", academic_year=ay, signatory=dict(name=signatory, designation="Chairperson / Secretary of the Trust"),
                programmes=i["programmes"],
                enrolment=dict(avg_sanctioned_3yr=sum(p["intake"] for p in i["programmes"]), avg_admitted_3yr=round(0.97 * sum(p["intake"] for p in i["programmes"]))),
                buildings=[dict(name=b["name"], completion_date=iso(b["completed"]), floors=b["floors"], declared_built_up_m2=b["declared"], oc_type=b["oc_type"]) for b in i["buildings"]],
                declared_built_up_total_m2=sum(b["declared"] for b in i["buildings"]),
                faculty=dict(declared_full_time=len(rows)), infrastructure=infra,
                accreditation_claim=dict(body="NAAC", score=i["naac"]) if i["naac"] else None,
                website_url=f"{WEB_BASE}/inst-{key}/mandatory-disclosure")
            out.write(f"{key}/{ay}/application.json", json.dumps(form, indent=1, sort_keys=True).encode())

        # mock: AICTE records, website, footprints, faculty registry
        for r in fac_rows[key][: i["fac_n"]]:
            mock["faculty_registry"].setdefault(r["faculty_id"], []).append(dict(institution_aicte_id=i["aicte"], full_time=True, since="2020-07-01"))
        if key == "c":
            for fid in DUP_FACULTY:
                mock["faculty_registry"].setdefault(fid, []).append(dict(institution_aicte_id=D_AICTE, full_time=True, since="2019-07-01"))
                mock["faculty_registry"][fid].append(dict(institution_aicte_id=i["aicte"], full_time=True, since="2026-06-01"))
        mock["aicte_records"][i["aicte"]] = dict(
            institution_id=i["aicte"], name=i["name"], previous_eoa=dict(academic_year=PREV_AY, status="GRANTED"),
            approved_intake={p["course"]: {PREV_AY: p["intake"], "2025-26": p["intake"]} for p in i["programmes"]},
            built_up_area_m2=sum(b["declared"] for b in i["buildings"]), faculty_count=i["fac_n"] + (12 if key == "c" else 0),
            campus=dict(lat=i["lat"], lon=i["lon"]), ter_payments=mock["_ter"] if key == "x" else {}, deficiency_history=[],
            provisional_oc_history=[])
    # fill TER (per institution) and provisional history after loops
    for key in "abc":
        i = INST[key]
        rec = mock["aicte_records"][i["aicte"]]
        rec["ter_payments"] = {ay: dict(receipt_no=f"TER-{key.upper()}-{ay}", amount=ter_amount("EOA", sum(p["divisions"] for p in i["programmes"]), ay), payment_date=iso(date(int(ay[:4]), 2, 1)), status="PAID")
                               for ay in ([AY, PREV_AY] if key in "ac" else [AY])}
        if key == "b":
            rec["provisional_oc_history"] = mock["_prov"]
    mock["aicte_records"][D_AICTE] = dict(institution_id=D_AICTE, name="Delta Polytechnic (Synthetic)", previous_eoa=dict(academic_year=PREV_AY, status="GRANTED"))
    for key in "abc":
        i = INST[key]
        mock["websites"][f"inst-{key}"] = dict(name=i["name"], intake_total=sum(p["intake"] for p in i["programmes"]), faculty_total=i["web_fac"],
                                               accreditation=f"NAAC {i['naac']}" if i["naac"] else "None")
        mock["footprints"][f"inst-{key}-main"] = footprints(i)
    mock["accreditation"]["naac"] = {INST["a"]["aicte"]: 3.22}
    mock["accreditation"]["nba"] = []
    mock["accreditation"]["nirf"] = []
    for k in ("_prov", "_ter"):
        mock.pop(k)
    out.write("mock_db.json", json.dumps(mock, indent=1, sort_keys=True).encode())

    expected = expected_flags()
    Path(a.expected).write_text(json.dumps(expected, indent=1))
    manifest = dict(seed=a.seed, files=dict(sorted(out.files.items())), documents=manifest_docs, photos=photos_meta)
    (out.root / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True))
    print(f"generated {len(out.files)} files under {out.root}")


def expected_flags() -> dict:
    return {
        "academic_year": AY,
        "a": dict(expected_tier="GREEN", planted=[dict(code="ISSUER_UNAVAILABLE", source="fire_noc:karnataka", severity="INFO")],
                  carry_forward=["LAND_DOCUMENT", "OCCUPANCY_CERTIFICATE"], optional=[dict(code="DUPLICATE_PHOTO", severity="INFO", note="earlier owner of the photo C reused")]),
        "b": dict(expected_tier="AMBER", planted=[
            dict(code="DOC_EXPIRES_BEFORE_AY", document_type="FIRE_SAFETY_CERTIFICATE", valid_till="2027-06-30"),
            dict(code="PROVISIONAL_OC_LIMIT_EXCEEDED", document_type="OCCUPANCY_CERTIFICATE", building="New Block", consecutive_years=3)],
            carry_forward=[], optional=[dict(code="ISSUER_UNAVAILABLE", source="occupancy:maharashtra")]),
        "c": dict(expected_tier="RED", planted=[
            dict(code="MODIFIED_AFTER_SIGNING", document_type="LAND_DOCUMENT", field="survey_no", original="SY-118/4B", edited="SY-118/9C"),
            dict(code="TAMPER_SUSPECTED", document_type="LAND_DOCUMENT", severity="CRITICAL"),
            dict(code="ISSUER_MISMATCH", document_type="LAND_DOCUMENT", source="digilocker"),
            dict(code="QR_MISMATCH", document_type="FIRE_SAFETY_CERTIFICATE", qr_valid_till="2026-12-31", printed_valid_till="2028-12-31"),
            dict(code="TIMELINE_IMPOSSIBLE", document_type="AFFIDAVIT_2", estamp_issue="2027-01-20", notarised="2027-01-15"),
            dict(code="DUPLICATE_PHOTO", document_type="INFRA_PHOTO", photo="lab_1.jpg", duplicate_of="a/lab_1.jpg"),
            dict(code="PHOTO_GPS_OFFSITE", document_type="INFRA_PHOTO", photo="classroom_1.jpg", approx_km=40),
            dict(code="DUPLICATE_FACULTY_CROSS_INSTITUTION", source="aicte_faculty_registry", count=12),
            dict(code="NORM_FACULTY_SHORTFALL", S=2400, required=120, declared=109, valid=97, shortfall=23, citation="Annexure-5, p. 95"),
            dict(code="BUILTUP_AREA_IMPLAUSIBLE", declared_m2=31500, footprint_m2=6025, floors=4, expected_m2=24100),
            dict(code="BUILDING_NOT_VISIBLE_ON_DATE", building="Block C", completion_year=2023, first_seen_year=2026),
            dict(code="DISCLOSURE_MISMATCH", declared_faculty=109, website_faculty=85)],
            carry_forward=["OCCUPANCY_CERTIFICATE"], optional=[dict(code="MISMATCH_CROSS_YEAR", field="survey_no"), dict(code="MISMATCH_CROSS_DOC", field="survey_no", document_type="LAND_DOCUMENT")]),
    }


if __name__ == "__main__":
    main()
