(() => {
  const storageKey = "postedRecipes";
  const maxImageSize = 300 * 1024;

  const readRecipes = () => {
    const savedRecipes = localStorage.getItem(storageKey);
    if (savedRecipes === null) return [];

    const recipes = JSON.parse(savedRecipes);
    if (!Array.isArray(recipes)) {
      throw new Error("保存されたレシピの形式が正しくありません。");
    }
    return recipes
      .filter((recipe) =>
        recipe &&
        typeof recipe.id === "string" &&
        typeof recipe.title === "string" &&
        typeof recipe.createdAt === "string"
      )
      .map((recipe) => ({
        ...recipe,
        image: typeof recipe.image === "string" ? recipe.image : "",
        ingredients: Array.isArray(recipe.ingredients)
          ? recipe.ingredients.filter((ingredient) =>
            ingredient && typeof ingredient.name === "string" && typeof ingredient.amount === "string"
          )
          : [],
        steps: Array.isArray(recipe.steps)
          ? recipe.steps.filter((step) => step && typeof step.text === "string")
          : []
      }));
  };

  const readImage = (file) => {
    if (!file) return Promise.resolve("");
    if (!file.type.startsWith("image/")) {
      return Promise.reject(new Error("画像ファイルを選択してください。"));
    }
    if (file.size > maxImageSize) {
      return Promise.reject(new Error("画像は1枚300KB以下にしてください。"));
    }

    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.addEventListener("load", () => {
        if (typeof reader.result === "string") {
          resolve(reader.result);
        } else {
          reject(new Error("画像を読み込めませんでした。"));
        }
      });
      reader.addEventListener("error", () => reject(new Error("画像を読み込めませんでした。")));
      reader.readAsDataURL(file);
    });
  };

  const renderRecipes = () => {
    const list = document.querySelector("#mypage-recipes-list");
    if (!list) return;

    const message = document.querySelector("#mypage-recipes-message");
    list.replaceChildren();

    let recipes;
    try {
      recipes = readRecipes();
    } catch (error) {
      console.error("投稿したレシピを読み込めませんでした。", error);
      message.textContent = "投稿したレシピを読み込めませんでした。";
      return;
    }

    if (recipes.length === 0) {
      message.hidden = false;
      message.textContent = "投稿したレシピはまだありません。";
      return;
    }

    message.hidden = true;
    message.textContent = "";
    recipes.sort((first, second) => Date.parse(second.createdAt) - Date.parse(first.createdAt));

    recipes.forEach((recipe) => {
      const card = document.createElement("article");
      card.className = "mypage-recipe-card";

      if (typeof recipe.image === "string" && recipe.image.startsWith("data:image/")) {
        const image = document.createElement("img");
        image.className = "mypage-recipe-image";
        image.src = recipe.image;
        image.alt = `${recipe.title}の料理写真`;
        image.loading = "lazy";
        card.append(image);
      }

      const content = document.createElement("div");
      content.className = "mypage-recipe-content";

      const title = document.createElement("h4");
      title.textContent = recipe.title;
      content.append(title);

      const date = document.createElement("time");
      date.className = "mypage-recipe-date";
      date.dateTime = recipe.createdAt;
      const createdAt = new Date(recipe.createdAt);
      date.textContent = Number.isNaN(createdAt.getTime())
        ? "投稿日不明"
        : `投稿日：${createdAt.toLocaleDateString("ja-JP")}`;
      content.append(date);

      if (Array.isArray(recipe.ingredients) && recipe.ingredients.length > 0) {
        const ingredients = document.createElement("p");
        ingredients.className = "mypage-recipe-summary";
        ingredients.textContent = `材料：${recipe.ingredients
          .map((ingredient) => `${ingredient.name} ${ingredient.amount}`)
          .join("、")}`;
        content.append(ingredients);
      }

      if (Array.isArray(recipe.steps) && recipe.steps.some((step) => step.text)) {
        const steps = document.createElement("ol");
        steps.className = "mypage-recipe-steps";
        recipe.steps.forEach((step) => {
          if (!step.text) return;
          const item = document.createElement("li");
          item.textContent = step.text;
          steps.append(item);
        });
        content.append(steps);
      }

      card.append(content);
      list.append(card);
    });
  };

  const setupRecipeForm = () => {
    const form = document.querySelector("body.page-post-recipe form");
    if (!form) return;

    const message = document.querySelector("#recipe-post-message");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      message.hidden = true;

      try {
        const title = form.querySelector("#title").value.trim();
        const ingredientRows = Array.from(form.querySelectorAll(".ingredient-row"));
        const ingredients = ingredientRows.map((row) => ({
          name: row.querySelector('input[name="ingredient_name[]"]').value.trim(),
          amount: row.querySelector('input[name="ingredient_amount[]"]').value.trim()
        }));
        if (!title || ingredients.some((ingredient) => !ingredient.name || !ingredient.amount)) {
          throw new Error("レシピ名、材料名、分量を入力してください。");
        }

        const stepItems = Array.from(form.querySelectorAll(".step-item"));
        const steps = await Promise.all(stepItems.map(async (item) => ({
          text: item.querySelector('textarea[name="process[]"]').value.trim(),
          image: await readImage(item.querySelector('input[name="process_img[]"]').files[0])
        })));
        const image = await readImage(form.querySelector("#dishimg").files[0]);
        const recipe = {
          id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          title,
          createdAt: new Date().toISOString(),
          image,
          ingredients,
          steps
        };

        localStorage.setItem(storageKey, JSON.stringify([recipe, ...readRecipes()]));
        window.location.href = "mypage.html";
      } catch (error) {
        console.error("レシピを保存できませんでした。", error);
        if (error && error.name === "QuotaExceededError") {
          message.textContent = "ブラウザーの保存容量が不足しているため、レシピを保存できませんでした。";
        } else {
          message.textContent = error instanceof Error
            ? `レシピを保存できませんでした。${error.message}`
            : "レシピを保存できませんでした。";
        }
        message.hidden = false;
      }
    });
  };

  setupRecipeForm();
  renderRecipes();
})();
