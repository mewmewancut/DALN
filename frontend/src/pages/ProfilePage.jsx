import { useCallback, useEffect, useState } from "react";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import { useAuth } from "../auth/AuthContext.jsx";
import AddressBook from "../components/AddressBook.jsx";
import SiteLayout from "../components/SiteLayout.jsx";

export default function ProfilePage() {
  const { session } = useAuth();
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState({ full_name: "", phone: "", avatar_url: "" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [avatarFailed, setAvatarFailed] = useState(false);
  const showError = useCallback((message) => setError(message), []);
  const showNotice = useCallback((message) => setNotice(message), []);

  useEffect(() => {
    let active = true;
    client
      .get("/users/me/profile")
      .then((response) => {
        if (!active) return;
        setProfile(response.data);
        setForm({
          full_name: response.data.full_name,
          phone: response.data.phone ?? "",
          avatar_url: response.data.avatar_url ?? "",
        });
      })
      .catch((requestError) => active && setError(errorMessage(requestError)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    setAvatarFailed(false);
  }, [form.avatar_url]);

  async function saveProfile(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const response = await client.patch("/users/me/profile", {
        full_name: form.full_name,
        phone: form.phone || null,
        avatar_url: form.avatar_url || null,
      });
      setProfile(response.data);
      setNotice("Đã cập nhật hồ sơ");
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  }

  if (loading) {
    return (
      <SiteLayout>
        <p role="status">Đang tải hồ sơ...</p>
      </SiteLayout>
    );
  }

  return (
    <SiteLayout wide>
      <p className="eyebrow">Tài khoản của tôi</p>
      <h1>Hồ sơ cá nhân</h1>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="form-success" role="status">
          {notice}
        </p>
      )}
      {profile && (
        <div className="profile-grid">
          <div className="avatar-preview">
            {form.avatar_url && !avatarFailed ? (
              <img src={form.avatar_url} alt="Ảnh đại diện" onError={() => setAvatarFailed(true)} />
            ) : (
              <span aria-label="Ảnh đại diện mặc định">
                {profile.full_name.charAt(0).toUpperCase()}
              </span>
            )}
          </div>
          <form className="form-stack" onSubmit={saveProfile}>
            <label>
              Email
              <input value={profile.email} disabled />
            </label>
            <label>
              Vai trò
              <input value={profile.role} disabled />
            </label>
            <label>
              Họ và tên
              <input
                required
                maxLength="255"
                value={form.full_name}
                onChange={(event) =>
                  setForm((current) => ({ ...current, full_name: event.target.value }))
                }
              />
            </label>
            <label>
              Số điện thoại
              <input
                type="tel"
                maxLength="20"
                value={form.phone}
                onChange={(event) =>
                  setForm((current) => ({ ...current, phone: event.target.value }))
                }
              />
            </label>
            <label>
              URL ảnh đại diện
              <input
                type="url"
                value={form.avatar_url}
                onChange={(event) =>
                  setForm((current) => ({ ...current, avatar_url: event.target.value }))
                }
              />
            </label>
            <button type="submit">Lưu hồ sơ</button>
          </form>
        </div>
      )}
      {session.role === "BUYER" && <AddressBook onError={showError} onNotice={showNotice} />}
    </SiteLayout>
  );
}
