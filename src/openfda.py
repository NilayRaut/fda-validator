import requests, weave

BASE = "https://api.fda.gov/drug"


def _get(endpoint, params):
    try:
        r = requests.get(f"{BASE}/{endpoint}.json", params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        return {"_error": str(e)}


def _error_from(res) -> str:
    return res.get("_error", "") if isinstance(res, dict) else ""


def _first(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _product_items(res: list) -> list[dict]:
    return [{"brand": x.get("brand_name"), "generic": x.get("generic_name"),
             "manufacturer": x.get("labeler_name"),
             "class": _first(x.get("pharm_class"))} for x in res]


@weave.op
def adverse_events(drug: str, limit: int = 5) -> dict:            # Safety & Efficacy + critic
    res = _get("event", {"search": f'patient.drug.medicinalproduct:"{drug}"',
                         "count": "patient.reaction.reactionmeddrapt.exact"})
    top = res[:limit] if isinstance(res, list) else []
    out = {"drug": drug, "top_reactions": top, "source": "openFDA FAERS (drug/event)"}
    if _error_from(res):
        out["_error"] = _error_from(res)
    return out


@weave.op
def recalls(drug: str, limit: int = 5) -> dict:                  # Safety & Efficacy + critic
    res = _get("enforcement", {"search": f'product_description:"{drug}"', "limit": limit})
    items = [{"reason": x.get("reason_for_recall"), "classification": x.get("classification"),
              "date": x.get("recall_initiation_date")} for x in res] if isinstance(res, list) else []
    out = {"drug": drug, "recalls": items, "source": "openFDA enforcement (drug/enforcement)"}
    if _error_from(res):
        out["_error"] = _error_from(res)
    return out


@weave.op
def approvals(drug: str, limit: int = 5) -> dict:                # Precedent & Market + critic
    res = _get("drugsfda", {"search": f'openfda.brand_name:"{drug}" openfda.generic_name:"{drug}"', "limit": limit})
    apps = [{"application_number": x.get("application_number"), "sponsor": x.get("sponsor_name"),
             "products": [p.get("brand_name") for p in x.get("products", [])]} for x in res] if isinstance(res, list) else []
    out = {"drug": drug, "applications": apps, "source": "openFDA Drugs@FDA (drug/drugsfda)"}
    if _error_from(res):
        out["_error"] = _error_from(res)
    return out


@weave.op
def marketed_products(drug: str, limit: int = 8) -> dict:        # Precedent & Market
    queries = [
        ("generic_name", {"search": f'generic_name:"{drug}"', "limit": limit}),
        ("openfda.generic_name", {"search": f'openfda.generic_name:"{drug}"', "limit": limit}),
        ("brand_name", {"search": f'brand_name:"{drug}"', "limit": limit}),
        ("brand_name.exact", {"search": f'brand_name.exact:"{drug.upper()}"', "limit": limit}),
    ]
    errors = []
    for query_name, params in queries:
        res = _get("ndc", params)
        if isinstance(res, list) and res:
            return {"drug": drug, "products": _product_items(res), "source": "openFDA NDC (drug/ndc)",
                    "query": query_name}
        if _error_from(res):
            errors.append(f"{query_name}: {_error_from(res)}")

    out = {"drug": drug, "products": [], "source": "openFDA NDC (drug/ndc)"}
    if errors:
        out["_error"] = " | ".join(errors)
    return out


@weave.op
def drug_label(drug: str, max_chars: int = 1200) -> dict:        # critic — nonclinical + clinical lenses
    # SPL label sections exist only for APPROVED/marketed drugs. Sections are truncated to keep
    # the critic's prompt token budget sane.
    res = _get("label", {"search": f'openfda.brand_name:"{drug}" openfda.generic_name:"{drug}"', "limit": 1})
    rec = (_first(res) if isinstance(res, list) else None) or {}

    def section(key):
        val = rec.get(key)
        if isinstance(val, list):
            val = " ".join(str(v) for v in val)
        return (val or "")[:max_chars]

    out = {
        "drug": drug,
        "nonclinical_toxicology": section("nonclinical_toxicology"),
        "clinical_pharmacology": section("clinical_pharmacology"),
        "clinical_studies": section("clinical_studies"),
        "warnings": section("warnings") or section("boxed_warning"),
        "source": "openFDA Drug Label (drug/label)",
    }
    if _error_from(res):
        out["_error"] = _error_from(res)
    return out
