from app.services.engines import SEVERITY_WEIGHT


def score_flags(flags: list[dict]) -> tuple[float, str, list[str]]:
    """flags: list of dicts with severity, confidence, forensic, status, message."""
    contributions = []
    for f in flags:
        if f.get("status") == "DISMISSED":
            continue
        weight = SEVERITY_WEIGHT.get(f["severity"], 0)
        mult = f["confidence"] if f.get("forensic") else 1.0
        contrib = round(weight * mult, 2)
        contributions.append((contrib, f["message"], f["severity"]))

    score = round(sum(c for c, _, _ in contributions), 2)
    has_critical = any(sev == "CRITICAL" for _, _, sev in contributions)
    has_major = any(sev == "MAJOR" for _, _, sev in contributions)

    if has_critical or score >= 60:
        tier = "RED"
    elif has_major or score >= 20:
        tier = "AMBER"
    else:
        tier = "GREEN"

    top = sorted(contributions, key=lambda c: -c[0])[:6]
    top_reasons = [f"{msg} (+{c})" for c, msg, _ in top if c > 0]
    return score, tier, top_reasons
