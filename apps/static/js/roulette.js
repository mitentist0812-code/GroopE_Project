document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("roulette-modal");
  const display = document.getElementById("roulette-display");
  const reel = display ? display.querySelector(".roulette-reel") : null;
  const result = document.getElementById("roulette-result");
  const winnerCard = document.getElementById("winner-card");
  const winnerName = document.getElementById("winner-name");
  const startButton = document.getElementById("start-roulette");
  const spinButton = document.getElementById("spin-roulette");
  const retryButton = document.getElementById("retry-roulette");
  const closeButton = document.getElementById("close-roulette");
  const selectedCount = document.getElementById("selected-count");

  if (
    !modal || !display || !reel || !result || !winnerCard || !winnerName ||
    !startButton || !spinButton || !retryButton || !closeButton || !selectedCount
  ) return;

  let candidates = [];
  let isSpinning = false;

  function getSelectedShops() {
    return Array.from(document.querySelectorAll(".roulette-shop:checked")).map((checkbox) => ({
      id: checkbox.value,
      name: checkbox.dataset.name || checkbox.value
    }));
  }

  function updateSelectedCount() {
    selectedCount.textContent = `${getSelectedShops().length}店舗`;
  }

  function makeItem(shop) {
    const item = document.createElement("div");
    const emoji = document.createElement("span");
    const name = document.createElement("b");
    item.className = "roulette-item";
    emoji.setAttribute("aria-hidden", "true");
    emoji.textContent = "🍽️";
    name.textContent = shop.name;
    item.append(emoji, name);
    return item;
  }

  function renderReel(shops, repetitions = 1) {
    reel.replaceChildren();
    reel.style.transition = "none";
    reel.style.transform = "translateY(0)";

    for (let copy = 0; copy < repetitions; copy++) {
      shops.forEach((shop) => reel.append(makeItem(shop)));
    }
  }

  function setStatus(title, message, spinning = false) {
    const status = document.getElementById("roulette-status");
    if (!status) return;

    status.replaceChildren();
    const dot = document.createElement("span");
    const text = document.createElement("div");
    const heading = document.createElement("strong");
    const detail = document.createElement("small");
    dot.className = "status-dot";
    dot.setAttribute("aria-hidden", "true");
    dot.textContent = spinning ? "◌" : "●";
    heading.textContent = title;
    detail.textContent = message;
    text.append(heading, detail);
    status.append(dot, text);
    status.classList.toggle("is-spinning", spinning);
  }

  function openModal() {
    candidates = getSelectedShops();
    if (candidates.length === 0) {
      alert("ルーレットに参加させる店舗を1つ以上選択してください。");
      return;
    }

    renderReel(candidates);
    winnerCard.hidden = true;
    retryButton.hidden = true;
    spinButton.hidden = false;
    spinButton.disabled = false;
    result.textContent = "";
    setStatus("準備完了！", `${candidates.length}店舗から抽選します。`);
    modal.hidden = false;
    closeButton.focus();
  }

  function closeModal() {
    if (isSpinning) return;
    modal.hidden = true;
    startButton.focus();
  }

  function spin() {
    if (isSpinning) return;

    candidates = getSelectedShops();
    if (candidates.length === 0) {
      alert("ルーレットに参加させる店舗を1つ以上選択してください。");
      return;
    }

    isSpinning = true;
    spinButton.disabled = true;
    retryButton.hidden = true;
    winnerCard.hidden = true;
    result.textContent = "";
    display.classList.remove("is-winner");
    setStatus("スロットが回転中…", "だんだん減速して当選店舗で止まります。", true);

    const winnerIndex = Math.floor(Math.random() * candidates.length);
    const winner = candidates[winnerIndex];
    const rounds = 16 + Math.floor(Math.random() * 5);
    renderReel(candidates, rounds + 1);

    const rowHeight = reel.querySelector(".roulette-item").getBoundingClientRect().height;
    const windowHeight = display.getBoundingClientRect().height;
    const centerOffset = (windowHeight - rowHeight) / 2;
    const fastRows = (rounds - 2) * candidates.length;
    const startRows = rounds * candidates.length;
    const fastDuration = 2500;
    const decelerationDuration = 1500;

    reel.style.transform = `translateY(${centerOffset - startRows * rowHeight}px)`;
    void reel.offsetHeight;
    display.classList.add("is-spinning");
    reel.style.transition = `transform ${fastDuration}ms linear, filter 100ms ease-out`;
    reel.style.transform = `translateY(${centerOffset - (startRows - fastRows) * rowHeight}px)`;

    window.setTimeout(() => {
      reel.style.transition = `transform ${decelerationDuration}ms cubic-bezier(.2,.75,.25,1), filter 350ms ease-out`;
      display.classList.remove("is-spinning");
      reel.style.transform = `translateY(${centerOffset - winnerIndex * rowHeight}px)`;
    }, fastDuration);

    window.setTimeout(() => {
      const previous = candidates[(winnerIndex + candidates.length - 1) % candidates.length];
      const next = candidates[(winnerIndex + 1) % candidates.length];
      reel.replaceChildren(makeItem(previous), makeItem(winner), makeItem(next));
      reel.style.transition = "none";
      reel.style.transform = `translateY(${-rowHeight + centerOffset}px)`;
      winnerName.textContent = winner.name;
      winnerCard.hidden = false;
      display.classList.add("is-winner");
      result.textContent = `当選店舗：${winner.name}`;
      setStatus("抽選が完了しました！", "今回のお店が決まりました。");
      spinButton.hidden = true;
      spinButton.disabled = false;
      retryButton.hidden = false;
      isSpinning = false;
    }, fastDuration + decelerationDuration + 100);
  }

  startButton.addEventListener("click", openModal);
  closeButton.addEventListener("click", closeModal);
  spinButton.addEventListener("click", spin);
  retryButton.addEventListener("click", spin);
  document.querySelectorAll(".roulette-shop").forEach((checkbox) => {
    checkbox.addEventListener("change", updateSelectedCount);
  });
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) closeModal();
  });

  updateSelectedCount();
});
