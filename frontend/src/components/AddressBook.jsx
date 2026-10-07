import { useEffect, useState } from "react";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import SearchableSelect from "./SearchableSelect.jsx";

const emptyAddress = {
  label: "Nhà riêng",
  receiver_name: "",
  receiver_phone: "",
  province_code: "",
  commune_code: "",
  address_detail: "",
  is_default: false,
};

export default function AddressBook({ onError, onNotice }) {
  const [addresses, setAddresses] = useState([]);
  const [provinces, setProvinces] = useState([]);
  const [communes, setCommunes] = useState([]);
  const [form, setForm] = useState(emptyAddress);
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([client.get("/users/me/addresses"), client.get("/locations/provinces")])
      .then(([addressResponse, provinceResponse]) => {
        if (!active) return;
        setAddresses(addressResponse.data);
        setProvinces(provinceResponse.data);
      })
      .catch((requestError) => active && onError(errorMessage(requestError)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [onError]);

  async function loadCommunes(provinceCode) {
    if (!provinceCode) {
      setCommunes([]);
      return;
    }
    const response = await client.get("/locations/communes", {
      params: { province_code: provinceCode },
    });
    setCommunes(response.data);
  }

  function changeField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  function resetForm() {
    setForm(emptyAddress);
    setEditingId(null);
    setCommunes([]);
  }

  async function save(event) {
    event.preventDefault();
    onError("");
    onNotice("");
    try {
      const path = editingId ? `/users/me/addresses/${editingId}` : "/users/me/addresses";
      const method = editingId ? "patch" : "post";
      const payload = editingId
        ? Object.fromEntries(Object.entries(form).filter(([field]) => field !== "is_default"))
        : form;
      const response = await client[method](path, payload);
      setAddresses((current) => {
        let next = editingId
          ? current.map((item) => (item.id === editingId ? response.data : item))
          : [...current, response.data];
        if (response.data.is_default) {
          next = next.map((item) => ({
            ...item,
            is_default: item.id === response.data.id,
          }));
        }
        return [...next].sort((a, b) => Number(b.is_default) - Number(a.is_default));
      });
      onNotice(editingId ? "Đã cập nhật địa chỉ" : "Đã thêm địa chỉ");
      resetForm();
    } catch (requestError) {
      onError(errorMessage(requestError));
    }
  }

  async function edit(address) {
    setEditingId(address.id);
    setForm({
      label: address.label,
      receiver_name: address.receiver_name,
      receiver_phone: address.receiver_phone,
      province_code: address.province_code,
      commune_code: address.commune_code,
      address_detail: address.address_detail,
      is_default: address.is_default,
    });
    try {
      await loadCommunes(address.province_code);
    } catch (requestError) {
      onError(errorMessage(requestError));
    }
  }

  async function setDefault(addressId) {
    try {
      await client.put(`/users/me/addresses/${addressId}/default`);
      setAddresses((current) =>
        current
          .map((item) => ({ ...item, is_default: item.id === addressId }))
          .sort((a, b) => Number(b.is_default) - Number(a.is_default)),
      );
    } catch (requestError) {
      onError(errorMessage(requestError));
    }
  }

  async function remove(addressId) {
    try {
      await client.delete(`/users/me/addresses/${addressId}`);
      setAddresses((current) => {
        const remaining = current.filter((item) => item.id !== addressId);
        if (remaining.length && !remaining.some((item) => item.is_default)) {
          return remaining.map((item, index) => ({ ...item, is_default: index === 0 }));
        }
        return remaining;
      });
      if (editingId === addressId) resetForm();
    } catch (requestError) {
      onError(errorMessage(requestError));
    }
  }

  return (
    <section className="address-section">
      <div>
        <h2>Sổ địa chỉ</h2>
      </div>
      {loading ? (
        <p role="status">Đang tải sổ địa chỉ...</p>
      ) : (
        <div className="address-book">
          <div className="address-list">
            {addresses.length === 0 && <p className="empty-state">Bạn chưa lưu địa chỉ nào.</p>}
            {addresses.map((address) => (
              <article className="address-card" key={address.id}>
                <div className="address-heading">
                  <strong>{address.label}</strong>
                  {address.is_default && <span className="status-badge">Mặc định</span>}
                </div>
                <p>
                  {address.receiver_name} · {address.receiver_phone}
                </p>
                <p>
                  {address.address_detail}, {address.commune_name}, {address.province_name}
                </p>
                <div className="inline-actions">
                  <button type="button" className="secondary" onClick={() => edit(address)}>
                    Sửa
                  </button>
                  {!address.is_default && (
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => setDefault(address.id)}
                    >
                      Đặt mặc định
                    </button>
                  )}
                  <button type="button" className="danger" onClick={() => remove(address.id)}>
                    Xóa
                  </button>
                </div>
              </article>
            ))}
          </div>
          <form className="form-stack address-form" onSubmit={save}>
            <h3>{editingId ? "Sửa địa chỉ" : "Thêm địa chỉ"}</h3>
            <label>
              Nhãn địa chỉ
              <input
                name="label"
                required
                maxLength="50"
                value={form.label}
                onChange={changeField}
              />
            </label>
            <label>
              Người nhận
              <input
                name="receiver_name"
                required
                maxLength="255"
                value={form.receiver_name}
                onChange={changeField}
              />
            </label>
            <label>
              Số điện thoại nhận hàng
              <input
                name="receiver_phone"
                type="tel"
                required
                maxLength="20"
                value={form.receiver_phone}
                onChange={changeField}
              />
            </label>
            <SearchableSelect
              label="Tỉnh/Thành phố"
              options={provinces}
              value={form.province_code}
              onChange={async (code) => {
                setForm((current) => ({ ...current, province_code: code, commune_code: "" }));
                try {
                  await loadCommunes(code);
                } catch (requestError) {
                  onError(errorMessage(requestError));
                }
              }}
            />
            <SearchableSelect
              label="Xã/Phường/Đặc khu"
              options={communes}
              value={form.commune_code}
              disabled={!form.province_code}
              onChange={(code) => setForm((current) => ({ ...current, commune_code: code }))}
            />
            <label>
              Địa chỉ cụ thể
              <textarea
                name="address_detail"
                required
                maxLength="500"
                value={form.address_detail}
                onChange={changeField}
                placeholder="Số nhà, đường, thôn/ấp/khu phố, tòa nhà..."
              />
            </label>
            {!editingId && (
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={form.is_default}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, is_default: event.target.checked }))
                  }
                />{" "}
                Đặt làm địa chỉ mặc định
              </label>
            )}
            <div className="inline-actions">
              <button type="submit">{editingId ? "Lưu địa chỉ" : "Thêm địa chỉ"}</button>
              {editingId && (
                <button type="button" className="secondary" onClick={resetForm}>
                  Hủy sửa
                </button>
              )}
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
