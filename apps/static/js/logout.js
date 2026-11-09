document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("a.logout").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      window.alert("ログアウトしました。");
      window.sessionStorage.clear();
      window.location.assign(link.href);
    });
  });
});
