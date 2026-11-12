"""
Local bridge between the website's private "Agents" section and the agents on this computer.

The website is public on GitHub Pages, but the agents (and their keys) stay on this PC.
This server only listens on 127.0.0.1, so it can only be reached from this computer,
and it only answers requests coming from the website itself.

  GET  /api/network            the networking agent's projects + on/off switches
  POST /api/network/toggle     body: {"index": 0, "agent_on": true}
  GET  /api/network/credits    Hunter.io searches / verifications left (runs hunter.py)

Start it with "Start Agents.bat".
"""
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.join(os.path.dirname(HERE), "test_1", "internship-agent")
PROJECTS = os.path.join(AGENT_DIR, "projects.json")
HUNTER = os.path.join(AGENT_DIR, "hunter.py")
APPLY_DIR = os.path.join(HERE, "auto-apply")
sys.path.insert(0, APPLY_DIR)
import agent as apply_agent  # noqa: E402  (auto-apply/agent.py)

PORT = 8765
SITE_FILES = {"/": "index.html", "/index.html": "index.html", "/style.css": "style.css",
              "/agents.js": "agents.js", "/motion.js": "motion.js",
              "/images/lake.jpg": "images/lake.jpg", "/images/lab.jpg": "images/lab.jpg",
              "/images/volleyball.jpg": "images/volleyball.jpg"}
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript",
         ".jpg": "image/jpeg"}
ALLOWED_ORIGINS = {
    "https://jackhovanec07-glitch.github.io",
    "http://127.0.0.1:8765",
    "http://localhost:8765",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
}
_lock = threading.Lock()


def read_projects():
    with open(PROJECTS, encoding="utf-8") as f:
        return json.load(f)


def write_projects(data):
    tmp = PROJECTS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, PROJECTS)


def apply_view():
    """Auto Apply Internships: settings plus the jobs waiting for Jack and the recent ones he applied to."""
    s = apply_agent.settings()
    queue = list(apply_agent.load(apply_agent.QUEUE, {}).values())
    fields = ("id", "company", "title", "location", "employees", "about", "pay", "url", "ready_on", "applied_on")
    ready = sorted((q for q in queue if q["status"] == "ready"), key=lambda q: q.get("ready_on", ""), reverse=True)
    applied = sorted((q for q in queue if q["status"] == "applied"), key=lambda q: q.get("applied_on", ""), reverse=True)
    return {"settings": {k: s[k] for k in ("agent_on", "location", "remote_ok", "daily_limit", "sheet_url")},
            "ready": [{k: q.get(k, "") for k in fields} for q in ready],
            "applied": [{k: q.get(k, "") for k in fields} for q in applied[:10]],
            "applied_count": len(applied),
            "waiting_review": sum(1 for q in queue if q["status"] == "found")}


def public_view(data):
    """Only what the page needs (no playbook paths)."""
    return {"projects": [
        {"name": p.get("name"), "url": p.get("url"), "agent_on": bool(p.get("agent_on"))}
        for p in data.get("projects", [])
    ]}


class Handler(http.server.BaseHTTPRequestHandler):
    def _origin_ok(self):
        return self.headers.get("Origin") in ALLOWED_ORIGINS

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin"))
        self.send_header("Vary", "Origin")

    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        if self._origin_ok():
            self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        if not self._origin_ok():
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in SITE_FILES:  # the website itself, so it also works at http://127.0.0.1:8765
            name = SITE_FILES[path]
            with open(os.path.join(HERE, name), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", TYPES[os.path.splitext(name)[1]])
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        # Browsers send Origin on every cross-site request; none means same page or this PC
        if self.headers.get("Origin") is not None and not self._origin_ok():
            return self._json(403, {"error": "Not allowed"})
        if path == "/api/network":
            with _lock:
                return self._json(200, public_view(read_projects()))
        if path == "/api/network/credits":
            try:
                out = subprocess.run([sys.executable, HUNTER, "credits"], cwd=AGENT_DIR,
                                     capture_output=True, text=True, timeout=60)
                return self._json(200, json.loads(out.stdout))
            except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
                return self._json(502, {"error": "Couldn't check Hunter credits"})
        if path == "/api/apply":
            with _lock:
                return self._json(200, apply_view())
        if path == "/api/apply/letter":
            jid = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("id", [""])[0]
            letter = os.path.join(apply_agent.LETTERS, f"{os.path.basename(jid)}.txt")
            if not os.path.exists(letter):
                return self._json(404, {"error": "No cover letter for that internship"})
            with open(letter, encoding="utf-8") as f:
                return self._json(200, {"id": jid, "letter": f.read()})
        return self._json(404, {"error": "Not found"})

    def do_POST(self):
        if not self._origin_ok():
            return self._json(403, {"error": "Not allowed"})
        path = self.path.split("?")[0]
        try:
            length = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(min(length, 10000)) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "Send JSON"})
        if path == "/api/apply/settings":
            return self._apply_settings(req)
        if path == "/api/apply/mark":
            return self._apply_mark(req)
        if path == "/api/apply/fill":
            return self._apply_fill(req)
        if path != "/api/network/toggle":
            return self._json(404, {"error": "Not found"})
        try:
            index = int(req["index"])
            agent_on = bool(req["agent_on"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return self._json(400, {"error": "Send {\"index\": number, \"agent_on\": true/false}"})
        with _lock:
            data = read_projects()
            if not 0 <= index < len(data["projects"]):
                return self._json(404, {"error": "No project at that index"})
            data["projects"][index]["agent_on"] = agent_on
            write_projects(data)
            return self._json(200, public_view(data))

    # ---------- Auto Apply Internships ----------
    def _apply_settings(self, req):
        with _lock:
            s = apply_agent.settings()
            if "agent_on" in req:
                s["agent_on"] = bool(req["agent_on"])
            if "location" in req:
                loc = str(req["location"]).strip()[:80]
                if not loc:
                    return self._json(400, {"error": "Enter a city, e.g. Indianapolis, IN"})
                s["location"] = loc
            if "remote_ok" in req:
                s["remote_ok"] = bool(req["remote_ok"])
            if "daily_limit" in req:
                try:
                    s["daily_limit"] = max(1, min(10, int(req["daily_limit"])))
                except (TypeError, ValueError):
                    return self._json(400, {"error": "Daily limit must be a number"})
            apply_agent.save(apply_agent.SETTINGS, s)
            return self._json(200, apply_view())

    def _apply_mark(self, req):
        status = req.get("status")
        if status not in ("applied", "skipped", "ready"):
            return self._json(400, {"error": "status must be applied, skipped or ready"})
        with _lock:
            queue = apply_agent.load(apply_agent.QUEUE, {})
            q = queue.get(str(req.get("id")))
            if not q:
                return self._json(404, {"error": "No internship with that id"})
            q["status"] = status
            if status == "applied":
                q["applied_on"] = apply_agent.today()
            if status == "skipped":
                q["skip_reason"] = "Skipped by Jack on the website"
            apply_agent.save(apply_agent.QUEUE, queue)
            return self._json(200, apply_view())

    def _apply_fill(self, req):
        jid = str(req.get("id", ""))
        with _lock:
            if jid not in apply_agent.load(apply_agent.QUEUE, {}):
                return self._json(404, {"error": "No internship with that id"})
        try:
            subprocess.Popen([sys.executable, os.path.join(APPLY_DIR, "autofill.py"), jid], cwd=APPLY_DIR,
                             creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        except OSError as e:
            return self._json(500, {"error": f"Couldn't start the autofill helper: {e}"})
        return self._json(200, {"ok": True})

    def log_message(self, fmt, *args):
        pass  # keep the window quiet


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    with Server(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Agents are connected. Your site with agents: http://127.0.0.1:{PORT}/  (enter your code at the bottom)")
        print("Keep this window open while you use the Agents section; close it to stop.")
        httpd.serve_forever()
