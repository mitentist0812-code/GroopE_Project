document.addEventListener("DOMContentLoaded", () => {
  const section = document.querySelector("#nearby-places");
  const status = document.querySelector("#nearby-status");
  const list = section && section.querySelector(".nearby-list");
  const moreLink = document.querySelector("#nearby-more-link");

  if (!section || !status || !list) return;

  function showError(message) {
    status.textContent = message;
    list.replaceChildren();
  }

  function renderPlaces(places) {
    list.replaceChildren();
    if (places.length === 0) {
      status.textContent = "近くにお店が見つかりませんでした。";
      return;
    }

    places.forEach((place) => {
      if (!place || typeof place.name !== "string") return;

      const card = document.createElement("article");
      card.className = "nearby-card";
      const thumb = document.createElement("div");
      thumb.className = "thumb";
      thumb.textContent = "店";

      const info = document.createElement("div");
      info.className = "info";
      const heading = document.createElement("h4");
      if (typeof place.url === "string" && place.url.startsWith("https://")) {
        const nameLink = document.createElement("a");
        nameLink.href = place.url;
        nameLink.textContent = place.name;
        nameLink.target = "_blank";
        nameLink.rel = "noopener noreferrer";
        heading.appendChild(nameLink);
      } else {
        heading.textContent = place.name;
      }

      const details = document.createElement("p");
      const rating = Number.isFinite(place.rating) ? `⭐ ${place.rating}` : "評価情報なし";
      const distance = Number.isFinite(place.distance) ? `📍 約${Math.round(place.distance)}m` : "距離情報なし";
      details.textContent = `${rating}　${distance}`;
      const address = document.createElement("p");
      address.textContent = typeof place.address === "string" ? place.address : "";

      info.append(heading, details, address);
      card.append(thumb, info);
      list.appendChild(card);
    });
    status.textContent = list.childElementCount
      ? ""
      : "近くのお店の情報を表示できませんでした。";
  }

  if (!navigator.geolocation) {
    showError("このブラウザーでは現在地を取得できません。");
    return;
  }

  navigator.geolocation.getCurrentPosition(async (position) => {
    const { latitude, longitude } = position.coords;
    const url = new URL(section.dataset.nearbyUrl, window.location.href);
    url.searchParams.set("latitude", latitude);
    url.searchParams.set("longitude", longitude);

    if (moreLink) {
      const resultsUrl = new URL(moreLink.href, window.location.href);
      resultsUrl.searchParams.set("keyword", "飲食店");
      resultsUrl.searchParams.set("latitude", latitude);
      resultsUrl.searchParams.set("longitude", longitude);
      moreLink.href = resultsUrl.toString();
    }

    status.textContent = "近くのお店を検索しています。";
    try {
      const response = await fetch(url.toString());
      const data = await response.json();
      if (!response.ok) {
        showError(typeof data.error === "string" ? data.error : "近くのお店を取得できませんでした。");
        return;
      }
      if (!Array.isArray(data.places)) {
        showError("近くのお店の情報を取得できませんでした。");
        return;
      }
      renderPlaces(data.places);
    } catch {
      showError("近くのお店を取得できませんでした。時間をおいて再度お試しください。");
    }
  }, () => {
    showError("現在地を取得できませんでした。位置情報を許可すると近くのお店を表示できます。");
  }, { timeout: 15000, maximumAge: 0 });
});
