import { useCallback, useEffect, useState } from "react";
import client from "../api/client.js";
import { cartErrorMessage as errorMessage } from "./errorMessage.js";
import { finishGuestMerge, markGuestMerge, readGuestCart, saveGuestItems } from "./guestCart.js";

const EMPTY = { items: [], total_amount: 0, shop_id: null, shop_name: null };

export default function useCart(session) {
  const [cart, setCart] = useState(EMPTY);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [mergeError, setMergeError] = useState("");
  const [reload, setReload] = useState(0);
  const [guestRevision, setGuestRevision] = useState(0);
  const buyer = session?.role === "BUYER";

  useEffect(() => {
    const changed = () => setGuestRevision((value) => value + 1);
    const storageChanged = (event) => {
      if (event.key === "fashion_guest_cart" || event.key === null) changed();
    };
    window.addEventListener("storage", storageChanged);
    return () => {
      window.removeEventListener("storage", storageChanged);
    };
  }, []);

  const previewRevision = buyer ? 0 : guestRevision;
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setLoadError("");
    setMergeError("");
    setCart(EMPTY);
    async function load() {
      const guest = readGuestCart();
      try {
        let next;
        if (buyer) {
          next = (await client.get("/cart", { signal: controller.signal })).data;
          if (controller.signal.aborted) return;
          if (guest.items.length) {
            try {
              markGuestMerge(guest);
              next = (
                await client.post(
                  "/cart/merge",
                  { merge_id: guest.merge_id, items: guest.items },
                  { signal: controller.signal },
                )
              ).data;
              if (controller.signal.aborted) return;
              if (!finishGuestMerge(guest)) {
                setMergeError(
                  "Giỏ tạm vừa thay đổi ở trang khác. Kiểm tra lại trước khi chuyển giỏ.",
                );
              }
            } catch (failure) {
              if (controller.signal.aborted) return;
              if ([404, 409, 422].includes(failure.response?.status)) markGuestMerge(guest, false);
              setMergeError(errorMessage(failure));
            }
          }
        } else {
          next = guest.items.length
            ? (
                await client.post(
                  "/cart/preview",
                  { items: guest.items },
                  { signal: controller.signal },
                )
              ).data
            : EMPTY;
        }
        if (!controller.signal.aborted) setCart(next);
      } catch (failure) {
        if (!controller.signal.aborted) setLoadError(errorMessage(failure));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [buyer, session?.token, reload, previewRevision]);

  const refresh = useCallback(() => setReload((value) => value + 1), []);
  async function saveAndPreview(items) {
    saveGuestItems(items);
    try {
      return (await client.post("/cart/preview", { items: readGuestCart().items })).data;
    } catch (failure) {
      refresh();
      throw failure;
    }
  }
  async function updateItem(item, quantity) {
    if (buyer) return (await client.put(`/cart/items/${item.id}`, { quantity })).data;
    return saveAndPreview(
      readGuestCart().items.map((entry) =>
        entry.variant_id === item.variant_id ? { ...entry, quantity } : entry,
      ),
    );
  }
  async function removeItem(item) {
    if (buyer) return (await client.delete(`/cart/items/${item.id}`)).data;
    return saveAndPreview(
      readGuestCart().items.filter((entry) => entry.variant_id !== item.variant_id),
    );
  }
  return { cart, setCart, loading, loadError, mergeError, refresh, updateItem, removeItem };
}
