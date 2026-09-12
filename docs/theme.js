(function () {
  "use strict";
  var KEY = "pste-theme";

  function stored() {
    try {
      return localStorage.getItem(KEY);
    } catch (e) {
      return null;
    }
  }

  function apply(theme) {
    if (theme === "light" || theme === "dark") {
      document.documentElement.setAttribute("data-theme", theme);
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }

  function current() {
    var attr = document.documentElement.getAttribute("data-theme");
    if (attr) return attr;
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  apply(stored());

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      apply(next);
      try {
        localStorage.setItem(KEY, next);
      } catch (e) {
        /* private window: the toggle still works, it just does not persist */
      }
    });
  });
})();
