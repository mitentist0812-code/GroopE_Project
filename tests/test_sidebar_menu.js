const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = readFileSync(join(__dirname, "..", "apps", "static", "js", "sidebar-menu.js"), "utf8");

function setup() {
  const callbacks = {};
  const attributes = {};
  const classes = new Set();
  const link = { addEventListener(name, callback) { callbacks[`link-${name}`] = callback; } };
  const sidebar = {
    classList: {
      contains(name) { return classes.has(name); },
      toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); },
    },
    querySelectorAll() { return [link]; },
    contains(target) { return target === this; },
  };
  const toggle = {
    addEventListener(name, callback) { callbacks[`toggle-${name}`] = callback; },
    setAttribute(name, value) { attributes[name] = value; },
    contains(target) { return target === this; },
    focus() { callbacks.focused = true; },
  };
  const document = {
    documentElement: { classList: { add(name) { classes.add(name); } } },
    addEventListener(name, callback) { callbacks[name] = callback; },
    querySelector(selector) { return selector === "#sidebar" ? sidebar : toggle; },
    querySelectorAll() { return []; },
  };
  const window = { innerWidth: 390, addEventListener(name, callback) { callbacks[name] = callback; } };
  vm.runInNewContext(script, { document, window });
  callbacks.DOMContentLoaded();
  return { callbacks, attributes, classes, sidebar, toggle, window };
}

test("menu opens and closes, including outside click and Escape", () => {
  const state = setup();
  state.callbacks["toggle-click"]();
  assert.equal(state.attributes["aria-expanded"], "true");
  assert.ok(state.classes.has("is-open"));
  state.callbacks.click({ target: state.sidebar });
  assert.ok(state.classes.has("is-open"));
  state.callbacks.click({ target: {} });
  assert.equal(state.attributes["aria-expanded"], "false");
  state.callbacks["toggle-click"]();
  state.callbacks.keydown({ key: "Escape" });
  assert.equal(state.attributes["aria-expanded"], "false");
  assert.ok(state.callbacks.focused);
  state.callbacks["toggle-click"]();
  state.window.innerWidth = 1000;
  state.callbacks.resize();
  assert.equal(state.attributes["aria-expanded"], "false");
});
