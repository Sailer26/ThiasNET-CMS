// Tema default: menu a scomparsa sui telefoni. Senza JavaScript il menu resta visibile.
(function () {
  "use strict";
  document.documentElement.classList.add("js");
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("site-nav");
  if (!toggle || !nav) {
    return;
  }
  nav.setAttribute("data-collapsed", "true");
  toggle.addEventListener("click", function () {
    var open = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", open ? "false" : "true");
    nav.setAttribute("data-collapsed", open ? "true" : "false");
  });
})();
