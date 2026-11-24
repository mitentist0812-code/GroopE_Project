const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = readFileSync(join(__dirname, "..", "apps", "static", "js", "calorie.js"), "utf8");

function setup() {
  const elements = {};
  const handlers = {};
  const revoked = [];
  for (const id of [
    "meal-photo", "photo-picker", "photo-preview", "preview-image", "preview-name",
    "change-photo", "photo-error", "estimate-button", "result-message", "calorie-results",
    "dish-name", "ingredient-details", "ingredient-list", "calorie-total", "add-ingredient",
    "edit-ingredients",
  ]) {
    handlers[id] = {};
    elements[id] = {
      addEventListener(name, callback) { handlers[id][name] = callback; },
    };
  }
  elements["estimate-button"].dataset = { authenticated: "true" };
  let clicked = 0;
  elements["meal-photo"].click = () => { clicked += 1; };
  let count = 0;
  const URL = {
    createObjectURL() { count += 1; return `blob:${count}`; },
    revokeObjectURL(url) { revoked.push(url); },
  };
  const document = {
    addEventListener(name, callback) { callback(); },
    querySelector(selector) { return elements[selector.slice(1)]; },
  };
  vm.runInNewContext(script, { document, URL });
  return { elements, handlers, revoked, clicks: () => clicked };
}

test("replaces the picker with the selected photo and allows changing it", () => {
  const { elements, handlers, revoked, clicks } = setup();
  const input = elements["meal-photo"];
  input.files = [{ name: "first.png", type: "image/png", size: 10 }];
  handlers["meal-photo"].change();
  assert.equal(elements["photo-picker"].hidden, true);
  assert.equal(elements["photo-preview"].hidden, false);
  assert.equal(elements["preview-name"].textContent, "first.png");
  assert.equal(elements["estimate-button"].disabled, false);
  handlers["change-photo"].click();
  assert.equal(clicks(), 1);
  input.files = [{ name: "second.jpg", type: "image/jpeg", size: 10 }];
  handlers["meal-photo"].change();
  assert.equal(elements["preview-name"].textContent, "second.jpg");
  assert.equal(elements["preview-image"].src, "blob:2");
  assert.deepEqual(revoked, ["blob:1"]);
});

test("restores the picker when the selected image cannot be used", () => {
  const { elements, handlers, revoked } = setup();
  const input = elements["meal-photo"];
  input.files = [{ name: "bad.png", type: "image/png", size: 10 }];
  handlers["meal-photo"].change();
  handlers["preview-image"].error();
  assert.equal(elements["photo-picker"].hidden, false);
  assert.equal(elements["photo-preview"].hidden, true);
  assert.equal(elements["photo-error"].hidden, false);
  assert.equal(elements["estimate-button"].disabled, true);
  assert.equal(input.value, "");
  assert.deepEqual(revoked, ["blob:1"]);
});
