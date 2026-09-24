import { useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import { variantLabel } from "./purchaseOrderPresentation.js";

const EMPTY_LINE = { variant_id: "", quantity: "1", unit_cost: "" };

export default function PurchaseOrderForm({ suppliers, variants, onCreated }) {
  const [supplierId, setSupplierId] = useState("");
  const [note, setNote] = useState("");
  const [lines, setLines] = useState([{ ...EMPTY_LINE }]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const activeSuppliers = suppliers.filter((supplier) => supplier.is_active);
  const chosenVariants = lines.map((line) => line.variant_id).filter(Boolean);
  const hasDuplicate = new Set(chosenVariants).size !== chosenVariants.length;

  function updateLine(index, field, value) {
    setLines((current) =>
      current.map((line, position) => (position === index ? { ...line, [field]: value } : line)),
    );
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (hasDuplicate) return;
    setSubmitting(true);
    setError("");
    try {
      await client.post("/shop/purchase-orders", {
        supplier_id: Number(supplierId),
        note: note.trim() || null,
        items: lines.map((line) => ({
          variant_id: Number(line.variant_id),
          quantity: Number(line.quantity),
          unit_cost: Number(line.unit_cost),
        })),
      });
      setSupplierId("");
      setNote("");
      setLines([{ ...EMPTY_LINE }]);
      onCreated();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="form-stack order-box" onSubmit={handleSubmit} aria-label="Tạo phiếu nhập">
      <h2>Tạo phiếu nhập</h2>
      <label>
        Nhà cung cấp
        <select value={supplierId} onChange={(event) => setSupplierId(event.target.value)} required>
          <option value="">Chọn nhà cung cấp</option>
          {activeSuppliers.map((supplier) => (
            <option key={supplier.id} value={supplier.id}>
              {supplier.name}
            </option>
          ))}
        </select>
      </label>
      {activeSuppliers.length === 0 && (
        <p className="muted">Chưa có nhà cung cấp đang hợp tác. Hãy thêm nhà cung cấp trước.</p>
      )}
      {lines.map((line, index) => (
        <div className="variant-row" key={index}>
          <label>
            Biến thể
            <select
              value={line.variant_id}
              onChange={(event) => updateLine(index, "variant_id", event.target.value)}
              required
            >
              <option value="">Chọn biến thể</option>
              {variants.map((variant) => (
                <option key={variant.variant_id} value={variant.variant_id}>
                  {variantLabel(variant)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Số lượng
            <input
              type="number"
              min="1"
              value={line.quantity}
              onChange={(event) => updateLine(index, "quantity", event.target.value)}
              required
            />
          </label>
          <label>
            Giá nhập (₫)
            <input
              type="number"
              min="0"
              value={line.unit_cost}
              onChange={(event) => updateLine(index, "unit_cost", event.target.value)}
              required
            />
          </label>
          <button
            type="button"
            disabled={lines.length === 1}
            onClick={() =>
              setLines((current) => current.filter((_, position) => position !== index))
            }
          >
            Bỏ dòng
          </button>
        </div>
      ))}
      <button type="button" onClick={() => setLines((current) => [...current, { ...EMPTY_LINE }])}>
        Thêm dòng
      </button>
      <label>
        Ghi chú
        <textarea value={note} onChange={(event) => setNote(event.target.value)} />
      </label>
      {hasDuplicate && (
        <p className="form-error">Mỗi biến thể chỉ được xuất hiện một lần trong phiếu nhập.</p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={submitting || hasDuplicate}>
        Tạo phiếu nháp
      </button>
    </form>
  );
}
