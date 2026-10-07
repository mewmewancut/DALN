import client from "./client.js";

export function productImageSource(src) {
  if (!src?.startsWith("/media/product-images/")) return src;
  return new URL(src, client.defaults.baseURL).href;
}

export async function uploadProductImage(file) {
  const body = new FormData();
  body.append("file", file);
  const response = await client.post("/shop/product-images", body);
  return response.data.image_url;
}
