"""Synthetic data for institutions A, B, C (2027-28). EVERYTHING here is invented.
Writes data/synthetic/{a,b,c}/2027-28/..., mock_db.json, manifest.json and data/expected_flags.json.
Run: python scripts/make_test_pki.py && python scripts/generate_synthetic.py --seed 2026"""
import argparse
import hashlib
import io
import json
import random
import shutil
from datetime import datetime
from pathlib import Path

import piexif
import pymupdf
import qrcode
from faker import Faker
from PIL import Image, ImageDraw
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import signers
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic"
PKI = DATA / "pki"
YEAR = "2027-28"
FOOTER = "SYNTHETIC DOCUMENT FOR PROTOTYPE TESTING. Not a real certificate. All names and numbers are fictional."
PAGE_H = 842

INSTS = {
    "a": dict(name="Aurora Institute of Technology (Synthetic)", trust="Aurora Vidya Trust (Synthetic)", state="Karnataka", st="KA",
              aicte="SYN-AICTE-1001", lat=13.12, lon=77.63, survey="SY-42/3A", signer="inst-a", faculty=26, web_faculty=26,
              programmes={"CSE": 60, "ECE": 60}, fire=("2025-11-20", "2028-11-19"),
              buildings=[("Main Block", 2012, 3, 2000, 6100, "FULL")]),
    "b": dict(name="Bhavani College of Engineering (Synthetic)", trust="Bhavani Shiksha Samiti (Synthetic)", state="Maharashtra", st="MH",
              aicte="SYN-AICTE-1002", lat=18.61, lon=73.82, survey="SY-77/1", signer="inst-b", faculty=42, web_faculty=42,
              programmes={"CSE": 60, "Mechanical": 60, "Civil": 60}, fire=("2024-07-01", "2027-06-30"),
              buildings=[("Main Block", 1990, 3, 1800, 5500, "FULL"), ("New Block", 2024, 3, 1500, 4600, "PROVISIONAL")]),
    "c": dict(name="Chandra Technical Campus (Synthetic)", trust="Chandra Educational Society (Synthetic)", state="Tamil Nadu", st="TN",
              aicte="SYN-AICTE-1003", lat=11.05, lon=77.01, survey="SY-118/4B", signer="inst-c", faculty=109, web_faculty=85,
              programmes={"CSE": 120, "ECE": 120, "Mechanical": 120, "Civil": 120, "EEE": 120}, fire=("2025-12-31", "2028-12-31"),
              buildings=[("Main Block", 2016, 4, 3000, 15500, "FULL"), ("Block B", 2019, 4, 1725, 8500, "FULL"),
                         ("Block C", 2023, 4, 1300, 7500, "FULL")]),
}
SIGNER_FOR_STATE = {"KA": "auth-ka", "MH": "auth-mh", "TN": "auth-tn"}
_signers: dict[str, signers.SimpleSigner] = {}


def signer(name):
    if name not in _signers:
        _signers[name] = signers.SimpleSigner.load(PKI / f"{name}.key.pem", PKI / f"{name}.cert.pem", ca_chain_files=(PKI / "ca.pem",))
    return _signers[name]


def make_pdf(title, rows, qr_payload=None):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(595, PAGE_H))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, 790, title)
    y = 740
    c.setFont("Helvetica", 11)
    for label, value in rows:  # label and value are separate text spans so extraction can pair them
        c.drawString(50, y, f"{label}:")
        c.drawString(260, y, str(value))
        y -= 28
    if qr_payload:
        img = qrcode.make(qr_payload).convert("RGB")
        c.drawImage(ImageReader(img), 430, 80, 110, 110)
    c.setFont("Helvetica", 7)
    c.drawString(50, 30, FOOTER)
    c.save()
    return buf.getvalue()


def sign(pdf: bytes, signer_name: str) -> bytes:
    w = IncrementalPdfFileWriter(io.BytesIO(pdf))
    return signers.sign_pdf(w, signers.PdfSignatureMetadata(field_name="Sig1"), signer=signer(signer_name)).getvalue()


def tamper_value(path: Path, row_index: int, new_text: str):
    """Edit a signed PDF AFTER signing (incremental update, different font): covers the old value and writes a new one."""
    doc = pymupdf.open(path)
    page = doc[0]
    y_pdf = 740 - 28 * row_index
    rect = pymupdf.Rect(258, PAGE_H - (y_pdf + 12), 560, PAGE_H - (y_pdf - 4))
    page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
    page.insert_text((260, PAGE_H - y_pdf), new_text, fontname="tiro", fontsize=11)
    doc.saveIncr()
    doc.close()


def gps_exif(lat, lon, when: datetime, make):
    def dms(v):
        d = int(v); m = int((v - d) * 60); s = round(((v - d) * 60 - m) * 60 * 100)
        return ((d, 1), (m, 1), (s, 100))
    gps = {piexif.GPSIFD.GPSLatitudeRef: "N", piexif.GPSIFD.GPSLatitude: dms(lat),
           piexif.GPSIFD.GPSLongitudeRef: "E", piexif.GPSIFD.GPSLongitude: dms(lon)}
    return piexif.dump({"0th": {piexif.ImageIFD.Make: make, piexif.ImageIFD.Model: "Synthetic Cam"},
                        "Exif": {piexif.ExifIFD.DateTimeOriginal: when.strftime("%Y:%m:%d %H:%M:%S")}, "GPS": gps})


def scene(label, seed) -> Image.Image:
    r = random.Random(seed)
    img = Image.new("RGB", (800, 600), tuple(r.randint(60, 200) for _ in range(3)))
    d = ImageDraw.Draw(img)
    for _ in range(25):
        x, y = r.randint(0, 700), r.randint(0, 500)
        d.rectangle([x, y, x + r.randint(30, 150), y + r.randint(30, 120)], fill=tuple(r.randint(0, 255) for _ in range(3)))
    d.text((20, 20), f"SYNTHETIC PHOTO: {label}", fill=(255, 255, 255))
    return img


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main(seed: int):
    rnd = random.Random(seed)
    Faker.seed(seed)
    fake = Faker("en_IN")
    if DATA.exists():
        for p in DATA.iterdir():
            if p.name != "pki":
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    db = {"mock": True, "unavailable": ["fire:KA", "occupancy:MH"], "estamp": {}, "fire": {}, "occupancy": {}, "digilocker": {},
          "udin": {}, "aicte": {}, "faculty_registry": {}, "websites": {}, "footprints": {}, "naac": {}}
    manifest = {"docs": []}
    photos_a_lab = None

    def add(key, folder, name, ptype, pdf, fields):
        p = folder / "docs" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(pdf)
        manifest["docs"].append({"inst": key, "path": p.relative_to(DATA).as_posix(), "type": ptype, "fields": fields})
        return p

    for key, i in INSTS.items():
        folder = DATA / key / YEAR
        n = {"a": 1, "b": 2, "c": 3}[key]
        auth = SIGNER_FOR_STATE[i["st"]]
        base = {"institution": i["name"], "aicte_id": i["aicte"]}

        # --- Affidavit 2 (C: e-stamp issued AFTER notarisation = planted #8)
        notarised, estamp_issue = ("2027-01-15", "2027-01-20") if key == "c" else ("2027-02-05", "2027-02-01")
        estamp_no = f"IN-{i['st']}{1000 + n}"
        aff = dict(institution=i["name"], trust=i["trust"], address=f"{fake.street_name()}, {fake.city()}", state=i["state"],
                   estamp_no=estamp_no, estamp_value="100", estamp_issue_date=estamp_issue, notarisation_date=notarised,
                   notary=f"{fake.name()} (Synthetic)", signatory=f"{fake.name()} (Synthetic)", designation="Chairperson")
        labels = ["Institution", "Trust", "Address", "State", "E-Stamp Number", "E-Stamp Value (Rs)", "E-Stamp Issue Date",
                  "Notarisation Date", "Notary", "Signatory", "Designation"]
        add(key, folder, "affidavit_2.pdf", "AFFIDAVIT_2", sign(make_pdf("Affidavit 2", list(zip(labels, aff.values()))), i["signer"]), aff)
        db["estamp"][estamp_no] = {"issue_date": estamp_issue, "value": 100, "holder": i["trust"]}

        # --- TER receipt
        ter = dict(receipt_no=f"TER-{n:04d}", institution=i["name"], aicte_id=i["aicte"], amount="150000", payment_date="2027-02-01", academic_year=YEAR)
        add(key, folder, "ter_receipt.pdf", "TER_RECEIPT", sign(make_pdf("Payment Receipt (TER)", [
            ("Receipt Number", ter["receipt_no"]), ("Institution", i["name"]), ("AICTE ID", i["aicte"]), ("Amount (Rs)", ter["amount"]),
            ("Payment Date", ter["payment_date"]), ("Academic Year", YEAR)]), "aicte-portal"), ter)

        # --- Occupancy certificates (one per building)
        for b, (bname, done, floors, foot, declared, oc) in enumerate(i["buildings"]):
            cert_no = f"OC/{i['st']}/{n}{b}"
            valid_till = "2028-12-31" if oc == "PROVISIONAL" else "2099-12-31"
            f = dict(certificate_no=cert_no, certificate_type=oc, institution=i["name"], building=bname, issue_date=f"{done}-06-30",
                     completion_date=f"{done}-05-31", built_up_area_m2=str(declared), floors=str(floors), survey_no=i["survey"],
                     valid_till=valid_till, authority=f"Building Authority, {i['state']} (Synthetic)")
            payload = json.dumps({"cert": cert_no, "valid_till": valid_till})
            add(key, folder, f"occupancy_{b}.pdf", "OCCUPANCY_CERTIFICATE", sign(make_pdf("Occupancy Certificate", [
                ("Certificate Number", cert_no), ("Certificate Type", oc), ("Institution", i["name"]), ("Building", bname),
                ("Issue Date", f["issue_date"]), ("Completion Date", f["completion_date"]), ("Built-up Area (sq m)", declared),
                ("Floors", floors), ("Survey No", i["survey"]), ("Valid Till", valid_till), ("Authority", f["authority"])], payload), auth), f)
            db["occupancy"][cert_no] = {"institution": i["aicte"], "type": oc, "built_up_area_m2": declared, "valid_till": valid_till}

        # --- Structural stability (B only: Main Block older than 30 years on 2027-08-01)
        if key == "b":
            f = dict(certificate_no="SS/MH/20", institution=i["name"], building="Main Block", engineer=f"{fake.name()} (Synthetic)",
                     registration_no="ENG-5521", issue_date="2025-02-14", valid_till="2030-02-13")
            add(key, folder, "structural.pdf", "STRUCTURAL_STABILITY_CERTIFICATE", sign(make_pdf("Structural Stability Certificate", [
                ("Certificate Number", f["certificate_no"]), ("Institution", i["name"]), ("Building", "Main Block"), ("Engineer", f["engineer"]),
                ("Registration No", "ENG-5521"), ("Issue Date", f["issue_date"]), ("Valid Till", f["valid_till"])]), auth), f)

        # --- Fire certificate (C: QR date differs from printed = planted #7)
        fire_no = f"FIRE/{i['st']}/{n}"
        printed_till = i["fire"][1]
        qr_till = "2026-12-31" if key == "c" else printed_till
        f = dict(certificate_no=fire_no, institution=i["name"], issue_date=i["fire"][0], valid_till=printed_till,
                 authority=f"Fire Services, {i['state']} (Synthetic)", state=i["state"])
        add(key, folder, "fire.pdf", "FIRE_SAFETY_CERTIFICATE", sign(make_pdf("Fire and Life Safety Certificate", [
            ("Certificate Number", fire_no), ("Institution", i["name"]), ("Issue Date", f["issue_date"]), ("Valid Till", printed_till),
            ("Authority", f["authority"]), ("State", i["state"])], json.dumps({"cert": fire_no, "valid_till": qr_till})), auth), f)
        db["fire"][fire_no] = {"institution": i["aicte"], "valid_from": f["issue_date"], "valid_till": printed_till}

        # --- Satellite map, accounts
        add(key, folder, "satellite_map.pdf", "SATELLITE_MAP", sign(make_pdf("Satellite Map", [
            ("Institution", i["name"]), ("Latitude", i["lat"]), ("Longitude", i["lon"]), ("Marked Location", "Main Building Entrance"),
            ("Imagery Date", "2027-01-05")]), i["signer"]), dict(institution=i["name"], latitude=str(i["lat"]), longitude=str(i["lon"])))
        udin = f"27{n:06d}ABCDEF"
        add(key, folder, "accounts.pdf", "AUDITED_ACCOUNTS", sign(make_pdf("Audited Statement of Accounts", [
            ("Entity", i["trust"]), ("Financial Year", "2025-26"), ("UDIN", udin), ("CA Name", f"{fake.name()} (Synthetic)"),
            ("Total Income (Rs)", rnd.randint(30, 90) * 1000000), ("Report Date", "2026-08-15")]), "ca-firm"), dict(udin=udin, entity=i["trust"]))
        db["udin"][udin] = {"entity": i["trust"], "financial_year": "2025-26"}

        # --- Land record (C: tampered after signing = planted #4, #5; DigiLocker holds the original = #6)
        uri = f"in.gov.synthetic-digilocker/LAND/{n:05d}"
        land_rows = [("Owner", i["trust"]), ("Survey No", i["survey"]), ("Village", fake.city()), ("Area (acres)", rnd.randint(8, 30)),
                     ("Registration No", f"REG-{n}{rnd.randint(1000, 9999)}"), ("Registration Date", "2010-03-12"), ("Land Use", "Educational"),
                     ("DigiLocker URI", uri), ("Issue Date", "2026-01-10")]
        land_pdf = sign(make_pdf("Land Ownership Record", land_rows), auth)
        db["digilocker"][uri] = {"fields": {"survey_no": i["survey"], "owner": i["trust"]}, "sha256": sha(land_pdf)}
        lp = add(key, folder, "land_record.pdf", "LAND_DOCUMENT", land_pdf, dict(owner=i["trust"], survey_no=i["survey"]))
        if key == "c":
            tamper_value(lp, 1, "SY-118/9C")
            manifest["docs"][-1]["fields"]["survey_no"] = "SY-118/9C"

        # --- Faculty CSV (C: 12 duplicates registered full-time at D since 2019 = planted #11)
        rows = ["faculty_id,name,designation,qualification,full_time,joining_date,department,national_id_hash"]
        depts = list(i["programmes"])
        own = i["faculty"] - (12 if key == "c" else 0)
        for k in range(own + (12 if key == "c" else 0)):
            dup = key == "c" and k >= own
            fid = f"AICTE-FAC-{900001 + (k - own)}" if dup else f"AICTE-FAC-{n}{k:05d}"
            role = rnd.choices(["Professor", "Associate Professor", "Assistant Professor"], [2, 3, 5])[0]
            q = "PhD" if role != "Assistant Professor" else "ME/MTech"
            nid = sha(f"synthetic-national-id-{fid}".encode())
            rows.append(f"{fid},{fake.name()} (Synthetic),{role},{q},true,{2012 + rnd.randint(0, 14)}-07-01,{depts[k % len(depts)]},{nid}")
            if dup:
                db["faculty_registry"][fid] = [{"aicte_id": "SYN-AICTE-1004", "since": "2019-07-01"}, {"aicte_id": i["aicte"], "since": "2026-07-01"}]
        (folder / "faculty.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

        # --- Photos (C lab = crop of A's lab = #9; C classroom ~40 km away = #10)
        (folder / "photos").mkdir(parents=True, exist_ok=True)
        for kind in ("classroom", "lab", "library"):
            lat, lon = i["lat"] + 0.0003, i["lon"] + 0.0003
            if key == "c" and kind == "classroom":
                lat += 0.36
            img = scene(f"{i['name']} {kind}", rnd.random())
            q = 90
            if key == "c" and kind == "lab":
                img, q = photos_a_lab.crop((20, 20, 780, 580)), 70
            if key == "a" and kind == "lab":
                photos_a_lab = img
            img.save(folder / "photos" / f"{kind}.jpg", quality=q, exif=gps_exif(lat, lon, datetime(2027, 1, 12, 10, 30), "SyntheticCam"))

        # --- Application form + AICTE record + footprints + website
        total = sum(b[4] for b in i["buildings"])
        (folder / "application.json").write_text(json.dumps({
            "institution": i["name"], "aicte_id": i["aicte"], "state": i["state"], "academic_year": YEAR, "category": "EOA",
            "programmes": [{"name": p, "level": "UG", "duration_years": 4, "intake": v} for p, v in i["programmes"].items()],
            "avg_sanctioned_3yr": sum(i["programmes"].values()), "avg_admitted_3yr": int(sum(i["programmes"].values()) * 0.9),
            "buildings": [{"name": b[0], "completion_year": b[1], "floors": b[2], "declared_built_up_m2": b[4], "oc_type": b[5]} for b in i["buildings"]],
            "declared_built_up_total_m2": total, "declared_full_time_faculty": i["faculty"],
            "infrastructure": {"classrooms": 30, "labs": 12, "pcs": 400, "bandwidth_mbps": 1000},
            "accreditation_claim": {"body": "NAAC", "score": 3.22} if key == "a" else None,
            "website": f"https://{key}.synthetic.invalid"}, indent=2), encoding="utf-8")
        db["aicte"][i["aicte"]] = {"previous_eoa": "2026-27", "approved_intake": sum(i["programmes"].values()), "built_up_area_m2": total,
                                   "faculty_count": i["faculty"], "campus": {"lat": i["lat"], "lon": i["lon"]},
                                   "ter_payments": ["2025-26", "2026-27"],
                                   "provisional_oc_history": {"New Block": ["2025-26", "2026-27"]} if key == "b" else {}}
        db["websites"][i["aicte"]] = {"url": f"https://{key}.synthetic.invalid", "faculty_count": i["web_faculty"]}
        db["footprints"][i["aicte"]] = [{"building": b[0], "footprint_m2": b[3], "floors": b[2],
                                         "first_seen_year": 2026 if (key == "c" and b[0] == "Block C") else b[1]} for b in i["buildings"]]
    db["naac"]["Aurora Institute of Technology (Synthetic)"] = 3.22
    (DATA / "mock_db.json").write_text(json.dumps(db, indent=2), encoding="utf-8")
    for d in manifest["docs"]:
        d["sha256"] = sha((DATA / d["path"]).read_bytes())
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def e(inst, code, sev, planted=True, note=""):
        return {"institution": inst, "code": code, "severity": sev, "planted": planted, "note": note}
    (ROOT / "data" / "expected_flags.json").write_text(json.dumps({"year": YEAR, "tiers": {"a": "GREEN", "b": "AMBER", "c": "RED"}, "flags": [
        e("a", "ISSUER_UNAVAILABLE", "INFO", note="#1 Karnataka fire portal down"),
        e("b", "DOC_EXPIRES_BEFORE_AY", "MAJOR", note="#2"), e("b", "PROVISIONAL_OC_LIMIT_EXCEEDED", "MAJOR", note="#3"),
        e("c", "MODIFIED_AFTER_SIGNING", "CRITICAL", note="#4"), e("c", "TAMPER_SUSPECTED", "CRITICAL", note="#5"),
        e("c", "ISSUER_MISMATCH", "MAJOR", note="#6"), e("c", "QR_MISMATCH", "MAJOR", note="#7"),
        e("c", "TIMELINE_IMPOSSIBLE", "MAJOR", note="#8"), e("c", "DUPLICATE_PHOTO", "MAJOR", note="#9"),
        e("c", "PHOTO_GPS_OFFSITE", "MAJOR", note="#10"), e("c", "DUPLICATE_FACULTY_CROSS_INSTITUTION", "MAJOR", note="#11"),
        e("c", "NORM_FACULTY_SHORTFALL", "MAJOR", note="#12"), e("c", "BUILTUP_AREA_IMPLAUSIBLE", "MAJOR", note="#13"),
        e("c", "BUILDING_NOT_VISIBLE_ON_DATE", "MAJOR", note="#14"), e("c", "DISCLOSURE_MISMATCH", "MAJOR", note="#15"),
        e("c", "MISMATCH_CROSS_DOC", "MAJOR", False, "optional consequence of #4"),
        e("b", "ISSUER_UNAVAILABLE", "INFO", False, "optional: Maharashtra occupancy has no API"),
    ]}, indent=2), encoding="utf-8")
    print(f"wrote {len(manifest['docs'])} PDFs for 3 institutions under {DATA}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    main(ap.parse_args().seed)
