const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = readFileSync(join(__dirname, "..", "apps", "static", "js", "home-search-ui.js"), "utf8");

test("selecting a mood fills the search field and closes the picker", () => {
  const callbacks = {};
  const button = {
    dataset: { mood: "がっつり" },
    addEventListener(name, callback) { callbacks[name] = callback; },
  };
  const input = { value: "", focus() { this.focused = true; } };
  const picker = { open: true };
  const document = {
    addEventListener(name, callback) { callbacks[name] = callback; },
    querySelectorAll(selector) { return selector === ".mood-card" ? [button] : []; },
    getElementById(id) { return id === "dishName" ? input : picker; },
  };
  vm.runInNewContext(script, { document });
  callbacks.DOMContentLoaded();
  callbacks.click();
  assert.equal(input.value, "がっつり");
  assert.equal(picker.open, false);
  assert.equal(input.focused, true);
});
