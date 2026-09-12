(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    // Each .switcher lives beside the block of .panel elements it drives.
    // Scoping the query to that shared parent keeps two switchers on one
    // page independent: changing one dropdown never touches the other
    // section's panels, because each selector only ever looks inside its
    // own parent.
    var switchers = Array.prototype.slice.call(
      document.querySelectorAll(".switcher select"));

    switchers.forEach(function (select) {
      var scope = select.closest(".switcher").parentNode;
      var panels = Array.prototype.slice.call(
        scope.querySelectorAll(".panel[id^='panel-']"));

      // The dropdown is the only control, so a panel is shown when its id is
      // the selected value. No JS runs before this: the first panel ships
      // visible and the rest ship hidden, so the page reads correctly with
      // scripting off.
      function show(id) {
        panels.forEach(function (p) { p.hidden = p.id !== id; });
      }

      select.addEventListener("change", function () { show(select.value); });
    });
  });
})();
