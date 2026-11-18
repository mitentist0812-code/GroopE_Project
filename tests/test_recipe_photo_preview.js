const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = readFileSync(join(__dirname, "..", "apps", "static", "js", "recipe-photo-preview.js"), "utf8");

function setup() {
  const handlers = {};
  const revoked = [];
  let count = 0;
  const form = { addEventListener(name, callback) { handlers[name] = callback; } };
  const document = {
    addEventListener(name, callback) { handlers[name] = callback; },
    querySelector() { return form; },
  };
  const window = { addEventListener(name, callback) { handlers[name] = callback; } };
  const URL = {
    createObjectURL() { count += 1; return `blob:${count}`; },
    revokeObjectURL(url) { revoked.push(url); },
  };
  vm.runInNewContext(script, { document, window, URL, console });
  handlers.DOMContentLoaded();
  return { handlers, revoked };
}

function imageInput() {
  const preview = { hidden: true, src: "", removeAttribute() { this.src = ""; } };
  const error = { hidden: true, textContent: "" };
  const input = {
    files: [],
    matches() { return true; },
    parentElement: {
      querySelector(selector) {
        return selector === ".recipe-photo-preview" ? preview : error;
      },
    },
  };
  return { input, preview, error };
}

test("previews selected files and releases replaced and removed step photos", () => {
  const state = setup();
  const { input, preview, error } = imageInput();
  input.files = [{ type: "image/png", size: 10 }];
  state.handlers.change({ target: input });
  assert.equal(preview.src, "blob:1");
  assert.equal(preview.hidden, false);

  input.files = [{ type: "image/jpeg", size: 100 }];
  state.handlers.change({ target: input });
  assert.deepEqual(state.revoked, ["blob:1"]);
  assert.equal(preview.src, "blob:2");

  const button = { closest() { return { querySelector() { return input; } }; } };
  state.handlers.click({ target: { closest() { return button; } } });
  assert.deepEqual(state.revoked, ["blob:1", "blob:2"]);
  assert.equal(preview.hidden, true);
  assert.equal(error.hidden, true);
});

test("rejects unsupported and oversized files without displaying a preview", () => {
  const state = setup();
  const { input, preview, error } = imageInput();
  for (const file of [{ type: "image/svg+xml", size: 10 }, { type: "image/png", size: 300 * 1024 + 1 }]) {
    input.files = [file];
    state.handlers.change({ target: input });
    assert.equal(preview.hidden, true);
    assert.equal(error.hidden, false);
    assert.match(error.textContent, /300KB/);
  }
  input.files = [];
  state.handlers.change({ target: input });
  assert.equal(error.hidden, true);
});
