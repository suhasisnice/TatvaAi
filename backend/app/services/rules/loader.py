"""Rule Pack (Handbook-as-Code): load YAML dir -> pack dict, validate against rulepacks/schema.json, (de)serialise for the DB."""
import ast
import json
from pathlib import Path

import jsonschema
import yaml

RULEPACK_DIR = Path(__file__).resolve().parents[4] / "rulepacks"
if not RULEPACK_DIR.exists():  # docker image layout: /app/rulepacks
    RULEPACK_DIR = Path("/app/rulepacks")
SCHEMA = json.loads((RULEPACK_DIR / "schema.json").read_text())
FILES = ("documents", "norms", "timelines", "risk", "categories")


def load_dir(path: Path) -> dict:
    pack: dict = {"rules": [], "constants": {}}
    for name in FILES:
        f = path / f"{name}.yaml"
        if not f.exists():
            continue
        part = yaml.safe_load(f.read_text()) or {}
        pack["rules"] += part.pop("rules", [])
        pack["constants"].update(part.pop("constants", {}))
        pack.update(part)
    pack["rules"] += category_rules(pack.get("categories", {}))
    return pack


def _expand(categories: dict, cat: str) -> list[dict]:
    spec = categories[cat]
    docs = _expand(categories, spec["inherits"]) if spec.get("inherits") else []
    return docs + spec.get("documents", [])


def category_rules(categories: dict) -> list[dict]:
    """One document_required rule per (category, document type): adding a category needs no rule code."""
    out = []
    for cat in categories:
        for d in _expand(categories, cat):
            r = {"id": f"DOC-{cat}-{d['type']}".replace("_", "-"), "title": f"{d['type'].replace('_', ' ').title()} is required for {cat}",
                 "applies_to": {"category": cat}, "type": "document_required", "document_type": d["type"], "requires": d.get("requires", []),
                 "code": "DOC_MISSING", "severity": d["severity"], "message": "{document_type} is {problem}", "citation": d["citation"]}
            if d.get("when"):
                r["when"] = d["when"]
            out.append(r)
    return out


def validate_pack(pack: dict) -> list[str]:
    """Returns human-readable errors (empty list = valid): schema, duplicate ids, expression syntax."""
    errors = [f"{'/'.join(map(str, e.absolute_path)) or '<pack>'}: {e.message}" for e in jsonschema.Draft7Validator(SCHEMA).iter_errors(pack)]
    seen = set()
    for i, r in enumerate(pack.get("rules", [])):
        rid = r.get("id", f"#{i}")
        if rid in seen:
            errors.append(f"rules/{i}: duplicate rule id {rid}")
        seen.add(rid)
        exprs = [r.get("check"), r.get("when")] + list((r.get("let") or {}).values())
        for e in exprs:
            if isinstance(e, str):
                try:
                    ast.parse(e, mode="eval")
                except SyntaxError as ex:
                    errors.append(f"rules/{i} ({rid}): bad expression {e!r}: {ex.msg}")
    return errors


def dump(pack: dict) -> str:
    return yaml.safe_dump(pack, sort_keys=False, allow_unicode=True)


def parse(blob: str) -> dict:
    return yaml.safe_load(blob)
