from urllib.parse import quote

from app.adapters.base import Result, call


def institution_record(aicte_id: str) -> Result:
    return call("AICTE records (MOCK)", f"/aicte/records/{quote(aicte_id)}")


def faculty_registry(faculty_id: str) -> Result:
    return call("AICTE faculty registry (MOCK)", f"/aicte/faculty-registry/{quote(faculty_id)}")
