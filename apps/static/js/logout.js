document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("logout-confirm-form");
  if (!form) return;

  form.addEventListener("submit", () => {
    try {
      window.sessionStorage.clear();
    } catch (error) {
      console.error("セッションストレージを消去できませんでした。", error);
    }
  });

  const cancel = document.getElementById("logout-cancel");
  cancel.addEventListener("click", (event) => {
    if (!document.referrer) return;
    const previous = new URL(document.referrer);
    if (previous.origin === window.location.origin && previous.pathname !== window.location.pathname) {
      event.preventDefault();
      window.history.back();
    }
  });
});
