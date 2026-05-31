import requests, weave

BASE = "https://api.fda.gov/drug"


def _get(endpoint, params):
    try:
        r = requests.get(f"{BASE}/{endpoint}.json", params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        return {"_error": str(e)}


@weave.op
def adverse_events(drug: str, limit: int = 5) -> dict:            # Safety & Efficacy + critic
    res = _get("event", {"search": f'patient.drug.medicinalproduct:"{drug}"',
                         "count": "patient.reaction.reactionmeddrapt.exact"})
    top = res[:limit] if isinstance(res, list) else []
    return {"drug": drug, "top_reactions": top, "source": "openFDA FAERS (drug/event)"}


@weave.op
def recalls(drug: str, limit: int = 5) -> dict:                  # Safety & Efficacy + critic
    res = _get("enforcement", {"search": f'product_description:"{drug}"', "limit": limit})
    items = [{"reason": x.get("reason_for_recall"), "classification": x.get("classification"),
              "date": x.get("recall_initiation_date")} for x in res] if isinstance(res, list) else []
    return {"drug": drug, "recalls": items, "source": "openFDA enforcement (drug/enforcement)"}


@weave.op
def approvals(drug: str, limit: int = 5) -> dict:                # Precedent & Market + critic
    res = _get("drugsfda", {"search": f'openfda.brand_name:"{drug}" openfda.generic_name:"{drug}"', "limit": limit})
    apps = [{"application_number": x.get("application_number"), "sponsor": x.get("sponsor_name"),
             "products": [p.get("brand_name") for p in x.get("products", [])]} for x in res] if isinstance(res, list) else []
    return {"drug": drug, "applications": apps, "source": "openFDA Drugs@FDA (drug/drugsfda)"}


@weave.op
def marketed_products(drug: str, limit: int = 8) -> dict:        # Precedent & Market
    res = _get("ndc", {"search": f'openfda.generic_name:"{drug}"', "limit": limit})
    items = [{"brand": x.get("brand_name"), "manufacturer": x.get("labeler_name"),
              "class": (x.get("pharm_class") or [None])[0]} for x in res] if isinstance(res, list) else []
    return {"drug": drug, "products": items, "source": "openFDA NDC (drug/ndc)"}


@weave.op
def drug_label(drug: str, max_chars: int = 1200) -> dict:        # critic — nonclinical + clinical lenses
    # SPL label sections exist only for APPROVED/marketed drugs. Each section is truncated to
    # keep the critic's prompt token budget sane.
    res = _get("label", {"search": f'openfda.brand_name:"{drug}" openfda.generic_name:"{drug}"', "limit": 1})
    rec = res[0] if isinstance(res, list) and res else {}

    def section(key):
        val = rec.get(key)
        if isinstance(val, list):
            val = " ".join(str(v) for v in val)
        return (val or "")[:max_chars]

    return {
        "drug": drug,
        "nonclinical_toxicology": section("nonclinical_toxicology"),
        "clinical_pharmacology": section("clinical_pharmacology"),
        "clinical_studies": section("clinical_studies"),
        "warnings": section("warnings") or section("boxed_warning"),
        "source": "openFDA Drug Label (drug/label)",
    }
