document.addEventListener("DOMContentLoaded", () => {
  const tabButtons = document.querySelectorAll(".tab-button");
  const searchPanels = document.querySelectorAll(".search-panel");

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.dataset.tab;
      tabButtons.forEach((tab) => tab.classList.remove("active"));
      searchPanels.forEach((panel) => panel.classList.remove("active"));
      button.classList.add("active");
      document.getElementById(targetId).classList.add("active");
    });
  });

  document.querySelectorAll(".mood-card").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById("dishName");
      input.value = button.dataset.mood;
      document.getElementById("mood-picker").open = false;
      input.focus();
    });
  });
});
