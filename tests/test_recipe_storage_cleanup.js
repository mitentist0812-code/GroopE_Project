const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = readFileSync(join(__dirname, "..", "apps", "static", "js", "recipes.js"), "utf8");

test("removes only the old browser recipe storage", () => {
  const storage = { postedRecipes: "old recipes", otherData: "keep" };
  vm.runInNewContext(script, {
    localStorage: { removeItem(key) { delete storage[key]; } },
  });
  assert.deepEqual(storage, { otherData: "keep" });
});

test("reports a storage removal failure", () => {
  let notice;
  const document = {
    createElement() {
      return { setAttribute(name, value) { this[name] = value; } };
    },
    querySelector() {
      return { prepend(element) { notice = element; } };
    },
  };
  vm.runInNewContext(script, {
    localStorage: { removeItem() { throw new Error("storage blocked"); } },
    document,
    console: { error() {} },
  });
  assert.equal(notice.role, "alert");
  assert.match(notice.textContent, /削除できませんでした/);
});
