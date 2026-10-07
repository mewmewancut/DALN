export function groupCart(cart) {
  const groups = new Map();
  for (const item of cart?.items ?? []) {
    const shopId = item.shop_id ?? cart.shop_id;
    if (!groups.has(shopId))
      groups.set(shopId, {
        shop_id: shopId,
        shop_name: item.shop_name ?? cart.shop_name ?? "Shop không còn khả dụng",
        items: [],
        total_amount: 0,
      });
    const group = groups.get(shopId);
    group.items.push(item);
    group.total_amount += item.quantity * item.unit_price;
  }
  return [...groups.values()];
}
