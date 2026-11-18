try {
  localStorage.removeItem("postedRecipes");
} catch (error) {
  console.error("以前のブラウザー内レシピを削除できませんでした。", error);
  const notice = document.createElement("p");
  notice.setAttribute("role", "alert");
  notice.textContent = "以前のブラウザー内レシピを削除できませんでした。ブラウザーの保存データを確認してください。";
  document.querySelector("main").prepend(notice);
}
