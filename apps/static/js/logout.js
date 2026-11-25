document.addEventListener("DOMContentLoaded", () => {
  const clearSessionStorage = () => {
    try {
      window.sessionStorage.clear();
    } catch (error) {
      console.error("セッションストレージを消去できませんでした。", error);
    }
  };

  const form = document.getElementById("logout-form");
  const link = document.querySelector("a.logout");
  if (form && link) {
    form.addEventListener("submit", clearSessionStorage);
    link.addEventListener("click", (event) => {
      event.preventDefault();
      if (window.confirm("ログアウトしますか？")) form.requestSubmit();
    });
  }

  const fallbackForm = document.getElementById("logout-confirm-form");
  if (fallbackForm) fallbackForm.addEventListener("submit", clearSessionStorage);
  const cancel = document.getElementById("logout-cancel");
  if (cancel) {
    cancel.addEventListener("click", (event) => {
      if (!document.referrer) return;
      const previous = new URL(document.referrer);
      if (previous.origin === window.location.origin && previous.pathname !== window.location.pathname) {
        event.preventDefault();
        window.history.back();
      }
    });
  }
});
