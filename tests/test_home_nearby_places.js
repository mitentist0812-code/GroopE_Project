const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const script = readFileSync(join(__dirname, "..", "apps", "static", "js", "nearby-places.js"), "utf8");

class Element {
  constructor() {
    this.children = [];
    this.dataset = {};
    this._textContent = "";
  }

  appendChild(child) {
    this.children.push(child);
  }

  append(...children) {
    this.children.push(...children);
  }

  replaceChildren(...children) {
    this.children = children;
    this._textContent = "";
  }

  get childElementCount() {
    return this.children.length;
  }

  set textContent(value) {
    this._textContent = String(value);
    this.children = [];
  }

  get textContent() {
    return this._textContent + this.children.map((child) => child.textContent).join("");
  }
}

function setup(places) {
  const section = new Element();
  section.dataset.nearbyUrl = "/nearby";
  const status = new Element();
  const list = new Element();
  section.querySelector = () => list;
  const moreLink = new Element();
  moreLink.href = "https://app.test/results";
  let onReady;
  let onPosition;
  let fetchedUrl;
  const document = {
    addEventListener(name, callback) {
      if (name === "DOMContentLoaded") onReady = callback;
    },
    querySelector(selector) {
      return {
        "#nearby-places": section,
        "#nearby-status": status,
        "#nearby-more-link": moreLink,
      }[selector];
    },
    createElement() {
      return new Element();
    },
  };
  const navigator = {
    geolocation: {
      getCurrentPosition(success) {
        onPosition = success;
      },
    },
  };

  vm.runInNewContext(script, {
    document,
    navigator,
    window: { location: { href: "https://app.test/" } },
    URL,
    Number,
    Math,
    fetch: async (url) => {
      fetchedUrl = url;
      return { ok: true, json: async () => ({ places }) };
    },
  });
  onReady();
  return {
    completeLocation: async () => onPosition({ coords: { latitude: 35.68, longitude: 139.76 } }),
    fetchedUrl: () => fetchedUrl,
    list,
    moreLink,
    status,
  };
}

test("loads and safely renders nearby places after obtaining browser location", async () => {
  const state = setup([{
    name: "<img src=x>",
    address: "東京都",
    rating: 4.5,
    distance: 125,
    url: "https://maps.google.com/?q=place",
  }]);

  await state.completeLocation();

  assert.equal(state.fetchedUrl(), "https://app.test/nearby?latitude=35.68&longitude=139.76");
  assert.equal(state.status.textContent, "");
  const [card] = state.list.children;
  const [thumb, info] = card.children;
  const [heading, details, address] = info.children;
  assert.equal(thumb.textContent, "店");
  assert.equal(heading.children[0].textContent, "<img src=x>");
  assert.equal(heading.children[0].target, "_blank");
  assert.equal(details.textContent, "⭐ 4.5　📍 約125m");
  assert.equal(address.textContent, "東京都");

  const moreUrl = new URL(state.moreLink.href);
  assert.equal(moreUrl.searchParams.get("keyword"), "飲食店");
  assert.equal(moreUrl.searchParams.get("latitude"), "35.68");
  assert.equal(moreUrl.searchParams.get("longitude"), "139.76");
});
