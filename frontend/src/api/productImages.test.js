// @vitest-environment jsdom
import { afterEach, expect, it } from "vitest";

import client from "./client.js";
import { productImageSource } from "./productImages.js";

const original = client.defaults.baseURL;
afterEach(() => {
  client.defaults.baseURL = original;
});

it("resolves uploaded images for a same-origin API proxy and a separate backend origin", () => {
  client.defaults.baseURL = "/api";
  expect(productImageSource("/media/product-images/1/demo.webp")).toBe(
    `${window.location.origin}/media/product-images/1/demo.webp`,
  );
  client.defaults.baseURL = "http://localhost:18000";
  expect(productImageSource("/media/product-images/1/demo.webp")).toBe(
    "http://localhost:18000/media/product-images/1/demo.webp",
  );
  expect(productImageSource("https://example.com/demo.webp")).toBe("https://example.com/demo.webp");
  expect(productImageSource(null)).toBeNull();
});
