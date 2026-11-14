// Minimal client-side filter for tables marked as filterable. Tables work without this script.
(function () {
  document.querySelectorAll('input.search[data-target]').forEach(function (box) {
    var table = document.getElementById(box.getAttribute('data-target'));
    if (!table) return;
    box.addEventListener('input', function () {
      var q = box.value.trim().toLowerCase();
      table.querySelectorAll('tbody tr').forEach(function (tr) {
        tr.style.display = !q || tr.textContent.toLowerCase().indexOf(q) !== -1 ? '' : 'none';
      });
    });
  });
})();
