// Anteprima nel pannello (D-02, D-55). File statico del CMS, nessun JavaScript inline.
// - evidenzia i blocchi ([data-block-id]) e comunica il click al pannello con postMessage;
// - accetta messaggi solo dal pannello della stessa origine;
// - nell'anteprima i link non portano altrove e i moduli non si inviano;
// - lo scorrimento resta dov'era quando l'anteprima si aggiorna (il pannello crea un iframe
//   nuovo a ogni modifica, D-107: la posizione si salva mentre si scorre).
(function () {
  "use strict";
  var ORIGIN = window.location.origin;
  var SCROLL_KEY = "cms-preview-scroll:" + window.location.pathname;
  var ACTIVE = "cms-preview-active";
  document.documentElement.classList.add("cms-preview");

  function inPanel() {
    return window.parent !== window;
  }

  function blockOf(node) {
    return node && node.closest ? node.closest("[data-block-id]") : null;
  }

  function send(type, uid) {
    if (inPanel()) {
      window.parent.postMessage({ type: type, uid: uid }, ORIGIN);
    }
  }

  function highlight(uid, scroll) {
    var blocks = document.querySelectorAll("[data-block-id]");
    for (var i = 0; i < blocks.length; i++) {
      var match = blocks[i].getAttribute("data-block-id") === uid;
      blocks[i].classList.toggle(ACTIVE, match);
      if (match && scroll) {
        blocks[i].scrollIntoView({ block: "center", behavior: "auto" });
      }
    }
  }

  document.addEventListener("click", function (event) {
    var block = blockOf(event.target);
    if (event.target.closest && event.target.closest("a, button")) {
      event.preventDefault();
    }
    if (block) {
      send("cms:block-click", block.getAttribute("data-block-id"));
    }
  });

  document.addEventListener("submit", function (event) {
    event.preventDefault();
  });

  window.addEventListener("message", function (event) {
    if (event.origin !== ORIGIN || event.source !== window.parent) {
      return;
    }
    var data = event.data || {};
    if (data.type === "cms:highlight" && typeof data.uid === "string") {
      highlight(data.uid, data.scroll !== false);
    }
  });

  try {
    var saved = window.sessionStorage.getItem(SCROLL_KEY);
    if (saved !== null) {
      window.scrollTo(0, parseInt(saved, 10) || 0);
    }
    var pending = false;
    window.addEventListener("scroll", function () {
      if (pending) {
        return;
      }
      pending = true; // al massimo una scrittura per fotogramma
      window.requestAnimationFrame(function () {
        pending = false;
        window.sessionStorage.setItem(SCROLL_KEY, String(window.scrollY));
      });
    });
  } catch (error) {
    // sessionStorage non disponibile: l'anteprima funziona lo stesso.
  }

  send("cms:ready", null);
})();
