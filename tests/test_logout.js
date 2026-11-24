const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = readFileSync(join(__dirname, "..", "apps", "static", "js", "logout.js"), "utf8");

function setup(referrer) {
  const callbacks = {};
  const form = { addEventListener(name, callback) { callbacks[name] = callback; } };
  const cancel = { addEventListener(name, callback) { callbacks[`cancel-${name}`] = callback; } };
  let cleared = 0;
  let back = 0;
  const document = {
    referrer,
    addEventListener(name, callback) { callbacks[name] = callback; },
    getElementById(id) { return id === "logout-confirm-form" ? form : cancel; },
  };
  const window = {
    location: { origin: "http://localhost", pathname: "/auth/logout" },
    sessionStorage: { clear() { cleared++; } },
    history: { back() { back++; } },
  };
  vm.runInNewContext(script, { document, window, URL, console });
  callbacks.DOMContentLoaded();
  return { callbacks, counts: () => ({ cleared, back }) };
}

test("cancel returns to previous page without clearing session storage", () => {
  const { callbacks, counts } = setup("http://localhost/users/");
  let prevented = false;
  callbacks["cancel-click"]({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.deepEqual(counts(), { cleared: 0, back: 1 });
});

test("confirmation clears session storage, external referrer uses home fallback", () => {
  const { callbacks, counts } = setup("https://example.com/");
  let prevented = false;
  callbacks["cancel-click"]({ preventDefault() { prevented = true; } });
  assert.equal(prevented, false);
  callbacks.submit();
  assert.deepEqual(counts(), { cleared: 1, back: 0 });
});
