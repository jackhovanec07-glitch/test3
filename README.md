# Jack Hovanec — Portfolio

**Live website:** https://jackhovanec07-glitch.github.io/test3/
**Code on GitHub:** https://github.com/jackhovanec07-glitch/test3

A personal portfolio site (plain HTML + CSS, no build step), hosted on GitHub Pages.

## Files
- `index.html` — the page content (edit text here)
- `style.css` — colors and layout (change `--accent` at the top to change the theme color)
- `motion.js` — scroll animations
- `images/` — photos on the page (`lake.jpg`, `lab.jpg`, `volleyball.jpg`)
- `agents.js` — the code box at the bottom and the private "My agents" section
- `agent-server.py` + `Start Agents.bat` — connect the agents section to the agents on this computer

## Agents section
Double-click `Start Agents.bat`. It opens the site at http://127.0.0.1:8765/ — scroll to the
bottom, enter the code, and the networking agent connects. Keep the black window open while using it.

## Auto apply internships agent (`auto-apply/`)
- `agent.py` finds business internships on Greenhouse, Lever and Ashby job boards for the chosen
  location (companies come from Hunter.io's free search plus `seeds.json`).
- `PLAYBOOK.md` is what the daily run follows: review postings, write cover letters, log them in
  the "Auto Apply Internships" Google Sheet.
- `autofill.py` fills an application in Chrome (never presses Submit). Started by the
  "Fill application" button in the agents section.
- Private and never uploaded: `auto-apply/private/` (form answers, resume, cover letters) and
  `auto-apply/data/` (settings, queue, browser profile).

## Updating the live site
Edit the files, then in this folder run `git add .`, `git commit -m "update"`, `git push`.
The live site updates about a minute later (the link stays the same).
