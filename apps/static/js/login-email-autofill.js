(() => {
  const storageKey = "rememberedLoginEmail";
  const emailInput = document.querySelector("#email");
  const preferenceToggle = document.querySelector("#remember-login-email");

  try {
    if (emailInput) {
      const savedEmail = localStorage.getItem(storageKey);
      if (savedEmail && !emailInput.value) emailInput.value = savedEmail;
    }

    if (preferenceToggle) {
      if (preferenceToggle.checked) {
        localStorage.setItem(storageKey, preferenceToggle.dataset.email);
      } else {
        localStorage.removeItem(storageKey);
      }
    }
  } catch (error) {
    console.error("ログイン用メールアドレスの自動入力を更新できませんでした。", error);
    const message = document.querySelector("#login-email-autofill-error");
    if (message) message.hidden = false;
  }
})();
