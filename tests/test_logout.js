const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = readFileSync(join(__dirname, "..", "apps", "static", "js", "logout.js"), "utf8");

function setup(confirmed, referrer = "") {
  const callbacks = {};
  const form = {
    addEventListener(name, callback) { callbacks[`form-${name}`] = callback; },
    requestSubmit() { callbacks["form-submit"](); submissions++; },
  };
  const link = { addEventListener(name, callback) { callbacks[`link-${name}`] = callback; } };
  const fallback = { addEventListener(name, callback) { callbacks[`fallback-${name}`] = callback; } };
  const cancel = { addEventListener(name, callback) { callbacks[`cancel-${name}`] = callback; } };
  let cleared = 0;
  let submissions = 0;
  let back = 0;
  const document = {
    referrer,
    addEventListener(name, callback) { callbacks[name] = callback; },
    querySelector(selector) { return selector === "a.logout" ? link : null; },
    getElementById(id) {
      return { "logout-form": form, "logout-confirm-form": fallback, "logout-cancel": cancel }[id] || null;
    },
  };
  const window = {
    confirm(message) { assert.equal(message, "ログアウトしますか？"); return confirmed; },
    location: { origin: "http://localhost", pathname: "/auth/logout" },
    sessionStorage: { clear() { cleared++; } },
    history: { back() { back++; } },
  };
  vm.runInNewContext(script, { document, window, URL, console });
  callbacks.DOMContentLoaded();
  return { callbacks, counts: () => ({ cleared, submissions, back }) };
}

test("cancelling the dialog leaves the session untouched", () => {
  const { callbacks, counts } = setup(false);
  let prevented = false;
  callbacks["link-click"]({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.deepEqual(counts(), { cleared: 0, submissions: 0, back: 0 });
});

test("confirming the dialog submits the logout form and clears session storage", () => {
  const { callbacks, counts } = setup(true);
  callbacks["link-click"]({ preventDefault() {} });
  assert.deepEqual(counts(), { cleared: 1, submissions: 1, back: 0 });
});

test("fallback confirmation still clears storage and cancel returns to the previous page", () => {
  const { callbacks, counts } = setup(false, "http://localhost/users/");
  let prevented = false;
  callbacks["cancel-click"]({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.deepEqual(counts(), { cleared: 0, submissions: 0, back: 1 });
  callbacks["fallback-submit"]();
  assert.deepEqual(counts(), { cleared: 1, submissions: 0, back: 1 });
});
