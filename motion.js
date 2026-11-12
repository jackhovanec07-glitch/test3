// Scroll effects: content rises in as it comes into view, photos wipe open,
// photos drift slightly (parallax), and a thin progress bar tracks the page.
// Everything is skipped for people who turn on "reduce motion" in their system settings.
(function () {
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var root = document.documentElement;
  var bar = document.querySelector(".progress");

  // Progress bar (kept even with reduced motion: it doesn't animate on its own)
  function updateBar() {
    var max = root.scrollHeight - root.clientHeight;
    bar.style.transform = "scaleX(" + (max > 0 ? root.scrollTop / max : 0) + ")";
  }

  if (reduce || !("IntersectionObserver" in window)) {
    window.addEventListener("scroll", updateBar, { passive: true });
    updateBar();
    return;
  }
  root.classList.add("motion");

  // Groups whose items come in one after another
  var groups = [".about-grid > *", ".facts li", ".cards .card", ".timeline li", ".contact p, .contact .cta"];
  groups.forEach(function (sel) {
    document.querySelectorAll(sel).forEach(function (el, i) {
      el.classList.add("reveal");
      el.style.setProperty("--stagger", Math.min(i, 5) * 90 + "ms");
    });
  });

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) {
        e.target.classList.add("in");
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.15, rootMargin: "0px 0px -8% 0px" });
  document.querySelectorAll(".reveal, .reveal-photo").forEach(function (el) { io.observe(el); });

  // Parallax
  var layers = Array.prototype.slice.call(document.querySelectorAll("[data-parallax]"));
  var ticking = false;
  function frame() {
    ticking = false;
    updateBar();
    var vh = window.innerHeight;
    layers.forEach(function (img) {
      var r = img.parentElement.getBoundingClientRect();
      if (r.bottom < 0 || r.top > vh) return;
      var offset = (r.top + r.height / 2 - vh / 2) * parseFloat(img.dataset.parallax);
      img.style.setProperty("--py", offset.toFixed(1) + "px");
    });
  }
  function onScroll() {
    if (!ticking) { ticking = true; requestAnimationFrame(frame); }
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  frame();
})();
