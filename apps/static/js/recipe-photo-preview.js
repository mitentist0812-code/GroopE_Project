document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("body.page-post-recipe form");
  if (!form) return;

  const urls = new Map();
  const clearPreview = (input) => {
    const url = urls.get(input);
    if (url) URL.revokeObjectURL(url);
    urls.delete(input);
    const preview = input.parentElement.querySelector(".recipe-photo-preview");
    preview.removeAttribute("src");
    preview.hidden = true;
  };

  form.addEventListener("change", (event) => {
    const input = event.target;
    if (!input.matches('input[type="file"]')) return;
    clearPreview(input);
    const error = input.parentElement.querySelector(".recipe-photo-preview-error");
    error.hidden = true;
    error.textContent = "";
    const file = input.files[0];
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/gif", "image/webp"].includes(file.type) || file.size > 300 * 1024) {
      error.textContent = "PNG・JPEG・GIF・WebP形式の300KB以下の画像を選択してください。";
      error.hidden = false;
      return;
    }

    try {
      const url = URL.createObjectURL(file);
      urls.set(input, url);
      const preview = input.parentElement.querySelector(".recipe-photo-preview");
      preview.src = url;
      preview.hidden = false;
    } catch (error) {
      console.error("画像のプレビューを表示できませんでした。", error);
      const message = input.parentElement.querySelector(".recipe-photo-preview-error");
      message.textContent = "画像のプレビューを表示できませんでした。";
      message.hidden = false;
    }
  });

  form.addEventListener("click", (event) => {
    const button = event.target.closest(".remove-step-button");
    if (!button) return;
    const input = button.closest(".step-item").querySelector('input[type="file"]');
    clearPreview(input);
  });

  window.addEventListener("pagehide", (event) => {
    if (event.persisted) return;
    for (const url of urls.values()) URL.revokeObjectURL(url);
    urls.clear();
  });
});
