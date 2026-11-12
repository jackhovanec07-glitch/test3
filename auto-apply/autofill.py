"""
Fill out one internship application in Chrome, then hand it to Jack to check and submit.

  python autofill.py ID

Opens the application form in a Chrome window, fills in the standard fields from
private/profile.json, uploads the resume, and pastes the cover letter. It NEVER presses
Submit: Jack reviews everything, answers anything it couldn't, and submits. When the page
shows a "thank you for applying" message, the internship is marked Applied automatically.
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agent  # noqa: E402

PROFILE = os.path.join(agent.PRIVATE, "profile.json")
BROWSER_PROFILE = os.path.join(agent.DATA, "chrome-profile")
DECLINE = re.compile(r"decline|prefer not|don.?t wish|do not wish|not to (say|answer|disclose)|choose not", re.I)
SUBMITTED = re.compile(r"thank(s| you) for (applying|your application)|application (has been |was )?"
                       r"(submitted|received)|we.?ve received your application|successfully submitted", re.I)


def apply_url(q):
    if q["ats"] == "greenhouse":
        return f"https://job-boards.greenhouse.io/{q['slug']}/jobs/{q['job_id']}"
    if q["ats"] == "lever":
        return q["url"].rstrip("/") + "/apply"
    if q["ats"] == "ashby":
        return f"https://jobs.ashbyhq.com/{q['slug']}/{q['job_id']}/application"
    return q["url"]


def rules(p, letter):
    """(label pattern, answer) in priority order. Answers starting with '=' pick a select/radio option."""
    full = f"{p['first_name']} {p['last_name']}"
    return [
        (r"cover letter", letter),
        (r"additional information|anything else|comments", letter),
        (r"preferred (first )?name|nickname", p["preferred_name"]),
        (r"first name|given name", p["first_name"]),
        (r"last name|surname|family name", p["last_name"]),
        (r"^(full |legal )?name\b|full name|legal name", full),
        (r"e-?mail", p["email"]),
        (r"phone|mobile", p["phone"]),
        (r"linkedin", p["linkedin"]),
        (r"website|portfolio|personal (site|url)", p["website"]),
        (r"gender|race|ethnic|hispanic|latin|veteran|disab|sexual orientation|transgender|pronoun", "=decline"),
        (r"sponsor", "=No"),
        (r"authori[sz]ed to work|legally (eligible|authori[sz]ed)|eligible to work|right to work", "=Yes"),
        (r"relocat", "=Yes"),
        (r"18 years|over 18|at least 18", "=Yes"),
        (r"how did you hear|where did you (hear|find)|referral source|^source", p["how_did_you_hear"]),
        (r"graduation.*year|year of graduation|grad year", p["graduation_year"]),
        (r"graduation.*month", p["graduation_month"]),
        (r"graduat", p["graduation"]),
        (r"\bgpa\b|grade point", p["gpa"]),
        (r"school|university|college|institution", p["school"]),
        (r"degree", p["degree"]),
        (r"major|discipline|field of study|area of study", p["major"]),
        (r"current (company|employer)|^company$|organization", p["school"]),
        (r"country", p["country"]),
        (r"\bcity\b", p["city"]),
        (r"^state\b|state/province|province", p["state"]),
        (r"location|where are you (based|located)|address", f"{p['city']}, {p['state']}"),
    ]


LABEL_JS = """
el => {
  const clean = s => (s || '').replace(/\\s+/g, ' ').replace(/\\*/g, '').trim();
  if (el.getAttribute('aria-label')) return clean(el.getAttribute('aria-label'));
  const by = el.getAttribute('aria-labelledby');
  if (by) { const t = by.split(' ').map(i => document.getElementById(i)).filter(Boolean).map(n => n.innerText).join(' '); if (clean(t)) return clean(t); }
  if (el.id) { const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]'); if (l) return clean(l.innerText); }
  const wrap = el.closest('label'); if (wrap) return clean(wrap.innerText);
  let n = el.parentElement;
  for (let i = 0; i < 4 && n; i++, n = n.parentElement) {
    const l = n.querySelector('label, legend, .application-label, [class*="label"]');
    if (l && clean(l.innerText)) return clean(l.innerText);
  }
  return clean(el.getAttribute('placeholder') || el.getAttribute('name') || '');
}
"""


def answer_for(label, table):
    low = label.lower()
    for pattern, value in table:
        if re.search(pattern, low):
            return value
    return None


def pick_option(options, value):
    """Index of the option that fits a '=Yes' / '=No' / '=decline' answer."""
    want = value[1:]
    for i, o in enumerate(options):
        t = o.strip()
        if want == "decline" and DECLINE.search(t):
            return i
        if want in ("Yes", "No") and re.match(rf"{want}\b", t, re.I):
            return i
    return None


def fill_page(page, profile, letter, resume, letter_file):
    table = rules(profile, letter)
    filled, missed = [], []

    # File uploads: resume, and the cover letter where only a file is accepted
    for inp in page.query_selector_all("input[type=file]"):
        try:
            label = (page.evaluate(LABEL_JS, inp) + " " + (inp.get_attribute("id") or "") + " " + (inp.get_attribute("name") or "")).lower()
            if "cover" in label:
                # Greenhouse lets you type it instead: prefer that
                group = inp.evaluate_handle("e => e.closest('div[class*=\"file-upload\"], fieldset, .field') || e.parentElement")
                manual = group.as_element().query_selector("button:has-text('Enter manually')") if group.as_element() else None
                if manual:
                    manual.click()
                    page.wait_for_timeout(400)
                else:
                    inp.set_input_files(letter_file)
                    filled.append("Cover letter (file)")
            elif resume:
                inp.set_input_files(resume)
                filled.append("Resume")
                resume = None  # only the first resume box
        except Exception:
            continue
    page.wait_for_timeout(800)

    # Text boxes, dropdowns and comboboxes
    for el in page.query_selector_all("input:not([type=hidden]):not([type=file]):not([type=checkbox]):not([type=radio]):not([type=submit]), textarea, select"):
        try:
            if not el.is_visible() or (el.input_value() or "").strip():
                continue
            label = page.evaluate(LABEL_JS, el)
            value = answer_for(label, table)
            if value is None:
                if label:
                    missed.append(label[:80])
                continue
            tag = el.evaluate("e => e.tagName.toLowerCase()")
            if tag == "select":
                options = el.evaluate("e => [...e.options].map(o => o.text)")
                idx = pick_option(options, value) if value.startswith("=") else next(
                    (i for i, o in enumerate(options) if value.lower() in o.lower()), None)
                if idx is None:
                    missed.append(label[:80]); continue
                el.select_option(index=idx)
            elif el.get_attribute("role") == "combobox" or el.get_attribute("aria-autocomplete"):
                el.click()
                typed = {"=Yes": "Yes", "=No": "No", "=decline": "Decline"}.get(value, value)
                el.fill(typed)
                page.wait_for_timeout(700)
                opts = page.query_selector_all("[role=option]")
                texts = [o.inner_text() for o in opts]
                idx = pick_option(texts, value) if value.startswith("=") else (0 if opts else None)
                if idx is None:
                    page.keyboard.press("Escape"); missed.append(label[:80]); continue
                opts[idx].click()
            else:
                if value.startswith("="):
                    missed.append(label[:80]); continue
                el.fill(value)
            filled.append(label[:60])
        except Exception:
            continue

    # Radio buttons (yes/no and demographic questions)
    seen = set()
    for r in page.query_selector_all("input[type=radio]"):
        try:
            name = r.get_attribute("name")
            if not name or name in seen:
                continue
            seen.add(name)
            group = page.query_selector_all(f'input[type=radio][name="{name}"]')
            question = r.evaluate("e => (e.closest('fieldset')?.querySelector('legend')?.innerText || e.closest('fieldset, [role=radiogroup], .field, li')?.innerText || '').slice(0, 300)")
            value = answer_for(question.split("\n")[0], table)
            if not value or not value.startswith("="):
                continue
            labels = [page.evaluate(LABEL_JS, g) for g in group]
            idx = pick_option(labels, value)
            if idx is not None:
                group[idx].check(force=True)
                filled.append(question.split("\n")[0][:60])
        except Exception:
            continue
    return filled, missed


def mark_applied(jid):
    queue = agent.load(agent.QUEUE, {})
    if jid in queue and queue[jid]["status"] != "applied":
        queue[jid].update({"status": "applied", "applied_on": agent.today()})
        agent.save(agent.QUEUE, queue)


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python autofill.py ID")
    jid = sys.argv[1]
    q = agent.load(agent.QUEUE, {}).get(jid)
    if not q:
        sys.exit(f"No internship with id {jid}")
    with open(PROFILE, encoding="utf-8") as f:
        profile = json.load(f)
    letter_file = os.path.join(agent.LETTERS, f"{jid}.txt")
    letter = open(letter_file, encoding="utf-8").read().strip() if os.path.exists(letter_file) else ""
    resume = os.path.join(agent.PRIVATE, profile["resume_file"])
    resume = resume if os.path.exists(resume) else None

    from playwright.sync_api import sync_playwright

    print(f"\n  {q['company']} — {q['title']}\n  Opening the application in Chrome…\n")
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(BROWSER_PROFILE, channel="chrome", headless=False,
                                                    no_viewport=True, args=["--start-maximized"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(apply_url(q), wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        # Lever/Ashby sometimes show the posting first with an Apply button
        for text in ("Apply for this job", "Apply"):
            btn = page.query_selector(f"a:has-text('{text}'), button:has-text('{text}')")
            if btn and not page.query_selector("input[type=file]"):
                try:
                    btn.click(); page.wait_for_timeout(2500)
                except Exception:
                    pass
                break

        filled, missed = fill_page(page, profile, letter, resume, letter_file)
        print("  Filled in:")
        for f in filled:
            print("   ✓", f)
        if missed:
            print("\n  Please answer these yourself:")
            for m in dict.fromkeys(missed):
                print("   •", m)
        print("\n  Check every answer, then press Submit in Chrome.")
        print("  This window marks it Applied when the confirmation page appears. Close Chrome when you're done.\n")

        # Count the confirmation message only if it wasn't already on the form page
        try:
            already = len(SUBMITTED.findall(page.inner_text("body", timeout=3000) or ""))
        except Exception:
            already = 0
        deadline = time.time() + 2 * 60 * 60
        while time.time() < deadline:
            try:
                if not ctx.pages:
                    break
                for pg in ctx.pages:
                    if len(SUBMITTED.findall(pg.inner_text("body", timeout=2000) or "")) > (already if pg is page else 0):
                        mark_applied(jid)
                        print("  ✓ Submitted — marked as Applied. You can close Chrome.")
                        deadline = 0
                        break
                time.sleep(2)
            except Exception:
                if not ctx.pages:
                    break
                time.sleep(2)
        try:
            ctx.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
