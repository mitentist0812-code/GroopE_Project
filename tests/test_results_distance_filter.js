const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const scripts = ["roulette.js", "results-distance-filter.js"].map((file) =>
  readFileSync(join(__dirname, "..", "apps", "static", "js", file), "utf8")
);

function element() {
  return {
    hidden: false,
    disabled: false,
    textContent: "",
    dataset: {},
    style: {},
    children: [],
    handlers: {},
    classList: { toggle() {}, remove() {}, add() {} },
    addEventListener(name, callback) { this.handlers[name] = callback; },
    setAttribute() {},
    append(...items) { this.children.push(...items); },
    replaceChildren(...items) { this.children = items; },
    focus() {},
  };
}

function setup(distances, mode = "local") {
  const results = distances.map((distance, index) => {
    const result = element();
    result.dataset.distance = String(distance);
    const checkbox = element();
    checkbox.checked = true;
    checkbox.value = String(index);
    checkbox.dataset.name = `店${index}`;
    checkbox.closest = () => result;
    result.checkbox = checkbox;
    return result;
  });
  const ids = [
    "roulette-modal", "roulette-display", "roulette-result", "winner-card",
    "winner-name", "start-roulette", "spin-roulette", "retry-roulette",
    "close-roulette", "selected-count", "roulette-status", "distanceFilter",
    "distance-filter-empty",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, element()]));
  const reel = element();
  elements["roulette-display"].querySelector = () => reel;
  elements.distanceFilter.value = mode === "unlimited" ? "unlimited" : "10";
  elements.distanceFilter.dataset.searchMode = mode;
  elements.distanceFilter.form = { submissions: 0, requestSubmit() { this.submissions++; } };
  elements.distanceFilter.disabled = true;
  const handlers = {};
  const document = {
    getElementById(id) { return elements[id]; },
    createElement() { return element(); },
    querySelectorAll(selector) {
      if (selector === "#resultList .result") return results;
      if (selector === ".roulette-shop") return results.map((item) => item.checkbox);
      if (selector === ".roulette-shop:checked") return results.map((item) => item.checkbox).filter((item) => item.checked);
      throw new Error(`Unexpected selector: ${selector}`);
    },
    addEventListener(name, callback) { (handlers[name] ||= []).push(callback); },
    dispatchEvent(event) { (handlers[event.type] || []).forEach((callback) => callback(event)); },
  };
  class Event { constructor(type) { this.type = type; } }
  const alerts = [];
  const context = { document, Event, alert(message) { alerts.push(message); } };
  scripts.forEach((script) => vm.runInNewContext(script, context));
  document.dispatchEvent(new Event("DOMContentLoaded"));
  return { results, elements, alerts };
}

test("distance filter preserves precision, restores shops and updates roulette candidates", () => {
  const { results, elements, alerts } = setup([1000, 1000.1, 3000.1, 5000.1]);
  const filter = elements.distanceFilter;
  const count = elements["selected-count"];
  assert.equal(filter.disabled, false);
  assert.equal(count.textContent, "4店舗");

  for (const [radius, visible] of [["1", 1], ["3", 2], ["5", 3], ["10", 4]]) {
    filter.value = radius;
    filter.handlers.change();
    assert.equal(results.filter((item) => !item.hidden).length, visible);
    assert.equal(count.textContent, `${visible}店舗`);
    assert.equal(elements["distance-filter-empty"].hidden, true);
  }
  assert.ok(results.every((item) => item.checkbox.checked));
  filter.value = "1";
  filter.handlers.change();
  elements["start-roulette"].handlers.click();
  assert.equal(elements["roulette-modal"].hidden, false);
  assert.match(elements["roulette-status"].children[1].children[1].textContent, /1店舗/);
  assert.equal(alerts.length, 0);
});

test("switching unlimited mode performs a new search and leaves results unfiltered", () => {
  const local = setup([]);
  local.elements.distanceFilter.value = "unlimited";
  local.elements.distanceFilter.handlers.change();
  assert.equal(local.elements.distanceFilter.form.submissions, 1);

  const unlimited = setup([1000, 200000], "unlimited");
  assert.ok(unlimited.results.every((item) => !item.hidden));
  assert.equal(unlimited.elements["selected-count"].textContent, "2店舗");
  unlimited.elements.distanceFilter.value = "10";
  unlimited.elements.distanceFilter.handlers.change();
  assert.equal(unlimited.elements.distanceFilter.form.submissions, 1);
});

test("no matching shops displays feedback and excludes them from roulette", () => {
  const { results, elements, alerts } = setup([1000.1, 3000]);
  elements.distanceFilter.value = "1";
  elements.distanceFilter.handlers.change();
  assert.ok(results.every((item) => item.hidden));
  assert.equal(elements["distance-filter-empty"].hidden, false);
  assert.equal(elements["selected-count"].textContent, "0店舗");
  elements["start-roulette"].handlers.click();
  assert.equal(alerts.length, 1);
  elements.distanceFilter.value = "10";
  elements.distanceFilter.handlers.change();
  assert.equal(elements["distance-filter-empty"].hidden, true);
  assert.equal(elements["selected-count"].textContent, "2店舗");
});
