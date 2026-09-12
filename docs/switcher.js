(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var select = document.getElementById("doc-select");
    if (!select) return;

    var panels = Array.prototype.slice.call(
      document.querySelectorAll(".panel[id^='panel-']"));

    // The dropdown is the only control, so a panel is shown when its id is the
    // selected value. No JS runs before this: panel-0 ships visible and the
    // rest ship hidden, so the page reads correctly with scripting off.
    function show(id) {
      panels.forEach(function (p) { p.hidden = p.id !== id; });
    }

    select.addEventListener("change", function () { show(select.value); });
  });
})();
