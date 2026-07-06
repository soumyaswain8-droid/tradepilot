/* TradePilot unified page-switcher — floating top-right nav cards on every page.
   Single source of truth; injected via <script src="/static/pageswitch.js"></script>.
   2026-06-06. */
(function () {
  var PAGES = [
    { key: "desk",   label: "Desk",   sub: "Trading desk",   href: "/dashboard", icon: "▤", match: ["/dashboard"] },
    { key: "market", label: "Market", sub: "Browse & scan",  href: "/",          icon: "◳", match: ["/", "/landing"] },
    { key: "live",   label: "Live",   sub: "Mission control", href: "/live",     icon: "◎", match: ["/live"] },
    { key: "lab",    label: "A/B",    sub: "Beta / testing",  href: "/lab",       icon: "◇", match: ["/lab"] },
    { key: "agents", label: "Agents", sub: "Sarathi team",   href: "/team",      icon: "⬡", match: ["/team", "/team_sarathi"] },
    { key: "decide", label: "Decisions", sub: "Root-cause & RC roadmap", href: "/decisions", icon: "⚑", match: ["/decisions"] },
  ];
  var path = location.pathname.replace(/\/$/, "") || "/";

  var css = ""
    + "#tp-switch{position:fixed;top:10px;right:12px;z-index:99999;display:flex;gap:5px;transition:top .2s ease;"
    + "padding:4px;border-radius:11px;background:rgba(8,13,20,.78);border:1px solid rgba(120,150,180,.18);"
    + "backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);box-shadow:0 4px 18px rgba(0,0,0,.4);"
    + "font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace}"
    + "#tp-switch a{display:flex;align-items:center;gap:6px;text-decoration:none;"
    + "padding:6px 10px;border-radius:8px;border:1px solid transparent;"
    + "transition:background .16s cubic-bezier(.23,1,.32,1),border-color .16s cubic-bezier(.23,1,.32,1),transform .16s cubic-bezier(.23,1,.32,1)}"
    + "#tp-switch a:hover{background:rgba(34,211,238,.08);border-color:rgba(34,211,238,.4)}"
    + "#tp-switch a:active{transform:scale(.97)}"
    + "#tp-switch .ic{font-size:13px;line-height:1;color:#7fb6cc}"
    + "#tp-switch .lb{font-size:11px;font-weight:600;letter-spacing:.03em;color:#cfe2ee}"
    + "#tp-switch a.on{background:rgba(34,211,238,.14);border-color:#22d3ee;box-shadow:0 0 14px rgba(34,211,238,.25) inset}"
    + "#tp-switch a.on .ic{color:#22d3ee}#tp-switch a.on .lb{color:#bff3fb}"
    + "@media(max-width:1000px){#tp-switch .lb{display:none}}";

  function build() {
    if (document.getElementById("tp-switch")) return;
    var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
    var nav = document.createElement("div"); nav.id = "tp-switch";
    PAGES.forEach(function (p) {
      var active = p.match.indexOf(path) !== -1;
      var a = document.createElement("a");
      a.href = p.href; a.title = p.label + " — " + p.sub;
      if (active) a.className = "on";
      a.innerHTML = '<span class="ic">' + p.icon + '</span><span class="lb">' + p.label + '</span>';
      nav.appendChild(a);
    });
    document.body.appendChild(nav);
    position(nav);
    window.addEventListener("resize", function () { position(nav); });
    // headers render/animate in late on some pages — settle position after load
    setTimeout(function () { position(nav); }, 600);
  }

  // Drop the switcher just below the page's top header bar(s). /live keeps it in
  // its (now-freed) top strip. Others: find the lowest bottom of any near-top,
  // full-width bar (header + a tab bar stacked right under it) and sit below.
  function position(nav) {
    if (path === "/live") { nav.style.top = "10px"; return; }
    var hb = 0, vw = window.innerWidth;
    document.querySelectorAll("body > *, body > * > *").forEach(function (el) {
      if (el.id === "tp-switch") return;
      var r = el.getBoundingClientRect();
      if (r.top <= 72 && r.width >= vw * 0.5 && r.height >= 26 && r.height <= 140 && r.bottom > hb) hb = r.bottom;
    });
    nav.style.top = (Math.round(hb || 48) + 10) + "px";
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();
