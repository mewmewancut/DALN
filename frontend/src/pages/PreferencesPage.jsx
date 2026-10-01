import { useEffect, useState } from "react";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import SiteLayout from "../components/SiteLayout.jsx";

const EMPTY_FORM = {
  category_ids: [],
  colors: [],
  min_price: "",
  max_price: "",
};

export default function PreferencesPage() {
  const [options, setOptions] = useState({ categories: [], colors: [] });
  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([client.get("/users/me/preferences/options"), client.get("/users/me/preferences")])
      .then(([optionsResponse, preferenceResponse]) => {
        if (!active) return;
        setOptions(optionsResponse.data);
        setForm({
          category_ids: preferenceResponse.data.category_ids,
          colors: preferenceResponse.data.colors,
          min_price: preferenceResponse.data.min_price ?? "",
          max_price: preferenceResponse.data.max_price ?? "",
        });
      })
      .catch((requestError) => {
        if (active) setLoadError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function toggleList(field, value) {
    setForm((current) => ({
      ...current,
      [field]: current[field].includes(value)
        ? current[field].filter((item) => item !== value)
        : [...current[field], value],
    }));
  }

  async function save(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (
      form.min_price !== "" &&
      form.max_price !== "" &&
      Number(form.min_price) > Number(form.max_price)
    ) {
      setError("Giá tối thiểu không được lớn hơn giá tối đa");
      return;
    }

    setSaving(true);
    try {
      const response = await client.put("/users/me/preferences", {
        category_ids: form.category_ids,
        colors: form.colors,
        min_price: form.min_price === "" ? null : Number(form.min_price),
        max_price: form.max_price === "" ? null : Number(form.max_price),
      });
      setForm({
        category_ids: response.data.category_ids,
        colors: response.data.colors,
        min_price: response.data.min_price ?? "",
        max_price: response.data.max_price ?? "",
      });
      setNotice("Đã lưu sở thích mua sắm");
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSaving(false);
    }
  }

  return (
    <SiteLayout wide>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Cá nhân hóa</p>
          <h1>Sở thích mua sắm</h1>
          <p className="muted">
            Chọn những gì bạn thường quan tâm. Thông tin này sẽ được dùng cho phần gợi ý sản phẩm
            sau này.
          </p>
        </div>
      </header>
      {loading && <p role="status">Đang tải sở thích...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {loadError && (
        <p className="form-error" role="alert">
          {loadError}
        </p>
      )}
      {notice && (
        <p className="form-success" role="status">
          {notice}
        </p>
      )}
      {!loading && !loadError && (
        <form className="preference-form" onSubmit={save}>
          <fieldset>
            <legend>Danh mục yêu thích</legend>
            <p className="muted">Bạn có thể chọn nhiều danh mục.</p>
            <div className="preference-options">
              {options.categories.map((category) => (
                <label key={category.id}>
                  <input
                    type="checkbox"
                    checked={form.category_ids.includes(category.id)}
                    onChange={() => toggleList("category_ids", category.id)}
                  />
                  <span>{category.name}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend>Màu sắc thường chọn</legend>
            {options.colors.length === 0 ? (
              <p className="muted">Catalog chưa có màu sắc để lựa chọn.</p>
            ) : (
              <div className="preference-options">
                {options.colors.map((color) => (
                  <label key={color}>
                    <input
                      type="checkbox"
                      checked={form.colors.includes(color)}
                      onChange={() => toggleList("colors", color)}
                    />
                    <span>{color}</span>
                  </label>
                ))}
              </div>
            )}
          </fieldset>

          <fieldset>
            <legend>Khoảng giá mong muốn</legend>
            <div className="preference-price-fields">
              <label>
                Giá tối thiểu (₫)
                <input
                  type="number"
                  min="0"
                  max="999999999999"
                  value={form.min_price}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, min_price: event.target.value }))
                  }
                />
              </label>
              <label>
                Giá tối đa (₫)
                <input
                  type="number"
                  min="0"
                  max="999999999999"
                  value={form.max_price}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, max_price: event.target.value }))
                  }
                />
              </label>
            </div>
          </fieldset>

          <button type="submit" className="primary-button" disabled={saving}>
            {saving ? "Đang lưu..." : "Lưu sở thích"}
          </button>
        </form>
      )}
    </SiteLayout>
  );
}
