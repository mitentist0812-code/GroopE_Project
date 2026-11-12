const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = readFileSync(join(__dirname, "..", "apps", "static", "js", "mood-search.js"), "utf8");

function setup(geolocation) {
  const status = { textContent: "" };
  const loadingIndicator = { hidden: true };
  const forms = ["recommend", "free"].map((id) => ({
    id,
    submitButton: { disabled: false },
    elements: { latitude: {}, longitude: {} },
    querySelector() { return this.submitButton; },
    addEventListener(name, callback) { this.onSubmit = callback; },
    submit() { this.submitted = true; },
  }));
  const handlers = {};
  const document = {
    addEventListener(name, callback) { handlers[name] = callback; },
    querySelectorAll() { return forms; },
    querySelector(selector) {
      return selector === ".search-status" ? status : loadingIndicator;
    },
  };
  const window = { addEventListener(name, callback) { handlers[name] = callback; } };
  vm.runInNewContext(script, { document, window, navigator: { geolocation } });
  handlers.DOMContentLoaded();
  return { forms, status, loadingIndicator, handlers };
}

for (const id of ["recommend", "free"]) {
  test(`${id} shows loading through search and resets on return`, () => {
    let success;
    const state = setup({ getCurrentPosition(callback) { success = callback; } });
    const form = state.forms.find((item) => item.id === id);
    let prevented = false;
    form.onSubmit({ preventDefault() { prevented = true; } });
    assert.ok(prevented);
    assert.equal(state.loadingIndicator.hidden, false);
    assert.ok(state.forms.every((item) => item.submitButton.disabled));
    assert.match(state.status.textContent, /現在地を取得/);
    success({ coords: { latitude: 35, longitude: 139 } });
    assert.equal(form.elements.latitude.value, 35);
    assert.equal(form.elements.longitude.value, 139);
    assert.ok(form.submitted);
    assert.equal(state.loadingIndicator.hidden, false);
    assert.match(state.status.textContent, /検索しています/);
    state.handlers.pageshow();
    assert.equal(state.loadingIndicator.hidden, true);
    assert.ok(state.forms.every((item) => !item.submitButton.disabled));
    assert.equal(state.status.textContent, "");
  });
}

test("location failure clears loading and enables retry", () => {
  let failure;
  const state = setup({ getCurrentPosition(success, error) { failure = error; } });
  state.forms[0].onSubmit({ preventDefault() {} });
  failure();
  assert.equal(state.loadingIndicator.hidden, true);
  assert.ok(state.forms.every((item) => !item.submitButton.disabled));
  assert.match(state.status.textContent, /現在地を取得できませんでした/);
});

test("unsupported geolocation does not start loading", () => {
  const state = setup(undefined);
  state.forms[0].onSubmit({ preventDefault() {} });
  assert.equal(state.loadingIndicator.hidden, true);
  assert.ok(state.forms.every((item) => !item.submitButton.disabled));
  assert.match(state.status.textContent, /位置情報を取得できません/);
});
