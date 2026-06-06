/* BanChan / blog — client interactions (vanilla JS, no deps).
 *
 * Hugo renders every post card at build time; this script only manipulates the
 * already-present DOM. Safe to load on any page — each init no-ops when its
 * target elements are absent.
 *
 * Contract this file relies on (produced by the template layer):
 *   List / home pages
 *     - #b-q                         search input
 *     - .b-list                      container of post cards
 *     - article.b-post               post card with data-* below
 *         data-cat   "C++"           single category key
 *         data-tags  "포인터 메모리"  space-separated tag list
 *         data-search "..."          pre-lowercased haystack (title/en/desc/tags)
 *         data-date  "2026-06-06"    YYYY-MM-DD
 *         data-read  "6"             read minutes (integer)
 *         data-pin   "0" | "1"       pinned flag
 *     - .b-tree .row[data-cat]       sidebar category row (toggles category filter)
 *     - .b-tags .t[data-tag]         sidebar tag chip (toggles tag filter)
 *     - .b-sort button[data-sort]    "new" / "short" sort buttons
 *     - .b-filters                   active-filter chip container (filled by JS)
 *     - .b-lhead .meta               "N / M entries" count label
 *     - .b-empty                     empty-state element after .b-list (hidden by default)
 *   Post detail pages
 *     - nav.b-toc a[href="#id"]      TOC links
 *     - .b-art .body h2[id]          headings observed for active TOC
 *     - .b-code .cp                  copy button (copies sibling <pre> text)
 *   Common
 *     - .b-main                      the scroll container (content, not sidebar)
 *     - #b-theme                     theme toggle button
 *
 * localStorage key: "bc-theme"  ->  "light" | "dark"
 *
 * Exposed init functions: initTheme, initSearchFilter, initSort, initTOC, initCopy
 */
(function () {
  "use strict";

  /* ── theme toggle ──────────────────────────────────────── */
  function initTheme() {
    var btn = document.getElementById("b-theme");

    // Sync body class with stored preference. The baseof <head> inline script
    // normally does this first to avoid FOUC; running it again is harmless.
    try {
      var saved = localStorage.getItem("bc-theme");
      if (saved === "light") document.body.classList.add("light");
      else if (saved === "dark") document.body.classList.remove("light");
    } catch (e) {}

    if (!btn) return;
    btn.addEventListener("click", function () {
      var isLight = document.body.classList.toggle("light");
      try {
        localStorage.setItem("bc-theme", isLight ? "light" : "dark");
      } catch (e) {}
    });
  }

  /* ── search + category/tag filter ──────────────────────── */
  function initSearchFilter() {
    var input = document.getElementById("b-q");
    var list = document.querySelector(".b-list");
    // The list page is identified by having a card list. Bail otherwise.
    if (!list) return;

    var cards = Array.prototype.slice.call(list.querySelectorAll(".b-post"));
    var rows = Array.prototype.slice.call(document.querySelectorAll(".b-tree .row"));
    var chips = Array.prototype.slice.call(document.querySelectorAll(".b-tags .t"));
    var filterBar = document.querySelector(".b-filters");
    var metaEl = document.querySelector(".b-lhead .meta");
    var empty = document.querySelector(".b-empty");

    // Current filter state. Mirrors the React route: search is exclusive with
    // category/tag (selecting one clears the others).
    var state = { q: "", cat: null, tag: null };

    function tagsOf(card) {
      return (card.getAttribute("data-tags") || "").split(/\s+/).filter(Boolean);
    }

    function matches(card) {
      if (state.q) {
        return (card.getAttribute("data-search") || "").indexOf(state.q) !== -1;
      }
      if (state.cat && card.getAttribute("data-cat") !== state.cat) return false;
      if (state.tag && tagsOf(card).indexOf(state.tag) === -1) return false;
      return true;
    }

    function syncActiveClasses() {
      rows.forEach(function (r) {
        r.classList.toggle("on", state.cat !== null && r.getAttribute("data-cat") === state.cat);
      });
      chips.forEach(function (c) {
        c.classList.toggle("on", state.tag !== null && c.getAttribute("data-tag") === state.tag);
      });
    }

    function renderChips() {
      if (!filterBar) return;
      filterBar.textContent = "";

      var active = [];
      if (state.cat) active.push({ kind: "cat", label: state.cat });
      if (state.tag) active.push({ kind: "tag", label: "#" + state.tag });
      if (state.q) active.push({ kind: "q", label: 'grep "' + state.q + '"' });

      active.forEach(function (item) {
        var chip = document.createElement("span");
        chip.className = "b-chip";
        chip.appendChild(document.createTextNode(item.label));

        var x = document.createElement("span");
        x.className = "x";
        x.textContent = "×";
        x.addEventListener("click", function () {
          if (item.kind === "cat") state.cat = null;
          else if (item.kind === "tag") state.tag = null;
          else if (item.kind === "q") {
            state.q = "";
            if (input) input.value = "";
          }
          apply();
        });
        chip.appendChild(x);
        filterBar.appendChild(chip);
      });

      if (active.length > 1) {
        var clearAll = document.createElement("span");
        clearAll.className = "b-chip b-chip-clear";
        clearAll.textContent = "clear all";
        clearAll.addEventListener("click", function () {
          state.q = "";
          state.cat = null;
          state.tag = null;
          if (input) input.value = "";
          apply();
        });
        filterBar.appendChild(clearAll);
      }
    }

    function apply() {
      var visible = 0;
      cards.forEach(function (card) {
        var show = matches(card);
        card.hidden = !show;
        if (show) visible++;
      });

      if (metaEl) {
        metaEl.textContent = visible + " / " + cards.length + " entries";
      }

      if (empty) {
        if (visible === 0) {
          list.hidden = true;
          empty.hidden = false;
        } else {
          list.hidden = false;
          empty.hidden = true;
        }
      }

      syncActiveClasses();
      renderChips();
    }

    // Search clears category/tag filters (React behavior).
    if (input) {
      input.addEventListener("input", function () {
        state.q = input.value.trim().toLowerCase();
        if (state.q) {
          state.cat = null;
          state.tag = null;
        }
        apply();
      });
    }

    // Category rows: toggle, clears search + tag.
    rows.forEach(function (r) {
      r.addEventListener("click", function () {
        var k = r.getAttribute("data-cat");
        state.cat = state.cat === k ? null : k;
        state.tag = null;
        state.q = "";
        if (input) input.value = "";
        apply();
      });
    });

    // Tag chips: toggle, clears search + category.
    chips.forEach(function (c) {
      c.addEventListener("click", function () {
        var t = c.getAttribute("data-tag");
        state.tag = state.tag === t ? null : t;
        state.cat = null;
        state.q = "";
        if (input) input.value = "";
        apply();
      });
    });

    // ⌘K / Ctrl+K focuses search (matches the prototype).
    if (input) {
      window.addEventListener("keydown", function (e) {
        if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
          e.preventDefault();
          input.focus();
        }
      });
    }

    apply();
  }

  /* ── sort ──────────────────────────────────────────────── */
  function initSort() {
    var list = document.querySelector(".b-list");
    var buttons = Array.prototype.slice.call(document.querySelectorAll(".b-sort button[data-sort]"));
    if (!list || !buttons.length) return;

    function num(card, attr, fallback) {
      var v = parseInt(card.getAttribute(attr), 10);
      return isNaN(v) ? fallback : v;
    }

    function sortBy(mode) {
      var cards = Array.prototype.slice.call(list.querySelectorAll(".b-post"));

      if (mode === "short") {
        // Read time ascending.
        cards.sort(function (a, b) {
          return num(a, "data-read", 0) - num(b, "data-read", 0);
        });
      } else {
        // Newest first, pinned on top.
        cards.sort(function (a, b) {
          var pin = num(b, "data-pin", 0) - num(a, "data-pin", 0);
          if (pin) return pin;
          var da = a.getAttribute("data-date") || "";
          var db = b.getAttribute("data-date") || "";
          // ISO YYYY-MM-DD sorts lexically; descending.
          return db < da ? -1 : db > da ? 1 : 0;
        });
      }

      cards.forEach(function (card) {
        list.appendChild(card);
      });

      buttons.forEach(function (btn) {
        btn.classList.toggle("on", btn.getAttribute("data-sort") === mode);
      });
    }

    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        sortBy(btn.getAttribute("data-sort"));
      });
    });

    // Apply the initially-active button (default "new" if none marked).
    var initial = buttons.filter(function (b) { return b.classList.contains("on"); })[0];
    sortBy(initial ? initial.getAttribute("data-sort") : "new");
  }

  /* ── TOC active tracking + smooth scroll ───────────────── */
  function initTOC() {
    var toc = document.querySelector("nav.b-toc");
    var main = document.querySelector(".b-main");
    if (!toc) return;

    var links = Array.prototype.slice.call(toc.querySelectorAll('a[href^="#"]'));
    if (!links.length) return;

    // Map heading id -> its TOC link.
    var linkById = {};
    links.forEach(function (a) {
      var id = decodeURIComponent((a.getAttribute("href") || "").slice(1));
      if (id) linkById[id] = a;
    });

    var headings = Object.keys(linkById)
      .map(function (id) { return document.getElementById(id); })
      .filter(Boolean);

    function setActive(id) {
      links.forEach(function (a) {
        a.classList.toggle("on", a === linkById[id]);
      });
    }

    if ("IntersectionObserver" in window && headings.length) {
      var ob = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) setActive(e.target.id);
        });
      }, { root: main || null, rootMargin: "-10% 0px -70% 0px", threshold: 0 });
      headings.forEach(function (h) { ob.observe(h); });
    }

    // Smooth scroll within the .b-main container on click.
    links.forEach(function (a) {
      a.addEventListener("click", function (e) {
        var id = decodeURIComponent((a.getAttribute("href") || "").slice(1));
        var el = document.getElementById(id);
        if (!el) return;
        e.preventDefault();
        if (main) {
          main.scrollTo({ top: el.offsetTop - 16, behavior: "smooth" });
        } else {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        setActive(id);
      });
    });
  }

  /* ── code block copy ───────────────────────────────────── */
  function initCopy() {
    var buttons = Array.prototype.slice.call(document.querySelectorAll(".b-code .cp"));
    if (!buttons.length) return;

    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var block = btn.closest(".b-code");
        // lineNumbersInTable: code lives in the last column's <pre>; the first
        // <pre> is the line-number gutter. Fall back to the only <pre> otherwise.
        var pre = block && (block.querySelector(".lntable td.lntd:last-child pre")
          || block.querySelector("pre"));
        if (!pre) return;

        var text = pre.innerText;

        function flash() {
          var prev = btn.textContent;
          btn.textContent = "copied ✓";
          btn.classList.add("done");
          setTimeout(function () {
            btn.textContent = prev || "copy";
            btn.classList.remove("done");
          }, 1400);
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(flash, function () {
            legacyCopy(text);
            flash();
          });
        } else {
          legacyCopy(text);
          flash();
        }
      });
    });

    function legacyCopy(text) {
      try {
        var ta = document.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "");
        ta.style.position = "absolute";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      } catch (e) {}
    }
  }

  /* ── boot ──────────────────────────────────────────────── */
  function init() {
    initTheme();
    initSearchFilter();
    initSort();
    initTOC();
    initCopy();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
