import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useAuth } from "../auth/AuthContext.jsx";
import { cartErrorMessage as errorMessage } from "../cart/errorMessage.js";
import { groupCart } from "../cart/groupCart.js";
import { readCheckoutSelection, readGuestCart, saveCheckoutSelection } from "../cart/guestCart.js";
import useCart from "../cart/useCart.js";
import { formatCurrency } from "../components/formatCurrency.js";
import SiteLayout from "../components/SiteLayout.jsx";
import CartShopGroup from "../components/cart/CartShopGroup.jsx";
import GuestCartRecovery from "../components/cart/GuestCartRecovery.jsx";

export default function CartPage() {
  const navigate = useNavigate();
  const { session } = useAuth();
  const { cart, setCart, loading, loadError, mergeError, refresh, updateItem, removeItem } =
    useCart(session);
  const [quantities, setQuantities] = useState({});
  const [selectedId, setSelectedId] = useState(() => readCheckoutSelection().shop_id);
  const [pendingItem, setPendingItem] = useState(null);
  const [actionError, setActionError] = useState("");
  const groups = groupCart(cart);
  const selected =
    groups.find((group) => group.shop_id === selectedId) ??
    (groups.length === 1 ? groups[0] : null);

  useEffect(() => {
    setQuantities((current) =>
      Object.fromEntries(
        cart.items.map((item) => [item.id, current[item.id] ?? String(item.quantity)]),
      ),
    );
  }, [cart]);

  useEffect(() => {
    if (loading || loadError || mergeError || !session || readGuestCart().items.length) return;
    const selection = readCheckoutSelection();
    if (selection.resume && cart.items.some((item) => item.shop_id === selection.shop_id)) {
      try {
        saveCheckoutSelection(selection.shop_id);
        navigate("/checkout", { state: { shopId: selection.shop_id }, replace: true });
      } catch (failure) {
        setActionError(errorMessage(failure));
      }
    }
  }, [cart, loading, loadError, mergeError, session, navigate]);

  async function update(item, quantity) {
    if (pendingItem !== null) return;
    setPendingItem(item.id);
    setActionError("");
    try {
      const next = await updateItem(item, quantity);
      setQuantities((current) => ({ ...current, [item.id]: String(quantity) }));
      setCart(next);
    } catch (failure) {
      setActionError(errorMessage(failure));
    } finally {
      setPendingItem(null);
    }
  }
  async function remove(item) {
    if (pendingItem !== null) return;
    setPendingItem(item.id);
    setActionError("");
    try {
      setCart(await removeItem(item));
    } catch (failure) {
      setActionError(errorMessage(failure));
    } finally {
      setPendingItem(null);
    }
  }
  function select(group) {
    try {
      saveCheckoutSelection(group.shop_id);
      setSelectedId(group.shop_id);
      setActionError("");
    } catch (failure) {
      setActionError(errorMessage(failure));
    }
  }
  function checkout() {
    if (!selected) return;
    try {
      saveCheckoutSelection(selected.shop_id, !session);
      navigate(session ? "/checkout" : "/login", {
        state: session ? { shopId: selected.shop_id } : { from: "/checkout" },
      });
    } catch (failure) {
      setActionError(errorMessage(failure));
    }
  }
  const hasDraft = selected?.items.some(
    (item) => Number(quantities[item.id] ?? item.quantity) !== item.quantity,
  );
  const invalid = selected?.items.some((item) => {
    const quantity = Number(quantities[item.id] ?? item.quantity);
    return (
      item.is_available === false ||
      !Number.isInteger(quantity) ||
      quantity < 1 ||
      quantity > item.stock_quantity
    );
  });

  return (
    <SiteLayout wide>
      <h1>Giỏ hàng</h1>
      <p className="muted">
        Mỗi lần thanh toán một shop. Hàng của shop khác vẫn được giữ trong giỏ.
      </p>
      {!session && <p>Giỏ tạm được lưu trên trình duyệt này. Bạn đăng nhập khi thanh toán.</p>}
      {loading && <p role="status">Đang tải giỏ hàng...</p>}
      {loadError && (
        <p className="form-error" role="alert">
          {loadError}
        </p>
      )}
      {actionError && (
        <p className="form-error" role="alert">
          {actionError}
        </p>
      )}
      {mergeError && (
        <p className="form-error" role="alert">
          {mergeError}
        </p>
      )}
      {!loading && !loadError && !mergeError && cart.items.length === 0 && (
        <div className="empty-state">
          <p>Giỏ hàng đang trống.</p>
          <Link to="/">Tiếp tục mua sắm</Link>
        </div>
      )}
      {!loading &&
        !loadError &&
        groups.map((group) => (
          <CartShopGroup
            key={group.shop_id ?? "unavailable"}
            group={group}
            quantities={quantities}
            busy={pendingItem !== null}
            selected={selected?.shop_id === group.shop_id}
            onSelect={() => select(group)}
            onQuantity={(id, value) => setQuantities((current) => ({ ...current, [id]: value }))}
            onUpdate={update}
            onRemove={remove}
          />
        ))}
      {!loading && !loadError && cart.items.length > 0 && (
        <div className="cart-summary">
          <strong>Tổng thanh toán: {formatCurrency(selected?.total_amount ?? 0)}</strong>
          {!selected && <p>Chọn một shop để thanh toán.</p>}
          {pendingItem !== null && <p role="status">Đang cập nhật giỏ hàng...</p>}
          {hasDraft && <p role="status">Cập nhật số lượng trước khi thanh toán.</p>}
          <button
            className="primary-button"
            type="button"
            disabled={
              !selected ||
              selected.shop_id == null ||
              pendingItem !== null ||
              hasDraft ||
              invalid ||
              !!mergeError
            }
            onClick={checkout}
          >
            Thanh toán
          </button>
        </div>
      )}
      {!loading && !loadError && mergeError && <GuestCartRecovery onRetry={refresh} />}
      {loadError && (
        <button type="button" onClick={refresh}>
          Tải lại giỏ hàng
        </button>
      )}
    </SiteLayout>
  );
}
