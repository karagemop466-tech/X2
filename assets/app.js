// X2 site shared behavior: table sorting, filtering, nav active state
(function () {
  "use strict";

  // Highlight current page in nav
  (function setActiveNav() {
    var path = window.location.pathname.split("/").pop() || "index.html";
    var links = document.querySelectorAll(".nav-links a");
    links.forEach(function (a) {
      var href = a.getAttribute("href") || "";
      var h = href.split("/").pop() || "index.html";
      if (h === path) {
        a.classList.add("active");
      }
    });
  })();

  // Make all tables sortable + filterable
  document.querySelectorAll("table.data").forEach(function (table) {
    var ths = Array.from(table.querySelectorAll("th"));
    var rows = Array.from(table.querySelectorAll("tbody tr"));
    if (!rows.length) return;

    var filterInput = document.getElementById("filter");
    var tbody = table.querySelector("tbody");

    function render(filterText) {
      var ft = (filterText || "").toLowerCase();
      rows.forEach(function (row) {
        var text = row.textContent || "";
        row.style.display = text.toLowerCase().indexOf(ft) >= 0 ? "" : "none";
      });
    }

    if (filterInput) {
      filterInput.addEventListener("input", function (e) {
        render(e.target.value);
      });
    }

    ths.forEach(function (th, idx) {
      if (!th.classList.contains("sortable")) return;
      var dir = 1;
      th.addEventListener("click", function () {
        dir = -dir;
        var colIndex = idx;
        var sorted = rows.slice().sort(function (a, b) {
          var av = a.children[colIndex] ? a.children[colIndex].textContent.trim() : "";
          var bv = b.children[colIndex] ? b.children[colIndex].textContent.trim() : "";
          var an = parseFloat(av.replace(/[^0-9.-]/g, ""));
          var bn = parseFloat(bv.replace(/[^0-9.-]/g, ""));
          if (!isNaN(an) && !isNaN(bn) && av.match(/^[\d\.,%-]+$/)) {
            return (an - bn) * dir;
          }
          return av.localeCompare(bv, undefined, { numeric: true }) * dir;
        });
        sorted.forEach(function (r) { tbody.appendChild(r); });
        ths.forEach(function (t) { t.classList.remove("sorted-asc", "sorted-desc"); });
        th.classList.add(dir === 1 ? "sorted-asc" : "sorted-desc");
        render(filterInput ? filterInput.value : "");
      });
    });
  });
})();
