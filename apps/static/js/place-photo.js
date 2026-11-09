(() => {
    const photo = document.getElementById("place-photo");
    if (!photo || !photo.dataset.fallback) return;

    const showFallback = () => {
        photo.src = photo.dataset.fallback;
        photo.alt = "店舗画像なし";
        document.getElementById("photo-error").hidden = false;
        document.getElementById("photo-attribution").hidden = true;
    };
    photo.addEventListener("error", showFallback, { once: true });
    if (photo.complete && photo.naturalWidth === 0) showFallback();
})();
