import client from "./client.js";

export function productImageSource(src) {
  if (!src?.startsWith("/media/product-images/")) return src;
  const apiBase = new URL(client.defaults.baseURL, window.location.origin);
  return new URL(src, apiBase).href;
}

export async function uploadProductImage(file) {
  const body = new FormData();
  body.append("file", file);
  const response = await client.post("/shop/product-images", body);
  return response.data.image_url;
}
