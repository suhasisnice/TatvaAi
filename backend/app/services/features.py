"""The product's feature map: the five checking engines roll up into two checking features.

  Feature 1  Handbook rule checker          faculty, rooms, computers, bandwidth, built-up area, certificate dates
  Feature 2  Document & consistency check   genuine? do the facts agree? across documents, years and colleges
  (Feature 3, risk ranking and officer review, is scoring + the review screens, not an engine.)
"""

FEATURE_OF_ENGINE = {"compliance": 1, "completeness": 1, "authenticity": 2, "issuer": 2, "consistency": 2}
FEATURE_LABEL = {1: "Handbook rule checker", 2: "Document & consistency check"}


def feature_of(engine: str) -> int:
    return FEATURE_OF_ENGINE.get(engine, 2)
