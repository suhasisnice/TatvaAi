"""Safe rule evaluation (simpleeval, never eval) against a context built from the evidence graph.

evaluate_pack(pack, ctx) -> list of results:
  {rule_id, scope, status PASS|FAIL|INSUFFICIENT_EVIDENCE, severity, code, title, message, inputs, computed, citation, details}
"""
import ast
import math
import re
from difflib import SequenceMatcher

from simpleeval import EvalWithCompoundTypes, InvalidExpression, NameNotDefined

FUNCS = {"ceil": math.ceil, "floor": math.floor, "min": min, "max": max, "sum": sum, "len": len, "abs": abs, "round": round}
REQ_CODES = {"dsc_valid": ("DOC_UNSIGNED", "not digitally signed"), "estamp_value_100": ("FIELD_MISSING", "not on Rs 100 e-stamp paper")}
ABBREV = {"inst": "institute", "tech": "technology", "engg": "engineering", "coll": "college", "univ": "university", "&": "and", "st": "saint"}


def _ev(expr, names: dict):
    return EvalWithCompoundTypes(names=names, functions=FUNCS).eval(str(expr))


def _names_in(exprs, ctx) -> set:
    out = set()
    for e in exprs:
        out |= {n.id for n in ast.walk(ast.parse(str(e), mode="eval")) if isinstance(n, ast.Name) and n.id in ctx}
    return out


def render(msg: str, names: dict) -> str:
    def sub(m):
        try:
            v = _ev(m.group(1), names)
            return f"{v:g}" if isinstance(v, float) else str(v)
        except Exception:
            return m.group(0)
    return re.sub(r"\{([^{}]+)\}", sub, msg)


def matches_scope(applies: dict, ctx: dict, group: dict | None) -> bool:
    for k, want in applies.items():
        have = (group or {}).get(k, ctx.get(k))
        if have is None and k in ("programme", "level"):
            return False
        if have not in (want if isinstance(want, list) else [want]):
            return False
    return True


def normalise(s: str) -> str:
    toks = re.sub(r"[^a-z0-9& ]+", " ", str(s).lower()).split()
    return " ".join(ABBREV.get(t, t) for t in toks)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalise(a), normalise(b)).ratio()


def _result(rule, status, scope=None, message="", inputs=None, computed=None, details=None) -> dict:
    return dict(rule_id=rule["id"], scope=scope, status=status, severity=rule["severity"], code=rule.get("code"), title=rule["title"],
                message=message, inputs=inputs or {}, computed=computed or {}, citation=rule["citation"], details=details or {})


def evaluate_formula(rule, ctx, scope=None) -> dict:
    names = dict(ctx)
    exprs = list((rule.get("let") or {}).values()) + [rule["check"]]
    try:
        computed = {}
        for k, e in (rule.get("let") or {}).items():
            names[k] = computed[k] = _ev(e, names)
        ok = bool(_ev(rule["check"], names))
    except NameNotDefined as e:
        return _result(rule, "INSUFFICIENT_EVIDENCE", scope, f"Missing evidence: {e.name}", details={"missing": e.name})
    except (TypeError, KeyError, InvalidExpression) as e:  # unsafe/unsupported expression is refused, never executed
        return _result(rule, "INSUFFICIENT_EVIDENCE", scope, f"Evidence unusable: {e}")
    inputs = {n: ctx[n] for n in sorted(_names_in(exprs, ctx))}
    return _result(rule, "PASS" if ok else "FAIL", scope, render(rule["message"], names), inputs, computed)


def evaluate_document_required(rule, ctx) -> dict:
    docs = ctx["docs"].get(rule["document_type"], [])
    if not docs:
        return _result(rule, "FAIL", message=render(rule["message"], {**ctx, "document_type": rule["document_type"], "problem": "missing"}),
                       details={"problem": "missing", "code": "DOC_MISSING"})
    failing = [(r, d) for d in docs for r in rule.get("requires", []) if not d["checks"].get(r)]
    if failing:
        r, d = failing[0]
        code, problem = REQ_CODES.get(r, ("FIELD_MISSING", f"failing requirement {r}"))
        return _result(rule, "FAIL", message=render(rule["message"], {"document_type": rule["document_type"], "problem": problem}),
                       details={"problem": problem, "code": code, "document_id": d["id"]})
    return _result(rule, "PASS", message="Present and valid", details={"document_ids": [d["id"] for d in docs]})


def evaluate_field_required(rule, ctx) -> dict:
    docs = ctx["docs"].get(rule["document_type"], [])
    if not docs:
        return _result(rule, "INSUFFICIENT_EVIDENCE", message=f"{rule['document_type']} not provided")
    missing = [f for d in docs for f in rule["fields"] if not d["fields"].get(f)]
    return _result(rule, "FAIL" if missing else "PASS", message=render(rule["message"], {"missing": ", ".join(missing)}) if missing else "All fields present",
                   details={"missing": missing, "document_id": docs[0]["id"]})


def evaluate_expiry(rule, ctx) -> dict:
    out = []
    ref = ctx.get(rule["valid_on"])
    for d in ctx["docs"].get(rule["document_type"], []):
        v = d["fields"].get(rule["field"])
        if not ref or not v or not re.match(r"\d{4}-\d{2}-\d{2}$", v):
            continue  # perpetual / absent / unparseable -> not an expiry case (completeness reports absent docs)
        if v < ref:
            out.append((d, v))
    if not out:
        return _result(rule, "PASS", message="Valid on the reference date")
    d, v = out[0]
    return _result(rule, "FAIL", message=render(rule["message"], {"valid_till": v, "valid_on": ref}), details={"document_id": d["id"], "valid_till": v, "valid_on": ref})


def evaluate_consistency(rule, ctx) -> dict:
    ref = ctx.get("form_values", {}).get(rule["reference"])
    if ref is None:
        return _result(rule, "INSUFFICIENT_EVIDENCE", message=f"No form value for {rule['reference']}")
    bad = []
    for s in rule["sources"]:
        for d in ctx["docs"].get(s["document_type"], []):
            v = d["fields"].get(s["field"])
            if v is None:
                continue
            sim = similarity(ref, v) if rule["threshold"] < 1.0 else float(normalise(ref) == normalise(v))
            if sim < rule["threshold"]:
                bad.append(dict(document_id=d["id"], document_type=s["document_type"], value=v, similarity=round(sim, 3)))
    msg = render(rule["message"], {"mismatches": "; ".join(f"{b['document_type']}={b['value']!r}" for b in bad)}) if bad else "Consistent"
    return _result(rule, "FAIL" if bad else "PASS", message=msg, inputs={"reference": ref}, details={"mismatches": bad})


def evaluate_pack(pack: dict, ctx: dict, only_types: set | None = None) -> list[dict]:
    results = []
    for rule in pack["rules"]:
        if only_types and rule["type"] not in only_types:
            continue
        applies = rule["applies_to"]
        grouped = "programme" in applies or "level" in applies
        if not grouped and not matches_scope(applies, ctx, None):
            continue
        if rule.get("when"):
            try:
                if not _ev(rule["when"], ctx):
                    continue
            except NameNotDefined:
                continue
        t = rule["type"]
        if grouped:
            for g in ctx["groups"]:
                if matches_scope({**applies}, ctx, g):
                    results.append(evaluate_formula(rule, {**ctx, **g["vars"]}, scope=f"{g['programme']}/{g['level']}"))
        elif t in ("formula", "threshold", "timeline"):
            results.append(evaluate_formula(rule, ctx))
        elif t == "document_required":
            results.append(evaluate_document_required(rule, ctx))
        elif t == "field_required":
            results.append(evaluate_field_required(rule, ctx))
        elif t == "expiry":
            results.append(evaluate_expiry(rule, ctx))
        elif t == "consistency":
            results.append(evaluate_consistency(rule, ctx))
    return results
