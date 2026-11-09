document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".sidebar-management-toggle").forEach((toggle) => {
    const menu = document.getElementById(toggle.getAttribute("aria-controls"));
    if (!menu) return;

    toggle.addEventListener("click", () => {
      const isExpanded = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", isExpanded ? "false" : "true");
    });
  });
});
