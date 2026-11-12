// Code box + private Agents section.
// The code is checked against its SHA-256 hash so it isn't written in plain text,
// but this is a public static site: it hides the section, it doesn't truly secure it.
// The real protection is that the agents only answer from this computer (agent-server.py).
(function () {
  var CODE_HASH = "488a33f1de72566bba0d9255eb057f2b52e94d20d71ccc94e15c7e76ddb21db5";
  var API = "http://127.0.0.1:8765/api/network";

  var portfolio = document.getElementById("top");
  var agents = document.getElementById("agents");
  var codeBox = document.getElementById("code-box");
  var navLinks = document.querySelector(".nav nav");
  var form = document.getElementById("code-form");
  var input = document.getElementById("code");
  var msg = document.getElementById("code-msg");

  function sha256(text) {
    return crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)).then(function (buf) {
      return Array.from(new Uint8Array(buf)).map(function (b) { return b.toString(16).padStart(2, "0"); }).join("");
    });
  }

  function remember(on) {
    try { on ? sessionStorage.setItem("agents", "1") : sessionStorage.removeItem("agents"); } catch (e) {}
  }

  function showAgents() {
    portfolio.hidden = true;
    codeBox.hidden = true;
    navLinks.hidden = true;
    agents.hidden = false;
    window.scrollTo(0, 0);
    loadNetwork();
  }

  function showPortfolio() {
    agents.hidden = true;
    portfolio.hidden = false;
    codeBox.hidden = false;
    navLinks.hidden = false;
    input.value = "";
    msg.textContent = "";
    remember(false);
    window.scrollTo(0, 0);
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    sha256(input.value.trim()).then(function (h) {
      if (h === CODE_HASH) {
        remember(true);
        showAgents();
      } else {
        msg.textContent = "Wrong code.";
        input.select();
      }
    });
  });
  document.getElementById("lock").addEventListener("click", showPortfolio);

  // ---------- Networking agent ----------
  var statusEl = document.getElementById("net-status");
  var list = document.getElementById("net-projects");
  var creditsEl = document.getElementById("net-credits");

  function setStatus(text, ok) {
    statusEl.textContent = text;
    statusEl.className = "status " + (ok ? "on" : "off");
  }

  function offline() {
    setStatus("Offline", false);
    list.innerHTML = "";
    var p = document.createElement("p");
    p.className = "muted";
    p.textContent = "Can't reach your agents. On your computer, double-click \"Start Agents.bat\" in the test3 folder, then press Refresh. If your browser asks to allow access to devices on your network, choose Allow.";
    list.appendChild(p);
  }

  function render(data) {
    setStatus("Connected", true);
    list.innerHTML = "";
    if (!data.projects || !data.projects.length) {
      list.textContent = "No projects yet.";
      return;
    }
    data.projects.forEach(function (project, index) {
      var row = document.createElement("div");
      row.className = "project-row";

      var name = document.createElement("a");
      name.href = project.url;
      name.target = "_blank";
      name.rel = "noopener";
      name.textContent = project.name + " ↗";

      var label = document.createElement("label");
      label.className = "toggle";
      var box = document.createElement("input");
      box.type = "checkbox";
      box.checked = project.agent_on;
      box.setAttribute("aria-label", "Run the agent for " + project.name);
      var sw = document.createElement("span");
      sw.className = "switch";
      var text = document.createElement("span");
      text.textContent = project.agent_on ? "Agent on" : "Agent off";

      box.addEventListener("change", function () {
        var want = box.checked;
        text.textContent = want ? "Agent on" : "Agent off";
        fetch(API + "/toggle", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ index: index, agent_on: want })
        }).then(function (r) {
          if (!r.ok) throw new Error();
        }).catch(function () {
          box.checked = !want;
          text.textContent = box.checked ? "Agent on" : "Agent off";
          alert("Couldn't save the change. Is Start Agents.bat running?");
        });
      });

      label.appendChild(box);
      label.appendChild(sw);
      label.appendChild(text);
      row.appendChild(name);
      row.appendChild(label);
      list.appendChild(row);
    });
  }

  function loadNetwork() {
    setStatus("Checking…", false);
    fetch(API, { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(render)
      .catch(offline);
  }

  document.getElementById("net-refresh").addEventListener("click", loadNetwork);
  document.getElementById("net-credits-btn").addEventListener("click", function () {
    creditsEl.textContent = "Checking…";
    fetch(API + "/credits", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (d) {
        creditsEl.textContent = d.searches_left + " searches · " + d.verifications_left + " verifications left";
      })
      .catch(function () { creditsEl.textContent = "Couldn't check credits."; });
  });

  var saved = null;
  try { saved = sessionStorage.getItem("agents"); } catch (e) {}
  if (saved === "1") showAgents();
})();
