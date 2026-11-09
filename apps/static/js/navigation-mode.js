document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.querySelector("#sidebar");
  const mypageItem = document.querySelector(".sidebar-mypage-item");
  const storeManagementItem = document.querySelector(".sidebar-store-management-item");
  const modeToggle = document.querySelector(".mode-toggle");

  if (!sidebar || !mypageItem || !storeManagementItem) return;

  const setMode = (isRestaurantMode, persist = false) => {
    mypageItem.hidden = isRestaurantMode;
    storeManagementItem.hidden = !isRestaurantMode;

    if (modeToggle) {
      modeToggle.setAttribute("aria-pressed", isRestaurantMode ? "true" : "false");
      modeToggle.setAttribute(
        "aria-label",
        isRestaurantMode ? "一般モードに切り替え" : "飲食店モードに切り替え"
      );
      modeToggle.textContent = isRestaurantMode ? "一般へ" : "飲食店へ";
    }

    if (persist) {
      localStorage.setItem("ichihane-mode", isRestaurantMode ? "restaurant" : "general");
    }
  };

  setMode(localStorage.getItem("ichihane-mode") === "restaurant");

  if (modeToggle) {
    modeToggle.addEventListener("click", () => {
      const isRestaurantMode = modeToggle.getAttribute("aria-pressed") !== "true";
      setMode(isRestaurantMode, true);
    });
  }
});
