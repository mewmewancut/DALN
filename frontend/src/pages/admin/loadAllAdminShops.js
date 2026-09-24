const SHOP_PAGE_SIZE = 100;

export async function loadAllAdminShops(client) {
  const shops = [];
  let page = 1;

  while (true) {
    const response = await client.get("/admin/shops", {
      params: { page, page_size: SHOP_PAGE_SIZE },
    });
    const batch = response.data.items;
    shops.push(...batch);

    if (shops.length >= response.data.total || batch.length === 0) return shops;
    page += 1;
  }
}
