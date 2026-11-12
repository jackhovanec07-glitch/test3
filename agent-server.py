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

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.join(os.path.dirname(HERE), "test_1", "internship-agent")
PROJECTS = os.path.join(AGENT_DIR, "projects.json")
HUNTER = os.path.join(AGENT_DIR, "hunter.py")
PORT = 8765
ALLOWED_ORIGINS = {
    "https://jackhovanec07-glitch.github.io",
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
        if not self._origin_ok():
            return self._json(403, {"error": "Not allowed"})
        path = self.path.split("?")[0]
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
        return self._json(404, {"error": "Not found"})

    def do_POST(self):
        if not self._origin_ok():
            return self._json(403, {"error": "Not allowed"})
        if self.path.split("?")[0] != "/api/network/toggle":
            return self._json(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(min(length, 10000)) or b"{}")
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

    def log_message(self, fmt, *args):
        pass  # keep the window quiet


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    with Server(("127.0.0.1", PORT), Handler) as httpd:
        print("Agents are connected. Open your website and enter your code.")
        print("Keep this window open while you use the Agents section; close it to stop.")
        httpd.serve_forever()
