# Auto Apply Internships: daily run playbook

Jack Hovanec (Purdue, Integrated Engineering & Business, graduating December 2029) wants
business internships for **summer 2027**. Long term he wants venture capital or consulting.
This run finds internships, writes a cover letter for each, and logs them in his Google Sheet.
Jack fills and submits each application himself from his website ("Fill application" button).

All commands run in `C:\Users\Jackh\OneDrive\Desktop\Claud\test3\auto-apply` and print JSON.

## Hard rules
- **Never submit an application, create an account, or send an email.** Your job ends at
  "ready" + the sheet row. Jack submits.
- Never invent facts about Jack. Use only the facts below.
- Never print, copy, or move anything in `private/` except writing new cover letters there via
  `agent.py ready`. Never commit `private/` or `data/` to git.

## Steps
1. `python agent.py status`. If `settings.agent_on` is false, stop and report "Agent is off".
   Budget for today = `settings.daily_limit` − `made_ready_today`. If 0, skip to step 5.
2. `python agent.py find`. It returns `new_internships` (best first) plus `waiting_from_before`.
3. Go through the candidates in that order (new ones first, then waiting ones) until the budget is
   used. For each, run `python agent.py show ID` and read `posting_text`. Skip it
   (`python agent.py skip ID --reason "..."`) if any of these is true:
   - `still_open` is false.
   - It isn't a business role (finance, consulting, strategy, operations, marketing, sales,
     analytics, venture/investing, supply chain, business development, etc. all count).
   - It's for graduate, MBA, law, or PhD students, or requires a class year Jack can't meet
     (e.g. "rising seniors only", "graduating in 2027"). "Rising sophomores/juniors" or no
     requirement is fine. When it's unclear, keep it.
   - It's not for summer 2027 (e.g. a spring or fall 2026 term, or a full-time role).
   - It's **unpaid** or for academic credit only, unless housing is provided. No pay listed is fine.
   - The location doesn't fit `settings.location` (or remote when `remote_ok` is true).
   Prefer venture capital, consulting, strategy, corporate development, and finance roles.
4. For each one you keep:
   - **Employees:** use the `employees` value if set (e.g. "201-500"). Otherwise give your best
     approximate figure, e.g. "~3,500".
   - **About:** one sentence on what the company does, in plain words.
   - **Pay:** what the posting says (e.g. "$7,000–$9,500/month + relocation"), else "Not listed".
   - **Cover letter:** 170–250 words, plain text, no address block. Start "Dear Hiring Team,"
     and end "Sincerely,\nJack Hovanec". Name the company and role, mention one or two specific
     things from the posting, and connect them to Jack's real experience below. Confident,
     specific, no clichés, no exaggeration.
   - Save the letter to a temp file and run
     `python agent.py ready ID --employees "..." --about "..." --pay "..." --letter-file PATH`.
5. Sync the Google Sheet (spreadsheet id = `settings.sheet_id`, tab `Applications`, columns A–J):
   `python agent.py unsynced`. For each row:
   - no `row`: append `values` to `Applications!A:J`, read the row number from the updated range,
     then `python agent.py synced ID --row N`.
   - has `row`: update `Applications!A{row}:J{row}` with `values`, then `python agent.py synced ID`.
6. Report: how many found, kept (company + role), skipped (with short reasons), and the sheet link.

## Facts about Jack (for cover letters)
- Purdue University, B.S. Integrated Engineering & Business, expected December 2029, GPA 3.87.
- Roncalli High School (Indianapolis): Academic All-State Gold 2025, All-State Athletic Award 2025,
  2025 IHSAA boys volleyball state champion.
- Purdue EPICS India team (2026–present): product for women in India who make tawas (cooking
  pans); leads semester goals on weight, cost and safety; ANSYS materials analysis; prepares
  design recommendations for nonprofit partners.
- Team Indiana Volleyball Club, positional court coach (2025–26): helped start the club's first
  boys program; recruited players, coordinated team formation, built practice plans.
- Hovanec Law, office intern (2022–present): filing systems, new-client documents, confidentiality.
- Edible Arrangements, seasonal operations assistant (2021–present): holiday delivery routing,
  high-volume orders, customer engagement, workflow efficiency.
- Deany Equipment Company, engineering & shop intern (summer 2024): engine diagnostics with
  master mechanics, parts ordering and delivery logistics, shop workflow and safety.
- Built AI-powered agents for internship outreach and short-form video clipping.
- Interests: venture capital, consulting. Willing to relocate.
