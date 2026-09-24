import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";

import App from "../App.jsx";
import client from "../api/client.js";
import { AuthProvider } from "../auth/AuthContext.jsx";

let container;
let root;

export function mountContainer() {
  localStorage.clear();
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  container = document.createElement("div");
  document.body.appendChild(container);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  return container;
}

export async function unmountContainer() {
  if (root) await act(async () => root.unmount());
  root = null;
  container.remove();
  delete globalThis.IS_REACT_ACT_ENVIRONMENT;
}

export function signInAs(role, shopId = null) {
  localStorage.setItem(
    "fashion_auth",
    JSON.stringify({ token: "test-token", role, shop_id: shopId }),
  );
}

export async function renderAt(path) {
  root = createRoot(container);
  await act(async () =>
    root.render(
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>,
    ),
  );
}

// Matches on the label's own caption, so option text inside a <select> does not interfere.
function findField(labelText, { scope = container, index = 0 } = {}) {
  const labels = [...scope.querySelectorAll("label")].filter(
    (label) => label.firstChild?.textContent.trim() === labelText,
  );
  const label = labels[index];
  if (!label) throw new Error(`Không tìm thấy trường "${labelText}"`);
  return label.querySelector("input, select, textarea");
}

export function field(labelText, options) {
  return findField(labelText, options);
}

export async function fill(labelText, value, options) {
  await setValue(findField(labelText, options), value);
}

export async function setValue(input, value) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(input.constructor.prototype, "value").set;
    setter.call(input, value);
    input.dispatchEvent(
      new Event(input.tagName === "SELECT" ? "change" : "input", { bubbles: true }),
    );
  });
}

export function buttons(scope = container) {
  return [...scope.querySelectorAll("button")];
}

export function buttonLabels(scope) {
  return buttons(scope).map((button) => button.textContent);
}

export function button(text, scope = container) {
  const match = buttons(scope).find((item) => item.textContent === text);
  if (!match) throw new Error(`Không tìm thấy nút "${text}"`);
  return match;
}

export async function click(element) {
  await act(async () => element.click());
}

export async function submit(form) {
  await act(async () =>
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })),
  );
}

export function rowContaining(text, scope = container) {
  return [...scope.querySelectorAll("tr, article")].find((row) => row.textContent.includes(text));
}

export function dialog() {
  return container.querySelector('[role="dialog"]');
}

export function alertText() {
  return container.querySelector('[role="alert"]')?.textContent;
}

export function routeGet(routes) {
  return vi.spyOn(client, "get").mockImplementation(async (url, options) => {
    if (!(url in routes)) throw new Error(`GET ${url} chưa được mock`);
    const data = routes[url];
    return { data: typeof data === "function" ? data(options) : data };
  });
}
