// Consenso cookie e contenuti esterni (D-06, D-60, D-66). File statico del CMS.
// - la scelta vive solo nel browser (cookie cms_consent, 12 mesi): il server non la legge;
// - "Accetta tutto" e "Solo necessari" hanno lo stesso peso; "Scegli" apre due caselle;
// - video e mappe: segnaposto; si caricano col consenso "Video e mappe" o con un clic;
// - Matomo parte solo con il consenso "Statistiche".
(function () {
  "use strict";
  var COOKIE = "cms_consent";
  var MAX_AGE = 365 * 24 * 3600;
  var ALLOWED_HOSTS = ["www.youtube-nocookie.com", "player.vimeo.com", "www.openstreetmap.org"];
  var script = document.currentScript;
  var banner = document.getElementById("cms-consent");
  var matomoUrl = script ? script.getAttribute("data-matomo-url") : null;
  var matomoSite = script ? script.getAttribute("data-matomo-site") : null;
  var statsLoaded = false;

  function readConsent() {
    var parts = document.cookie.split(";");
    for (var i = 0; i < parts.length; i++) {
      var pair = parts[i].trim().split("=");
      if (pair[0] === COOKIE) {
        var match = /^v1\.e([01])\.s([01])$/.exec(pair[1] || "");
        if (match) {
          return { embeds: match[1] === "1", stats: match[2] === "1" };
        }
      }
    }
    return null;
  }

  function writeConsent(consent) {
    var value = "v1.e" + (consent.embeds ? "1" : "0") + ".s" + (consent.stats ? "1" : "0");
    var secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = COOKIE + "=" + value + "; Max-Age=" + MAX_AGE + "; Path=/; SameSite=Lax" + secure;
  }

  function safeSource(src) {
    try {
      var url = new URL(src);
      return url.protocol === "https:" && ALLOWED_HOSTS.indexOf(url.hostname) !== -1;
    } catch (error) {
      return false;
    }
  }

  function loadEmbed(placeholder) {
    var src = placeholder.getAttribute("data-cms-embed-src");
    if (!src || !safeSource(src) || placeholder.classList.contains("cms-embed--loaded")) {
      return;
    }
    var frame = document.createElement("iframe");
    frame.src = src;
    frame.title = placeholder.getAttribute("data-cms-embed-title") || "";
    frame.loading = "lazy";
    frame.referrerPolicy = "strict-origin-when-cross-origin";
    frame.setAttribute("sandbox", "allow-scripts allow-same-origin allow-presentation allow-popups");
    if (placeholder.getAttribute("data-cms-embed") === "video") {
      frame.setAttribute("allow", "fullscreen; picture-in-picture");
    }
    placeholder.replaceChildren(frame);
    placeholder.classList.add("cms-embed--loaded");
  }

  function loadAllEmbeds() {
    var placeholders = document.querySelectorAll("[data-cms-embed]");
    for (var i = 0; i < placeholders.length; i++) {
      loadEmbed(placeholders[i]);
    }
  }

  function loadStats() {
    if (statsLoaded || !matomoUrl || !/^[0-9]+$/.test(matomoSite || "")) {
      return;
    }
    var base;
    try {
      base = new URL(matomoUrl);
    } catch (error) {
      return;
    }
    if (base.protocol !== "https:") {
      return;
    }
    statsLoaded = true;
    var root = base.href.replace(/\/?$/, "/");
    var queue = (window._paq = window._paq || []);
    queue.push(["setTrackerUrl", root + "matomo.php"]);
    queue.push(["setSiteId", matomoSite]);
    queue.push(["trackPageView"]);
    queue.push(["enableLinkTracking"]);
    var tag = document.createElement("script");
    tag.async = true;
    tag.src = root + "matomo.js";
    document.head.appendChild(tag);
  }

  function apply(consent) {
    if (consent.embeds) {
      loadAllEmbeds();
    }
    if (consent.stats) {
      loadStats();
    }
  }

  function boxes() {
    var embeds = banner ? banner.querySelector('input[name="embeds"]') : null;
    var stats = banner ? banner.querySelector('input[name="stats"]') : null;
    return { embeds: embeds, stats: stats };
  }

  function showBanner(focus) {
    if (!banner) {
      return;
    }
    var current = readConsent() || { embeds: false, stats: false };
    var inputs = boxes();
    if (inputs.embeds) {
      inputs.embeds.checked = current.embeds;
    }
    if (inputs.stats) {
      inputs.stats.checked = current.stats;
    }
    banner.hidden = false;
    if (focus) {
      var first = banner.querySelector("button");
      if (first) {
        first.focus();
      }
    }
  }

  function choose(consent) {
    writeConsent(consent);
    if (banner) {
      banner.hidden = true;
    }
    apply(consent);
  }

  function toggleChoices(button) {
    var panel = document.getElementById("cms-consent-choices");
    var save = banner.querySelector('[data-cms-consent="save"]');
    var open = button.getAttribute("aria-expanded") === "true";
    button.setAttribute("aria-expanded", open ? "false" : "true");
    if (panel) {
      panel.hidden = open;
    }
    if (save) {
      save.hidden = open;
    }
  }

  if (banner) {
    banner.addEventListener("click", function (event) {
      var button = event.target.closest ? event.target.closest("[data-cms-consent]") : null;
      if (!button) {
        return;
      }
      var action = button.getAttribute("data-cms-consent");
      var inputs = boxes();
      if (action === "all") {
        choose({ embeds: true, stats: true });
      } else if (action === "necessary") {
        choose({ embeds: false, stats: false });
      } else if (action === "choose") {
        toggleChoices(button);
      } else if (action === "save") {
        choose({
          embeds: Boolean(inputs.embeds && inputs.embeds.checked),
          stats: Boolean(inputs.stats && inputs.stats.checked),
        });
      }
    });
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target.closest) {
      return;
    }
    if (target.closest("[data-cms-consent-open]")) {
      showBanner(true);
      return;
    }
    var load = target.closest(".cms-embed__load");
    if (load) {
      var placeholder = load.closest("[data-cms-embed]");
      if (placeholder) {
        loadEmbed(placeholder); // un clic esplicito vale per questo solo contenuto
      }
    }
  });

  var saved = readConsent();
  if (saved) {
    apply(saved);
  } else {
    showBanner(false);
  }
})();
