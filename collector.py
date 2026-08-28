"""Public-feed collector. No user information is processed or stored here."""
from __future__ import annotations
import json, hashlib, html, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path("jobs.json")
FEEDS = [
    ("greenhouse", "OpenAI", "openai"),
    ("lever", "Postman", "postman"),
    ("ashby", "Notion", "notion"),
]

def get(url: str):
    request = Request(url, headers={"User-Agent": "JobDiscoveryCollector/1.0", "Accept": "application/json"})
    with urlopen(request, timeout=20) as response:
        return json.load(response)

def clean(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).replace("\u00a0", " ")[:100_000]

def job(provider, company, job_id, title, url, description="", location=None, department=None, employment=None, remote=None):
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    key = f"{provider}:{job_id}"
    return {"id": key, "provider": provider, "provider_job_id": str(job_id), "company": company,
        "title": title or "Untitled", "description": clean(description), "city": location,
        "department": department, "employment_type": employment, "remote_status": remote,
        "salary": None, "shift": None, "required_skills": [], "application_url": url,
        "original_url": url, "removed": False}

def greenhouse(company, board):
    data = get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
    return [job("greenhouse", company, x["id"], x.get("title"), x.get("absolute_url"), x.get("content", ""), x.get("location", {}).get("name"), ", ".join(d.get("name", "") for d in x.get("departments", [])).strip() or None, remote="remote" if "remote" in (x.get("location", {}).get("name") or "").lower() else None) for x in data.get("jobs", [])]

def lever(company, site):
    data = get(f"https://api.lever.co/v0/postings/{site}?mode=json")
    return [job("lever", company, x["id"], x.get("text"), x.get("hostedUrl"), x.get("descriptionPlain", ""), x.get("categories", {}).get("location"), x.get("categories", {}).get("team"), x.get("categories", {}).get("commitment"), "remote" if "remote" in (x.get("categories", {}).get("location") or "").lower() else None) for x in data]

def ashby(company, board):
    data = get(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
    return [job("ashby", company, x["id"], x.get("title"), x.get("jobUrl"), x.get("descriptionHtml", ""), x.get("location"), x.get("department"), x.get("employmentType"), "remote" if x.get("isRemote") else None) for x in data.get("jobs", [])]

def main():
    jobs=[]
    for provider, company, board in FEEDS:
        try:
            found = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}[provider](company, board)
            jobs.extend(x for x in found if x)
            print(f"{provider}:{company} jobs={len(found)}")
        except Exception as exc:
            print(f"{provider}:{company} failed: {exc}")
    jobs.sort(key=lambda x: (x["company"], x["title"], x["id"]))
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "cursor": str(int(time.time())), "jobs": jobs}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    if not jobs: raise SystemExit("No provider returned a job; retaining no empty feed")

if __name__ == "__main__": main()
