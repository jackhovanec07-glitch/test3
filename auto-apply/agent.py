"""
Auto Apply Internships agent: finds business internships and keeps the application queue.

Job sources (public job-board feeds, no scraping, no logins):
  Greenhouse  https://boards-api.greenhouse.io/v1/boards/<company>/jobs
  Lever       https://api.lever.co/v0/postings/<company>
  Ashby       https://api.ashbyhq.com/posting-api/job-board/<company>
Companies come from Hunter.io's free "discover" search for the chosen city (no credits used)
plus a starter list of firms that hire business interns (seeds.json).

Commands (all print JSON):
  python agent.py settings                       current settings
  python agent.py find                           search for new matching internships
  python agent.py show ID                        full posting text, for writing a cover letter
  python agent.py ready ID --employees X --about "..." --pay "..." --letter-file F
  python agent.py skip ID --reason "..."
  python agent.py unsynced                       rows the Google Sheet still needs (new or changed)
  python agent.py synced ID [--row N]            record that the sheet row is up to date
  python agent.py status                         counts by status

Private data (profile, resume, cover letters, queue) lives in private/ and data/, which are
never uploaded to GitHub.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PRIVATE = os.path.join(HERE, "private")
LETTERS = os.path.join(PRIVATE, "letters")
SETTINGS = os.path.join(DATA, "settings.json")
QUEUE = os.path.join(DATA, "queue.json")
COMPANIES = os.path.join(DATA, "companies.json")
SEEDS = os.path.join(HERE, "seeds.json")
HUNTER_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), "test_1", "internship-agent")

DEFAULT_SETTINGS = {"agent_on": False, "location": "Indianapolis, IN", "remote_ok": True,
                    "daily_limit": 8, "sheet_id": "", "sheet_url": ""}
HEADCOUNTS = ["1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001+"]
NEW_PROBES_PER_RUN = 200
UA = {"User-Agent": "internship-finder (personal use)"}

INTERN = re.compile(r"\b(intern|interns|internship|co-?op|summer analyst|summer associate)\b", re.I)
BUSINESS = re.compile(
    r"business|financ|analyst|operations|strateg|consult|marketing|sales|investment|invest|venture|capital|"
    r"account|supply chain|procurement|corporate development|corp ?dev|product manag|growth|partnership|"
    r"revenue|people|human resources|\bhr\b|econom|commercial|brand|communications|real estate|"
    r"private equity|banking|trading|risk|audit|\btax\b|merchandis|customer success|bizops|program manag|"
    r"general management|leadership|rotational|associate", re.I)
NOT_BUSINESS = re.compile(
    r"software|engineer|developer|data scien|machine learning|\bml\b|research scien|ph\.?d|mechanical|"
    r"electrical|hardware|firmware|design|\bux\b|scien|research|nurse|clinical|pharmac|chemist|biolog|"
    r"lab tech|it support|security|legal|counsel", re.I)
GENERIC_INTERN = re.compile(r"^\W*(summer\s+)?(\d{4}\s+)?(intern|internship|summer intern(ship)?)\b", re.I)
OLD_YEAR = re.compile(r"\b(2024|2025|2026)\b")
PAY_HINT = re.compile(r"(\$\s?\d[\d,.]*\s?(k|/hr|/hour| per hour| an hour|/week| per week|/month)?|stipend|"
                      r"housing|relocation|unpaid|paid internship|hourly rate|compensation)", re.I)


# ---------- small helpers ----------
def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def settings():
    s = dict(DEFAULT_SETTINGS)
    s.update(load(SETTINGS, {}))
    return s


def get_json(url, method="GET", body=None, timeout=25):
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(UA, **({"Content-Type": "application/json"} if body is not None else {}))
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def text_of(markup):
    t = html.unescape(html.unescape(markup or ""))  # Greenhouse escapes its HTML twice
    t = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n\n", t).strip()


def today():
    return dt.date.today().isoformat()


# ---------- job boards ----------
def board_jobs(ats, slug):
    """All open jobs on one company's board, in one common shape."""
    out = []
    if ats == "greenhouse":
        d = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
        for j in d.get("jobs", []):
            out.append({"job_id": str(j["id"]), "title": j.get("title", ""),
                        "location": (j.get("location") or {}).get("name", ""),
                        "url": j.get("absolute_url", ""), "remote": False,
                        "text": text_of(j.get("content")), "pay": ""})
    elif ats == "lever":
        d = get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
        for j in d:
            cat = j.get("categories") or {}
            sal = j.get("salaryRange") or {}
            pay = f"${sal['min']:,}–${sal['max']:,} {sal.get('interval', '')}".strip() if sal.get("min") else ""
            extra = "\n".join(f"{l.get('text', '')}\n{text_of(l.get('content'))}" for l in j.get("lists") or [])
            out.append({"job_id": j["id"], "title": j.get("text", ""),
                        "location": cat.get("location", "") or ", ".join(cat.get("allLocations") or []),
                        "url": j.get("hostedUrl", ""), "remote": j.get("workplaceType") == "remote",
                        "text": "\n\n".join(filter(None, [j.get("descriptionPlain"), extra, j.get("additionalPlain")])),
                        "pay": pay})
    elif ats == "ashby":
        d = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
        for j in d.get("jobs", []):
            comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
            locs = [j.get("location") or ""] + [a.get("location", "") for a in j.get("secondaryLocations") or []]
            out.append({"job_id": j["id"], "title": j.get("title", ""), "location": "; ".join(filter(None, locs)),
                        "url": j.get("jobUrl", ""), "remote": bool(j.get("isRemote")),
                        "text": j.get("descriptionPlain") or text_of(j.get("descriptionHtml")), "pay": comp})
    return out


def probe(slug):
    """Which job board (if any) this company slug uses."""
    for ats, url in (("greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{slug}"),
                     ("lever", f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=1"),
                     ("ashby", f"https://api.ashbyhq.com/posting-api/job-board/{slug}")):
        try:
            d = get_json(url, timeout=15)
        except (urllib.error.URLError, ValueError, TimeoutError, OSError):
            continue
        if ats == "greenhouse":
            return ats, d.get("name", "")
        if ats == "lever" and isinstance(d, list) and d:
            return ats, ""
        if ats == "ashby" and isinstance(d, dict) and "jobs" in d:
            return ats, ""
    return None, ""


def slug_guesses(domain, name):
    base = domain.split(".")[0].lower()
    guesses = [base, base.replace("-", ""), re.sub(r"[^a-z0-9]", "", (name or "").lower())]
    return [g for i, g in enumerate(guesses) if g and g not in guesses[:i]]


def same_company(board_name, name):
    if not board_name or not name:
        return True
    words = lambda s: {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2} - {"inc", "llc", "the", "company", "group"}
    return bool(words(board_name) & words(name))


# ---------- finding companies ----------
def parse_location(loc):
    loc = (loc or "").strip()
    if loc.lower() in ("", "anywhere"):
        return "anywhere", None, None
    if loc.lower() == "remote":
        return "remote", None, None
    parts = [p.strip() for p in loc.split(",")]
    return "city", parts[0], (parts[1].upper() if len(parts) > 1 else None)


def discover_companies(city, state, companies, progress):
    """Free Hunter search for companies headquartered in the city, one page per size bucket per run."""
    sys.path.insert(0, HUNTER_DIR)
    try:
        import hunter
    except ImportError:
        return []
    key = f"{city},{state}".lower()
    new = []
    for bucket in HEADCOUNTS:
        offset = progress.get(key, {}).get(bucket, 0)
        if offset < 0:
            continue  # this bucket is finished
        body = {"headquarters_location": {"include": [dict({"country": "US", "city": city}, **({"state": state} if state else {}))]},
                "headcount": [bucket]}
        try:
            r = hunter.request("POST", "discover", params={"limit": 100, "offset": offset}, body=body)
        except SystemExit:
            continue
        found = r.get("data", [])
        total = (r.get("meta") or {}).get("results") or 0
        progress.setdefault(key, {})[bucket] = offset + 100 if offset + 100 < total else -1
        for c in found:
            if not hunter.looks_like_business(c):
                continue
            dom = (c.get("domain") or "").lower()
            entry = companies.setdefault(dom, {"name": c.get("organization") or dom})
            entry["employees"] = bucket
            entry.setdefault("cities", [])
            if key not in entry["cities"]:
                entry["cities"].append(key)
            if "ats" not in entry:
                new.append(dom)
    return new


def cmd_find(_):
    s = settings()
    mode, city, state = parse_location(s["location"])
    companies = load(COMPANIES, {})
    progress = companies.pop("_discover_progress", {})
    for seed in load(SEEDS, {}).get("companies", []):
        e = companies.setdefault(seed["domain"], {"name": seed["name"]})
        e.update({"ats": seed["ats"], "slug": seed["slug"], "seed": True})
        if seed.get("employees"):
            e["employees"] = seed["employees"]

    to_probe = []
    if mode == "city":
        to_probe = discover_companies(city, state, companies, progress)
    to_probe += [d for d, c in companies.items() if "ats" not in c and d not in to_probe]
    to_probe = to_probe[:NEW_PROBES_PER_RUN]

    def check(dom):
        c = companies[dom]
        for g in slug_guesses(dom, c.get("name")):
            ats, board_name = probe(g)
            if ats and same_company(board_name, c.get("name")):
                return dom, ats, g
        return dom, None, None

    with ThreadPoolExecutor(16) as ex:
        for dom, ats, slug in ex.map(check, to_probe):
            companies[dom].update({"ats": ats, "slug": slug, "checked": today()})

    # Which boards to read this run
    key = f"{city},{state}".lower() if mode == "city" else None
    boards = [(d, c) for d, c in companies.items()
              if c.get("ats") and (mode != "city" or c.get("seed") or key in c.get("cities", []))]

    queue = load(QUEUE, {})
    added = []

    def read(item):
        dom, c = item
        try:
            return dom, c, board_jobs(c["ats"], c["slug"])
        except (urllib.error.URLError, ValueError, TimeoutError, OSError, KeyError):
            return dom, c, []

    with ThreadPoolExecutor(16) as ex:
        for dom, c, jobs in ex.map(read, boards):
            for j in jobs:
                title, loc = j["title"], j["location"]
                if not INTERN.search(title) or NOT_BUSINESS.search(title):
                    continue
                if not (BUSINESS.search(title) or (GENERIC_INTERN.search(title) and BUSINESS.search(j["text"][:800]))):
                    continue
                if OLD_YEAR.search(title) and "2027" not in title:
                    continue
                remote = j["remote"] or "remote" in loc.lower()
                if mode == "remote" and not remote:
                    continue
                if mode == "city" and city.lower() not in loc.lower() and not (s["remote_ok"] and remote):
                    continue
                jid = f"{c['ats']}-{c['slug']}-{j['job_id']}"
                if jid in queue:
                    continue
                hints = sorted({m.group(0).strip() for m in PAY_HINT.finditer(j["text"])})[:6]
                queue[jid] = {"id": jid, "status": "found", "found_on": today(), "company": c.get("name", dom),
                              "domain": dom, "ats": c["ats"], "slug": c["slug"], "job_id": j["job_id"],
                              "title": title, "location": loc or ("Remote" if remote else ""), "remote": remote,
                              "url": j["url"], "pay": j["pay"], "pay_hints": hints,
                              "employees": c.get("employees", ""), "about": "", "sheet": {}}
                added.append(jid)

    companies["_discover_progress"] = progress
    save(COMPANIES, companies)
    save(QUEUE, queue)

    def score(jid):
        t = (queue[jid]["title"] + " " + queue[jid]["company"]).lower()
        return -sum(w in t for w in ("venture", "capital", "consult", "strategy", "invest", "private equity",
                                      "corporate development", "business operations", "analyst"))
    added.sort(key=score)
    print(json.dumps({"location": s["location"], "companies_checked": len(to_probe), "boards_read": len(boards),
                      "new_internships": [{k: queue[i][k] for k in ("id", "company", "title", "location", "pay",
                                                                      "pay_hints", "employees", "url")} for i in added],
                      "waiting_from_before": [i for i, q in queue.items() if q["status"] == "found" and i not in added]},
                     indent=2))


def find_job(queue, jid):
    if jid not in queue:
        sys.exit(json.dumps({"error": f"No internship with id {jid}"}))
    return queue[jid]


def cmd_show(a):
    q = find_job(load(QUEUE, {}), a.id)
    try:
        job = next((j for j in board_jobs(q["ats"], q["slug"]) if j["job_id"] == q["job_id"]), None)
    except (urllib.error.URLError, ValueError, OSError):
        job = None
    print(json.dumps({**{k: v for k, v in q.items() if k != "sheet"},
                      "still_open": job is not None,
                      "posting_text": (job or {}).get("text", "")[:12000]}, indent=2))


def cmd_ready(a):
    queue = load(QUEUE, {})
    q = find_job(queue, a.id)
    os.makedirs(LETTERS, exist_ok=True)
    with open(a.letter_file, encoding="utf-8") as f:
        letter = f.read().strip()
    with open(os.path.join(LETTERS, f"{a.id}.txt"), "w", encoding="utf-8") as f:
        f.write(letter + "\n")
    q.update({"status": "ready", "ready_on": today(), "employees": a.employees or q.get("employees", ""),
              "about": a.about, "pay": a.pay or q.get("pay", "")})
    save(QUEUE, queue)
    print(json.dumps({"ok": True, "id": a.id, "status": "ready"}))


def cmd_skip(a):
    queue = load(QUEUE, {})
    q = find_job(queue, a.id)
    q.update({"status": "skipped", "skip_reason": a.reason, "skipped_on": today()})
    save(QUEUE, queue)
    print(json.dumps({"ok": True, "id": a.id, "status": "skipped"}))


SHEET_STATUS = {"ready": "Ready for you", "filling": "Ready for you", "applied": "Applied"}


def cmd_unsynced(_):
    """Rows to add or update in the Google Sheet (skipped jobs are never added)."""
    rows = []
    for q in load(QUEUE, {}).values():
        status = SHEET_STATUS.get(q["status"])
        if not status:
            continue
        if q["sheet"].get("status") == status:
            continue
        rows.append({"id": q["id"], "row": q["sheet"].get("row"), "values": [
            q.get("ready_on") or q["found_on"], q["company"], q["title"], q["location"], q.get("employees", ""),
            q.get("about", ""), q.get("pay", ""), q["url"], status, q.get("applied_on", "")]})
    print(json.dumps({"sheet_url": settings()["sheet_url"], "columns": [
        "Date", "Company", "Position", "Location", "Employees", "What they do", "Pay", "Link", "Status", "Applied on"],
        "rows": rows}, indent=2))


def cmd_synced(a):
    queue = load(QUEUE, {})
    q = find_job(queue, a.id)
    q["sheet"] = {"status": SHEET_STATUS.get(q["status"], q["status"]), "row": a.row or q["sheet"].get("row")}
    save(QUEUE, queue)
    print(json.dumps({"ok": True}))


def cmd_status(_):
    counts = {}
    for q in load(QUEUE, {}).values():
        counts[q["status"]] = counts.get(q["status"], 0) + 1
    applied_today = sum(1 for q in load(QUEUE, {}).values() if q.get("ready_on") == today())
    print(json.dumps({"settings": settings(), "counts": counts, "made_ready_today": applied_today}, indent=2))


def cmd_settings(_):
    print(json.dumps(settings(), indent=2))


def main():
    p = argparse.ArgumentParser(description="Auto Apply Internships agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("settings")
    sub.add_parser("find")
    sub.add_parser("status")
    sub.add_parser("unsynced")
    sh = sub.add_parser("show"); sh.add_argument("id")
    r = sub.add_parser("ready"); r.add_argument("id"); r.add_argument("--employees", default="")
    r.add_argument("--about", required=True); r.add_argument("--pay", default=""); r.add_argument("--letter-file", required=True)
    sk = sub.add_parser("skip"); sk.add_argument("id"); sk.add_argument("--reason", required=True)
    sy = sub.add_parser("synced"); sy.add_argument("id"); sy.add_argument("--row", type=int)
    a = p.parse_args()
    {"settings": cmd_settings, "find": cmd_find, "show": cmd_show, "ready": cmd_ready, "skip": cmd_skip,
     "unsynced": cmd_unsynced, "synced": cmd_synced, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    main()
