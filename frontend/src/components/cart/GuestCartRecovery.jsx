import { useEffect, useState } from "react";
import client from "../../api/client.js";
import { cartErrorMessage as errorMessage } from "../../cart/errorMessage.js";
import { groupCart } from "../../cart/groupCart.js";
import { readGuestCart, saveGuestItems } from "../../cart/guestCart.js";
import CartShopGroup from "./CartShopGroup.jsx";

export default function GuestCartRecovery({ onRetry }) {
  const [cart, setCart] = useState(null);
  const [error, setError] = useState("");
  const [quantities, setQuantities] = useState({});
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const guest = readGuestCart();
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setCart(null);
    setQuantities({});
    client
      .post("/cart/preview", { items: readGuestCart().items }, { signal: controller.signal })
      .then(({ data }) => {
        if (controller.signal.aborted) return;
        setCart(data);
        setQuantities(
          Object.fromEntries(data.items.map((item) => [item.id, String(item.quantity)])),
        );
        setError("");
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(errorMessage(failure));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision]);

  function change(item, quantity) {
    try {
      saveGuestItems(
        readGuestCart().items.map((entry) =>
          entry.variant_id === item.variant_id ? { ...entry, quantity } : entry,
        ),
      );
      setRevision((value) => value + 1);
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }
  function remove(item) {
    try {
      saveGuestItems(readGuestCart().items.filter((entry) => entry.variant_id !== item.variant_id));
      setRevision((value) => value + 1);
    } catch (failure) {
      setError(errorMessage(failure));
    }
  }
  const hasDraft = cart?.items.some(
    (item) => Number(quantities[item.id] ?? item.quantity) !== item.quantity,
  );
  return (
    <section className="guest-cart-recovery" aria-label="Giỏ tạm chưa chuyển">
      <h2>Giỏ tạm chưa chuyển</h2>
      <p>
        {guest.pending
          ? "Chưa xác nhận được kết quả chuyển giỏ. Hãy thử đồng bộ lại trước khi sửa giỏ tạm."
          : "Giỏ tạm vẫn được giữ. Chỉnh số lượng hoặc xóa hàng không còn bán, rồi chuyển lại vào giỏ tài khoản."}
      </p>
      {loading && <p role="status">Đang tải giỏ tạm...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!loading &&
        !error &&
        groupCart(cart).map((group) => (
          <CartShopGroup
            key={group.shop_id ?? "unavailable"}
            group={group}
            quantities={quantities}
            busy={guest.pending}
            onQuantity={(id, value) => setQuantities((current) => ({ ...current, [id]: value }))}
            onUpdate={change}
            onRemove={remove}
          />
        ))}
      <button type="button" onClick={onRetry} disabled={loading || hasDraft}>
        Thử chuyển giỏ tạm
      </button>
    </section>
  );
}
