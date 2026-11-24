document.addEventListener("DOMContentLoaded", () => {
  const filter = document.getElementById("distanceFilter");
  if (!filter) return;

  const results = document.querySelectorAll("#resultList .result");
  const emptyMessage = document.getElementById("distance-filter-empty");

  function applyFilter() {
    const radius = filter.value === "unlimited" ? Infinity : Number(filter.value) * 1000;
    let visibleCount = 0;
    results.forEach((result) => {
      const distance = result.dataset.distance;
      result.hidden = distance === "" || !Number.isFinite(Number(distance)) || Number(distance) > radius;
      if (!result.hidden) visibleCount++;
    });
    if (emptyMessage) emptyMessage.hidden = visibleCount > 0;
    document.dispatchEvent(new Event("results-filtered"));
  }

  filter.addEventListener("change", () => {
    if ((filter.value === "unlimited") !== (filter.dataset.searchMode === "unlimited")) {
      filter.form.requestSubmit();
      return;
    }
    applyFilter();
  });
  filter.disabled = false;
  applyFilter();
});
