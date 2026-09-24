import { useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import VariantManager from "./VariantManager.jsx";

const EMPTY_VARIANT = { size: "", color: "", price: "", initial_quantity: "0" };

function infoFromProduct(product) {
  return {
    category_id: product ? String(product.category_id) : "",
    name: product?.name ?? "",
    description: product?.description ?? "",
    image_url: product?.image_url ?? "",
    base_price: product ? String(product.base_price) : "",
  };
}

function infoPayload(info) {
  return {
    category_id: Number(info.category_id),
    name: info.name.trim(),
    description: info.description.trim() || null,
    image_url: info.image_url.trim() || null,
    base_price: Number(info.base_price),
  };
}

export default function ProductFormDialog({ categories, product, onClose }) {
  const [info, setInfo] = useState(() => infoFromProduct(product));
  const [variants, setVariants] = useState([{ ...EMPTY_VARIANT }]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const isEdit = product != null;

  function updateInfo(field, value) {
    setInfo((current) => ({ ...current, [field]: value }));
    setSaved(false);
  }

  function updateVariant(index, field, value) {
    setVariants((current) =>
      current.map((variant, position) =>
        position === index ? { ...variant, [field]: value } : variant,
      ),
    );
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      if (isEdit) {
        await client.put(`/products/${product.id}`, infoPayload(info));
        setSaved(true);
      } else {
        await client.post("/products", {
          ...infoPayload(info),
          variants: variants.map((variant) => ({
            size: variant.size.trim(),
            color: variant.color.trim(),
            price: Number(variant.price),
            initial_quantity: Number(variant.initial_quantity),
          })),
        });
        onClose();
        return;
      }
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
    setSubmitting(false);
  }

  return (
    <div className="dialog-backdrop">
      <section
        className="dialog dialog-wide"
        role="dialog"
        aria-modal="true"
        aria-label={isEdit ? "Sửa sản phẩm" : "Thêm sản phẩm"}
      >
        <h2>{isEdit ? `Sửa ${product.name}` : "Thêm sản phẩm"}</h2>
        <form className="form-stack" onSubmit={handleSubmit}>
          <label>
            Danh mục
            <select
              value={info.category_id}
              onChange={(event) => updateInfo("category_id", event.target.value)}
              required
            >
              <option value="">Chọn danh mục</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Tên sản phẩm
            <input
              value={info.name}
              onChange={(event) => updateInfo("name", event.target.value)}
              required
            />
          </label>
          <label>
            Mô tả
            <textarea
              value={info.description}
              onChange={(event) => updateInfo("description", event.target.value)}
            />
          </label>
          <label>
            Link ảnh
            <input
              value={info.image_url}
              onChange={(event) => updateInfo("image_url", event.target.value)}
            />
          </label>
          <label>
            Giá cơ sở (₫)
            <input
              type="number"
              min="0"
              value={info.base_price}
              onChange={(event) => updateInfo("base_price", event.target.value)}
              required
            />
          </label>
          {!isEdit && (
            <fieldset className="variant-editor">
              <legend>Biến thể</legend>
              {variants.map((variant, index) => (
                <div className="variant-row" key={index}>
                  <label>
                    Size
                    <input
                      value={variant.size}
                      onChange={(event) => updateVariant(index, "size", event.target.value)}
                      required
                    />
                  </label>
                  <label>
                    Màu
                    <input
                      value={variant.color}
                      onChange={(event) => updateVariant(index, "color", event.target.value)}
                      required
                    />
                  </label>
                  <label>
                    Giá (₫)
                    <input
                      type="number"
                      min="0"
                      value={variant.price}
                      onChange={(event) => updateVariant(index, "price", event.target.value)}
                      required
                    />
                  </label>
                  <label>
                    Tồn kho ban đầu
                    <input
                      type="number"
                      min="0"
                      value={variant.initial_quantity}
                      onChange={(event) =>
                        updateVariant(index, "initial_quantity", event.target.value)
                      }
                      required
                    />
                  </label>
                  <button
                    type="button"
                    disabled={variants.length === 1}
                    onClick={() =>
                      setVariants((current) => current.filter((_, position) => position !== index))
                    }
                  >
                    Bỏ dòng
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => setVariants((current) => [...current, { ...EMPTY_VARIANT }])}
              >
                Thêm biến thể
              </button>
            </fieldset>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {saved && <p role="status">Đã lưu thông tin sản phẩm.</p>}
          <div className="dialog-actions">
            <button type="button" onClick={onClose}>
              Đóng
            </button>
            <button type="submit" disabled={submitting}>
              {isEdit ? "Lưu thông tin" : "Tạo sản phẩm"}
            </button>
          </div>
        </form>
        {isEdit && <VariantManager product={product} />}
      </section>
    </div>
  );
}
