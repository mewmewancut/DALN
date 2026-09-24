import { useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";

const EMPTY_VARIANT = { size: "", color: "", price: "", initial_quantity: "0" };

export default function VariantManager({ product }) {
  const [variants, setVariants] = useState(product.variants);
  const [prices, setPrices] = useState(() =>
    Object.fromEntries(product.variants.map((variant) => [variant.id, String(variant.price)])),
  );
  const [draft, setDraft] = useState(EMPTY_VARIANT);
  const [pending, setPending] = useState(null);
  const [error, setError] = useState("");

  function replaceVariant(updated) {
    setVariants((current) =>
      current.map((variant) => (variant.id === updated.id ? updated : variant)),
    );
    setPrices((current) => ({ ...current, [updated.id]: String(updated.price) }));
  }

  async function updateVariant(variant, body) {
    setPending(variant.id);
    setError("");
    try {
      const response = await client.put(`/variants/${variant.id}`, body);
      replaceVariant(response.data);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setPending(null);
    }
  }

  async function addVariant(event) {
    event.preventDefault();
    setPending("new");
    setError("");
    try {
      const response = await client.post(`/products/${product.id}/variants`, {
        size: draft.size.trim(),
        color: draft.color.trim(),
        price: Number(draft.price),
        initial_quantity: Number(draft.initial_quantity),
      });
      setVariants((current) => [...current, response.data]);
      setPrices((current) => ({ ...current, [response.data.id]: String(response.data.price) }));
      setDraft(EMPTY_VARIANT);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setPending(null);
    }
  }

  return (
    <section className="variant-editor">
      <h3>Biến thể</h3>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Size</th>
              <th>Màu</th>
              <th>SKU</th>
              <th>Giá (₫)</th>
              <th>Tồn kho</th>
              <th>Trạng thái</th>
              <th>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {variants.map((variant) => {
              const price = prices[variant.id];
              const invalidPrice = price === "" || !(Number(price) >= 0);
              return (
                <tr key={variant.id}>
                  <td>{variant.size}</td>
                  <td>{variant.color}</td>
                  <td>{variant.sku}</td>
                  <td>
                    <input
                      aria-label={`Giá ${variant.color} ${variant.size}`}
                      type="number"
                      min="0"
                      value={price}
                      onChange={(event) =>
                        setPrices((current) => ({ ...current, [variant.id]: event.target.value }))
                      }
                    />
                  </td>
                  <td>{variant.quantity}</td>
                  <td>{variant.is_active ? "Đang bán" : "Đã ẩn"}</td>
                  <td className="table-actions">
                    <button
                      type="button"
                      disabled={
                        pending === variant.id || invalidPrice || Number(price) === variant.price
                      }
                      onClick={() => updateVariant(variant, { price: Number(price) })}
                    >
                      Lưu giá
                    </button>
                    <button
                      type="button"
                      disabled={pending === variant.id}
                      onClick={() => updateVariant(variant, { is_active: !variant.is_active })}
                    >
                      {variant.is_active ? "Ẩn" : "Hiện"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted">Tồn kho chỉ thay đổi qua đơn hàng hoặc phiếu nhập hàng.</p>
      <form className="variant-row" onSubmit={addVariant} aria-label="Thêm biến thể mới">
        <label>
          Size mới
          <input
            value={draft.size}
            onChange={(event) => setDraft({ ...draft, size: event.target.value })}
            required
          />
        </label>
        <label>
          Màu mới
          <input
            value={draft.color}
            onChange={(event) => setDraft({ ...draft, color: event.target.value })}
            required
          />
        </label>
        <label>
          Giá mới (₫)
          <input
            type="number"
            min="0"
            value={draft.price}
            onChange={(event) => setDraft({ ...draft, price: event.target.value })}
            required
          />
        </label>
        <label>
          Tồn kho ban đầu
          <input
            type="number"
            min="0"
            value={draft.initial_quantity}
            onChange={(event) => setDraft({ ...draft, initial_quantity: event.target.value })}
            required
          />
        </label>
        <button type="submit" disabled={pending === "new"}>
          Thêm biến thể
        </button>
      </form>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
