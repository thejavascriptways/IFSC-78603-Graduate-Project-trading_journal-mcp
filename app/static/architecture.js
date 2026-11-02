(function () {
  "use strict";
  var dataEl = document.getElementById("arch-data");
  var tip = document.getElementById("arch-tip");
  if (!dataEl || !tip) return;

  var nodes = {};
  JSON.parse(dataEl.textContent).forEach(function (n) { nodes[n.id] = n; });
  var edges = Array.prototype.slice.call(document.querySelectorAll(".arch-edge"));
  var active = null;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    return node;
  }

  function buildTip(n) {
    tip.textContent = "";
    tip.appendChild(el("p", "arch-tip-kind arch-" + n.kind, n.kind_label));
    tip.appendChild(el("h3", "arch-tip-title", n.label));
    if (n.sub) tip.appendChild(el("p", "arch-tip-sub", n.sub));
    tip.appendChild(el("p", "arch-tip-summary", n.summary));
    if (n.details && n.details.length) {
      var ul = el("ul", "arch-tip-list");
      n.details.forEach(function (d) { ul.appendChild(el("li", null, d)); });
      tip.appendChild(ul);
    }
    (n.lists || []).forEach(function (group) {
      tip.appendChild(el("p", "arch-tip-heading", group.title));
      var row = el("p", "arch-tip-chips");
      group.items.forEach(function (item) { row.appendChild(el("code", null, item)); });
      tip.appendChild(row);
    });
    if (n.files && n.files.length) {
      tip.appendChild(el("p", "arch-tip-heading", "Where in the code"));
      var files = el("p", "arch-tip-chips");
      n.files.forEach(function (f) { files.appendChild(el("code", null, f)); });
      tip.appendChild(files);
    }
  }

  function place(target) {
    var r = target.getBoundingClientRect();
    var vw = document.documentElement.clientWidth;
    var vh = window.innerHeight;
    var margin = 12;
    tip.style.left = "0px";
    tip.style.top = "0px";
    var tw = tip.offsetWidth, th = tip.offsetHeight;
    var left = Math.max(margin, Math.min(r.left + r.width / 2 - tw / 2, vw - tw - margin));
    var top = r.bottom + 10;
    if (top + th > vh - margin) top = r.top - th - 10;
    if (top < margin) top = Math.max(margin, Math.min(r.bottom + 10, vh - th - margin));
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }

  function highlight(id) {
    edges.forEach(function (e) {
      e.classList.toggle("is-active", id !== null && (e.dataset.from === id || e.dataset.to === id));
    });
  }

  function show(target) {
    var n = nodes[target.dataset.nodeId];
    if (!n) return;
    if (active) active.classList.remove("is-active");
    active = target;
    target.classList.add("is-active");
    target.setAttribute("aria-describedby", "arch-tip");
    buildTip(n);
    tip.hidden = false;
    place(target);
    highlight(n.id);
  }

  function hide() {
    if (active) { active.classList.remove("is-active"); active.removeAttribute("aria-describedby"); }
    active = null;
    tip.hidden = true;
    highlight(null);
  }

  var touchOnly = window.matchMedia && window.matchMedia("(hover: none)").matches;
  Array.prototype.forEach.call(document.querySelectorAll(".arch-node"), function (node) {
    node.addEventListener("mouseenter", function () { show(node); });
    node.addEventListener("mouseleave", hide);
    node.addEventListener("focus", function () { show(node); });
    node.addEventListener("blur", hide);
    node.addEventListener("click", function () {
      if (!touchOnly) return;
      if (active === node) hide(); else show(node);
    });
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") hide(); });
  window.addEventListener("scroll", function () { if (active) place(active); }, true);
  window.addEventListener("resize", function () { if (active) place(active); });
})();
