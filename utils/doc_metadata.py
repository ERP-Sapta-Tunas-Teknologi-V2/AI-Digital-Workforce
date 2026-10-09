import re

INDUSTRIES = {"fsi", "manufaktur", "healthcare", "media", "other"}
PERSONAS = {"cio", "manager", "procurement", "staff_it"}
CONTENT_TYPES = {"battlecard", "objection"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def _as_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return value
    raise ValueError("must be a string or list")

def _enum_list(name, value, allowed):
    items = [str(v).strip().lower() for v in _as_list(value)]
    bad = [v for v in items if v not in allowed]
    if bad:
        raise ValueError(f"{name} invalid: {bad}, allowed: {sorted(allowed)}")
    return sorted(set(items))

def _free_list(value):
    return sorted({str(v).strip().lower() for v in _as_list(value) if str(v).strip()})

def normalize_doc_metadata(raw):
    """Validasi & normalisasi. Key di luar skema ditolak agar tidak menimpa metadata chunk (source, page, category, dst.)."""
    if not isinstance(raw, dict):
        raise ValueError("metadata must be an object")

    allowed_keys = {"industry", "persona", "competitor", "products",
                    "content_type", "effective_date"}
    unknown = set(raw) - allowed_keys
    if unknown:
        raise ValueError(f"unknown metadata keys: {sorted(unknown)}")

    out = {}
    if "industry" in raw:
        out["industry"] = _enum_list("industry", raw["industry"], INDUSTRIES)
    if "persona" in raw:
        out["persona"] = _enum_list("persona", raw["persona"], PERSONAS)
    if "competitor" in raw:
        out["competitor"] = _free_list(raw["competitor"])
    if "products" in raw:
        out["products"] = _free_list(raw["products"])
    if raw.get("content_type"):
        ct = str(raw["content_type"]).strip().lower()
        if ct not in CONTENT_TYPES:
            raise ValueError(f"content_type invalid, allowed: {sorted(CONTENT_TYPES)}")
        out["content_type"] = ct
    if raw.get("effective_date"):
        ed = str(raw["effective_date"]).strip()
        if not _DATE_RE.match(ed):
            raise ValueError("effective_date must use YYYY-MM-DD")
        out["effective_date"] = ed
    return out