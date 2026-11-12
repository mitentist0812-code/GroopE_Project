document.addEventListener("DOMContentLoaded", () => {
  const forms = document.querySelectorAll("#recommend, #free");
  const status = document.querySelector(".search-status");
  const loadingIndicator = document.querySelector(".search-loading");

  const setLoading = (loading) => {
    forms.forEach((form) => {
      form.querySelector('input[type="submit"]').disabled = loading;
    });
    loadingIndicator.hidden = !loading;
  };

  window.addEventListener("pageshow", () => {
    setLoading(false);
    status.textContent = "";
  });

  forms.forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!navigator.geolocation) {
        status.textContent = "このブラウザでは位置情報を取得できません。";
        return;
      }

      setLoading(true);
      status.textContent = "現在地を取得しています。位置情報の利用を許可してください。";
      navigator.geolocation.getCurrentPosition(
        (position) => {
          form.elements.latitude.value = position.coords.latitude;
          form.elements.longitude.value = position.coords.longitude;
          status.textContent = form.id === "recommend"
            ? "AIの提案と店舗を検索しています。しばらくお待ちください。"
            : "店舗を検索しています。しばらくお待ちください。";
          form.submit();
        },
        () => {
          status.textContent = "現在地を取得できませんでした。位置情報の設定を確認して、もう一度お試しください。";
          setLoading(false);
        },
        { timeout: 15000, maximumAge: 0 }
      );
    });
  });
});
