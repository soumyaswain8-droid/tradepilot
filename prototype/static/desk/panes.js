/* panes.js — the two Agent Floor consoles, framed.

   Why iframes: /floor and /team are self-contained documents that assume they
   own the browser. floor.html sets body{overflow:hidden}, paints scanlines via
   body::after and sizes a canvas to the viewport; team.html styles bare
   header/main/section selectors. All three stylesheets also define --bg,
   --panel and --green with DIFFERENT values, so concatenating them would let
   last-one-wins quietly restyle whichever loaded first. A frame is a document
   boundary, which is exactly the isolation those two need.

   Why unmount clears src: team.html polls every 5s (POLL_MS = 5000, ~720
   requests/hour) and floor.html every 2s (setTimeout(poll, 2000), ~1,800
   requests/hour) -- ~2,520 requests/hour combined. Left mounted behind a
   hidden tab, that traffic runs for a screen nobody is looking at.
   about:blank tears the document down and takes its timers with it. */
(function () {
  "use strict";

  function pane(viewId, frameId, src) {
    window.TPRouter.register(viewId, {
      mount: function () {
        var f = document.getElementById(frameId);
        if (f && f.getAttribute("src") !== src) f.setAttribute("src", src);
      },
      unmount: function () {
        var f = document.getElementById(frameId);
        if (f) f.setAttribute("src", "about:blank");
      }
    });
  }

  pane("agents-quant", "frameQuant", "/team?embed=1");
  pane("agents-floor", "frameFloor", "/floor?embed=1");
})();
