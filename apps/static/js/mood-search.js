document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("recommend");
  const status = document.getElementById("location-status");
  const submit = form.querySelector('input[type="submit"]');

  window.addEventListener("pageshow", () => {
    submit.disabled = false;
    status.textContent = "";
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!navigator.geolocation) {
      status.textContent = "このブラウザでは位置情報を取得できません。";
      return;
    }

    submit.disabled = true;
    status.textContent = "現在地を取得しています。位置情報の利用を許可してください。";
    navigator.geolocation.getCurrentPosition(
      (position) => {
        form.elements.latitude.value = position.coords.latitude;
        form.elements.longitude.value = position.coords.longitude;
        status.textContent = "AIの提案と店舗を検索しています。しばらくお待ちください。";
        form.submit();
      },
      () => {
        status.textContent = "現在地を取得できませんでした。位置情報の設定を確認して、もう一度お試しください。";
        submit.disabled = false;
      },
      { timeout: 15000, maximumAge: 0 }
    );
  });
});
