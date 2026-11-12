// Code box + private Agents section.
// The code is checked against its SHA-256 hash so it isn't written in plain text,
// but this is a public static site: it hides the section, it doesn't truly secure it.
// The real protection is that the agents only answer from this computer (agent-server.py).
(function () {
  var CODE_HASH = "488a33f1de72566bba0d9255eb057f2b52e94d20d71ccc94e15c7e76ddb21db5";
  // Opened from Start Agents.bat (port 8765) -> same server; from GitHub -> reach this PC's server
  var BASE = location.port === "8765" ? "" : "http://127.0.0.1:8765";
  var API = BASE + "/api/network";

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
    loadApply();
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
    p.textContent = "Can't reach your agents. On your computer, double-click \"Start Agents.bat\" in the test3 folder. It opens your site at 127.0.0.1:8765, where the agents always connect. (On the GitHub link, your browser may also ask to allow access to devices on your network: choose Allow, then press Refresh.)";
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

  // ---------- Auto apply internships ----------
  var A = BASE + "/api/apply";
  var aStatus = document.getElementById("apply-status");
  var aOn = document.getElementById("apply-on");
  var aOnText = document.getElementById("apply-on-text");
  var aForm = document.getElementById("apply-settings");
  var aLoc = document.getElementById("apply-location");
  var aRemote = document.getElementById("apply-remote");
  var aLimit = document.getElementById("apply-limit");
  var aSaved = document.getElementById("apply-saved");
  var aSheet = document.getElementById("apply-sheet");
  var aReady = document.getElementById("apply-ready");
  var aApplied = document.getElementById("apply-applied");

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function post(path, body) {
    return fetch(A + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || "Failed"); return d; });
    });
  }

  function meta(j) {
    return [j.location, j.employees && (j.employees + " employees"), j.pay].filter(Boolean).join(" · ");
  }

  function jobRow(j, ready) {
    var row = el("div", "job");
    var top = el("div", "job-top");
    var a = el("a", "job-title", j.company + " — " + j.title);
    a.href = j.url; a.target = "_blank"; a.rel = "noopener";
    top.appendChild(a);
    if (!ready && j.applied_on) top.appendChild(el("span", "muted", "Applied " + j.applied_on));
    row.appendChild(top);
    row.appendChild(el("p", "job-meta", meta(j)));
    if (!ready) return row;
    if (j.about) row.appendChild(el("p", "job-about", j.about));

    var actions = el("div", "job-actions");
    var fill = el("button", "btn primary", "Fill application");
    var letterBtn = el("button", "btn", "Cover letter");
    var done = el("button", "btn", "Mark applied");
    var skip = el("button", "btn", "Skip");
    [fill, letterBtn, done, skip].forEach(function (b) { b.type = "button"; actions.appendChild(b); });
    row.appendChild(actions);

    fill.addEventListener("click", function () {
      fill.disabled = true;
      fill.textContent = "Opening…";
      post("/fill", { id: j.id }).then(function () {
        fill.textContent = "Opened in Chrome — check it and press Submit";
      }).catch(function (e) {
        fill.disabled = false;
        fill.textContent = "Fill application";
        alert(e.message);
      });
    });

    var letterBox = null;
    letterBtn.addEventListener("click", function () {
      if (letterBox) { letterBox.remove(); letterBox = null; return; }
      fetch(A + "/letter?id=" + encodeURIComponent(j.id), { cache: "no-store" })
        .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
        .then(function (d) {
          letterBox = el("div", "letter", d.letter);
          var copy = el("button", "btn", "Copy");
          copy.type = "button";
          copy.style.marginTop = "10px";
          copy.addEventListener("click", function () {
            navigator.clipboard.writeText(d.letter).then(function () { copy.textContent = "Copied"; });
          });
          letterBox.appendChild(el("br"));
          letterBox.appendChild(copy);
          row.appendChild(letterBox);
        })
        .catch(function () { alert("Couldn't load the cover letter."); });
    });

    function mark(status) {
      post("/mark", { id: j.id, status: status }).then(renderApply).catch(function (e) { alert(e.message); });
    }
    done.addEventListener("click", function () { mark("applied"); });
    skip.addEventListener("click", function () {
      if (confirm("Skip " + j.company + " — " + j.title + "?")) mark("skipped");
    });
    return row;
  }

  function renderApply(d) {
    aStatus.textContent = "Connected";
    aStatus.className = "status on";
    var s = d.settings;
    aOn.disabled = false;
    aOn.checked = s.agent_on;
    aOnText.textContent = s.agent_on ? "Agent on" : "Agent off";
    if (document.activeElement !== aLoc) aLoc.value = s.location;
    aRemote.checked = s.remote_ok;
    aLimit.value = s.daily_limit;
    aSheet.href = s.sheet_url || "#";

    aReady.innerHTML = "";
    document.getElementById("apply-ready-count").textContent = "(" + d.ready.length + ")";
    if (!d.ready.length) {
      aReady.appendChild(el("p", null, s.agent_on
        ? "Nothing waiting. New internships show up here after the daily run (8 AM)."
        : "Turn the agent on and new internships will show up here after the daily run (8 AM)."));
    }
    d.ready.forEach(function (j) { aReady.appendChild(jobRow(j, true)); });

    aApplied.innerHTML = "";
    document.getElementById("apply-applied-count").textContent = "(" + d.applied_count + " total)";
    if (!d.applied.length) aApplied.appendChild(el("p", null, "None yet."));
    d.applied.forEach(function (j) { aApplied.appendChild(jobRow(j, false)); });
  }

  function applyOffline() {
    aStatus.textContent = "Offline";
    aStatus.className = "status off";
    aOn.disabled = true;
    aReady.innerHTML = "";
    aReady.appendChild(el("p", null, "Can't reach your computer. Double-click \"Start Agents.bat\" in the test3 folder."));
    aApplied.innerHTML = "";
  }

  function loadApply() {
    fetch(A, { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(renderApply)
      .catch(applyOffline);
  }

  aOn.addEventListener("change", function () {
    var want = aOn.checked;
    aOnText.textContent = want ? "Agent on" : "Agent off";
    post("/settings", { agent_on: want }).then(renderApply).catch(function (e) {
      aOn.checked = !want;
      aOnText.textContent = aOn.checked ? "Agent on" : "Agent off";
      alert(e.message);
    });
  });

  aForm.addEventListener("submit", function (e) {
    e.preventDefault();
    aSaved.textContent = "Saving…";
    post("/settings", { location: aLoc.value, remote_ok: aRemote.checked, daily_limit: aLimit.value })
      .then(function (d) { renderApply(d); aSaved.textContent = "Saved"; setTimeout(function () { aSaved.textContent = ""; }, 2000); })
      .catch(function (err) { aSaved.textContent = err.message; });
  });

  document.getElementById("net-refresh").addEventListener("click", loadApply);

  var saved = null;
  try { saved = sessionStorage.getItem("agents"); } catch (e) {}
  if (saved === "1") showAgents();
})();
