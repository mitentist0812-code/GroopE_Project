document.addEventListener("DOMContentLoaded", () => {
  const photoInput = document.querySelector("#meal-photo");
  const photoPicker = document.querySelector("#photo-picker");
  const preview = document.querySelector("#photo-preview");
  const previewImage = document.querySelector("#preview-image");
  const previewName = document.querySelector("#preview-name");
  const changePhotoButton = document.querySelector("#change-photo");
  const errorMessage = document.querySelector("#photo-error");
  const estimateButton = document.querySelector("#estimate-button");
  const resultMessage = document.querySelector("#result-message");
  const results = document.querySelector("#calorie-results");
  const dishName = document.querySelector("#dish-name");
  const ingredientDetails = document.querySelector("#ingredient-details");
  const list = document.querySelector("#ingredient-list");
  const total = document.querySelector("#calorie-total");
  const addButton = document.querySelector("#add-ingredient");
  const editButton = document.querySelector("#edit-ingredients");
  const isAuthenticated = estimateButton.dataset.authenticated === "true";
  let previewUrl = "";
  let editing = false;

  function updateTotal() {
    const rows = [...list.querySelectorAll(".calorie-ingredient")];
    let calories = 0;
    let matched = 0;
    rows.forEach((row) => {
      const food = row.querySelector("select");
      const grams = row.querySelector('input[type="number"]');
      const query = row.querySelector('input[type="search"]');
      const summary = row.querySelector(".ingredient-summary");
      const reference = row.querySelector(".ingredient-reference");
      const valid = food.value && grams.validity.valid && grams.value !== "";
      summary.textContent = `${query.value.trim() || "材料名未入力"}：${grams.value || "未入力"} g`;
      reference.textContent = food.value
        ? `自動選択または編集した食品：${food.selectedOptions[0].textContent}`
        : "食品が未選択です。材料を編集して食品を選んでください。";
      if (!valid) return;
      calories += Number(food.selectedOptions[0].dataset.calories) * Number(grams.value) / 100;
      matched += 1;
    });
    if (!matched) {
      total.textContent = "合計は未計算です。材料を編集して食品と量を選んでください。";
    } else if (matched < rows.length) {
      total.textContent = `照合済みの材料の小計：約${Math.round(calories)} kcal（${rows.length - matched}件は未計算）`;
    } else {
      total.textContent = `推定合計：約${Math.round(calories)} kcal`;
    }
  }

  function setEditing(value) {
    editing = value;
    editButton.textContent = editing ? "編集を終了" : "材料を編集";
    editButton.setAttribute("aria-expanded", String(editing));
    addButton.hidden = !editing;
    list.querySelectorAll(".ingredient-editor").forEach((editor) => {
      editor.hidden = !editing;
    });
  }

  async function searchFood(row) {
    const query = row.querySelector('input[type="search"]');
    const select = row.querySelector("select");
    const message = row.querySelector(".food-search-status");
    const button = row.querySelector(".food-search-button");
    select.replaceChildren(new Option("食品を選択してください", ""));
    updateTotal();
    if (!query.value.trim()) {
      message.textContent = "食品名を入力してください。";
      return;
    }
    const searched = query.value;
    button.disabled = true;
    message.textContent = "食品を検索しています。";
    try {
      const url = new URL(estimateButton.dataset.foodsUrl, window.location.href);
      url.searchParams.set("q", searched);
      const response = await fetch(url);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "食品を検索できませんでした。");
      if (query.value !== searched) return;
      data.foods.forEach((food) => {
        const option = new Option(`${food.name}（${food.kcal_per_100g} kcal / 100g）`, food.id);
        option.dataset.calories = food.kcal_per_100g;
        select.add(option);
      });
      message.textContent = data.foods.length
        ? (data.truncated ? "候補が多いため先頭50件を表示しています。食品名を絞り込めます。" : "食品を選択してください。")
        : "該当する食品がありません。別の名前で検索してください。";
    } catch (error) {
      message.textContent = error instanceof Error ? error.message : "食品を検索できませんでした。";
    } finally {
      button.disabled = false;
    }
  }

  function addIngredient(name = "", grams = "", matchedFood = null) {
    if (list.children.length >= 20) {
      resultMessage.textContent = "材料は20件まで追加できます。";
      return;
    }
    const row = document.createElement("section");
    row.className = "calorie-ingredient";
    const summary = document.createElement("strong");
    summary.className = "ingredient-summary";
    const reference = document.createElement("p");
    reference.className = "ingredient-reference";
    const editor = document.createElement("div");
    editor.className = "ingredient-editor";
    editor.hidden = !editing;
    const nameLabel = document.createElement("label");
    nameLabel.textContent = "材料名 ";
    const query = document.createElement("input");
    query.type = "search";
    query.maxLength = 80;
    query.value = name;
    nameLabel.append(query);
    const search = document.createElement("button");
    search.type = "button";
    search.className = "food-search-button";
    search.textContent = "食品を検索";
    const status = document.createElement("p");
    status.className = "food-search-status";
    status.setAttribute("role", "status");
    const foodLabel = document.createElement("label");
    foodLabel.textContent = "食品成分表の食品 ";
    const select = document.createElement("select");
    select.add(new Option("食品を選択してください", ""));
    if (matchedFood) {
      const option = new Option(
        `${matchedFood.name}（${matchedFood.kcal_per_100g} kcal / 100g）`,
        matchedFood.id,
        true,
        true,
      );
      option.dataset.calories = matchedFood.kcal_per_100g;
      select.add(option);
    }
    foodLabel.append(select);
    const gramsLabel = document.createElement("label");
    gramsLabel.textContent = "量（g） ";
    const amount = document.createElement("input");
    amount.type = "number";
    amount.min = "0.1";
    amount.max = "10000";
    amount.step = "any";
    amount.value = grams;
    gramsLabel.append(amount);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "材料を削除";
    editor.append(nameLabel, search, status, foodLabel, gramsLabel, remove);
    row.append(summary, reference, editor);
    list.append(row);
    search.addEventListener("click", () => searchFood(row));
    query.addEventListener("input", () => {
      select.replaceChildren(new Option("食品を選択してください", ""));
      status.textContent = "材料名を変更しました。食品を再検索してください。";
      updateTotal();
    });
    select.addEventListener("change", updateTotal);
    amount.addEventListener("input", updateTotal);
    remove.addEventListener("click", () => {
      row.remove();
      updateTotal();
    });
    updateTotal();
  }

  photoInput.addEventListener("change", () => {
    const file = photoInput.files[0];
    errorMessage.hidden = true;
    errorMessage.textContent = "";
    estimateButton.disabled = true;
    preview.hidden = true;
    photoPicker.hidden = false;
    results.hidden = true;
    resultMessage.textContent = "写真を選択すると、ここに推定結果が表示されます。";
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = "";
    if (!file) return;
    if (!file.type.startsWith("image/") || file.size > 10 * 1024 * 1024) {
      errorMessage.textContent = "画像ファイルを10MB以下で選択してください。";
      errorMessage.hidden = false;
      photoInput.value = "";
      return;
    }
    previewUrl = URL.createObjectURL(file);
    previewImage.src = previewUrl;
    previewName.textContent = file.name;
    preview.hidden = false;
    photoPicker.hidden = true;
    estimateButton.disabled = !isAuthenticated;
    resultMessage.textContent = "写真の準備ができました。「カロリーを推定する」を押してください。";
  });

  previewImage.addEventListener("error", () => {
    preview.hidden = true;
    photoPicker.hidden = false;
    estimateButton.disabled = true;
    photoInput.value = "";
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = "";
    errorMessage.textContent = "この画像はプレビューできません。別の画像を選択してください。";
    errorMessage.hidden = false;
  });

  changePhotoButton.addEventListener("click", () => photoInput.click());

  estimateButton.addEventListener("click", async () => {
    if (!isAuthenticated || !photoInput.files[0]) return;
    estimateButton.disabled = true;
    photoInput.disabled = true;
    changePhotoButton.disabled = true;
    results.hidden = true;
    resultMessage.textContent = "写真を解析しています。しばらくお待ちください。";
    try {
      const scale = Math.min(1, 1600 / Math.max(previewImage.naturalWidth, previewImage.naturalHeight));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(previewImage.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(previewImage.naturalHeight * scale));
      const context = canvas.getContext("2d");
      if (!context || !previewImage.naturalWidth) throw new Error("画像を読み込めませんでした。");
      context.drawImage(previewImage, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
      if (!blob) throw new Error("画像を変換できませんでした。");
      const form = new FormData();
      form.append("photo", blob, "meal.jpg");
      form.append("csrf_token", estimateButton.dataset.csrfToken);
      const response = await fetch(estimateButton.dataset.analyzeUrl, { method: "POST", body: form });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "画像解析に失敗しました。");
      if (!data.is_food) {
        resultMessage.textContent = "料理を確認できませんでした。別の写真をお試しください。";
        return;
      }
      list.replaceChildren();
      dishName.textContent = `料理の候補：${data.dish}`;
      resultMessage.textContent = "材料一覧を開いて、推定した材料と食品を確認してください。";
      setEditing(false);
      ingredientDetails.open = false;
      results.hidden = false;
      data.ingredients.forEach((item) => addIngredient(item.name, item.grams, item.food));
    } catch (error) {
      resultMessage.textContent = error instanceof Error ? error.message : "画像解析に失敗しました。";
    } finally {
      photoInput.disabled = false;
      changePhotoButton.disabled = false;
      estimateButton.disabled = !isAuthenticated || !photoInput.files[0];
    }
  });

  addButton.addEventListener("click", () => addIngredient());
  editButton.addEventListener("click", () => setEditing(!editing));
});
