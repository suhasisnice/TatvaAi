"""Thin per-source adapters over adapters.base.call. One function per external system (all MOCK in this build):
SHCIL e-stamp, DigiLocker, ICAI UDIN, state fire NOC portal, state occupancy portal, mandatory-disclosure website, geo footprints."""
import re
from urllib.parse import quote

from app.adapters.base import Result, call


def shcil_estamp(cert_no: str) -> Result:
    return call("SHCIL e-stamp (MOCK)", "/shcil/verify", cert_no=cert_no)


def digilocker(uri: str) -> Result:
    return call("DigiLocker (MOCK)", f"/digilocker/issued/{quote(uri, safe='')}")


def icai_udin(udin: str) -> Result:
    return call("ICAI UDIN (MOCK)", "/udin/verify", udin=udin)


def state_slug(state: str) -> str:
    return re.sub(r"[^a-z]", "", state.lower())


def fire_noc(state: str, cert_no: str) -> Result:
    return call(f"{state} fire NOC portal (MOCK)", f"/fire/{state_slug(state)}/verify", cert_no=cert_no)


def occupancy(state: str, cert_no: str) -> Result:
    return call(f"{state} occupancy certificate portal (MOCK)", f"/occupancy/{state_slug(state)}/verify", cert_no=cert_no)


def website_disclosure(slug: str) -> dict | None:
    """Fetch and parse the institution's mandatory-disclosure page. The URL comes from configuration + the institution slug,
    never from the (untrusted) application form."""
    res = call("Institution website (MOCK)", f"/web/{quote(slug)}/mandatory-disclosure")
    html = (res.body or {}).get("text")
    if res.http_status != 200 or not html:
        return None
    cell = lambda i: (re.search(rf"id='{i}'>([^<]*)<", html) or [None, None])[1]
    return dict(intake_total=int(cell("intake") or 0), faculty_total=int(cell("faculty") or 0), accreditation=cell("accreditation"), source=res.source)


def geo_footprints(campus_id: str) -> Result:
    return call("Building footprint dataset (MOCK)", f"/geo/footprints/{quote(campus_id)}")
