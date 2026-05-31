import requests, weave

# ClinicalTrials.gov API v2 (public, no auth). Grounds INVESTIGATIONAL compounds that are
# absent from openFDA (FAERS/Drugs@FDA/NDC cover marketed products only). Fail-soft like openfda.py.
CTGOV = "https://clinicaltrials.gov/api/v2/studies"


@weave.op
def clinical_trials(drug: str, limit: int = 5) -> dict:
    try:
        r = requests.get(CTGOV, params={"query.term": drug, "pageSize": limit}, timeout=15)
        r.raise_for_status()
        studies = r.json().get("studies", [])
    except Exception as e:
        return {"drug": drug, "trials": [], "source": "ClinicalTrials.gov (API v2)", "_error": str(e)}

    trials = []
    for s in studies:
        ps = s.get("protocolSection", {})
        idm = ps.get("identificationModule", {})
        nct = idm.get("nctId")
        trials.append({
            "nct_id": nct,
            "title": idm.get("briefTitle"),
            "status": ps.get("statusModule", {}).get("overallStatus"),
            "phase": ", ".join(ps.get("designModule", {}).get("phases", []) or []),
            "conditions": ", ".join(ps.get("conditionsModule", {}).get("conditions", []) or []),
            "sponsor": ps.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name"),
            "url": f"https://clinicaltrials.gov/study/{nct}" if nct else "",
        })
    return {"drug": drug, "trials": trials, "source": "ClinicalTrials.gov (API v2)"}
