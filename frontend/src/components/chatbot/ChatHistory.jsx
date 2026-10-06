import { useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";

export default function ChatHistory({ history, selected, busy, onSelect, onDeleted }) {
  const [editing, setEditing] = useState(null);
  const [title, setTitle] = useState("");
  const [deleting, setDeleting] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  async function rename(event) {
    event.preventDefault();
    if (!title.trim() || saving) return;
    setSaving(true);
    try {
      await client.patch(`/analytics/chat/conversations/${editing}`, { title: title.trim() });
      setEditing(null);
      setError("");
      await history.refresh();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setSaving(false);
    }
  }
  async function remove() {
    setSaving(true);
    try {
      await client.delete(`/analytics/chat/conversations/${deleting}`);
      onDeleted(deleting);
      setDeleting(null);
      setError("");
      await history.refresh();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setSaving(false);
    }
  }
  return (
    <aside className="genie-history" aria-label="Lịch sử trò chuyện">
      <h2>Lịch sử trò chuyện</h2>
      {(error || history.error) && <p role="alert">{error || history.error}</p>}
      {history.error && (
        <button onClick={() => history.refresh()} disabled={history.loading}>
          Tải lại lịch sử
        </button>
      )}
      {history.loading && <p role="status">Đang tải lịch sử…</p>}
      {!history.loading && !history.error && !history.items.length && (
        <p>Chưa có cuộc trò chuyện nào.</p>
      )}
      <ul>
        {history.items.map((item) => (
          <li key={item.id}>
            <button
              className="genie-history-title"
              aria-pressed={selected === item.id}
              disabled={busy || saving}
              onClick={() => onSelect(item.id)}
            >
              {item.title}
            </button>
            <div className="genie-history-actions">
              <button
                aria-label={`Đổi tên ${item.title}`}
                disabled={busy || saving}
                onClick={() => {
                  setEditing(item.id);
                  setTitle(item.title);
                  setDeleting(null);
                  setError("");
                }}
              >
                Đổi tên
              </button>
              <button
                aria-label={`Xóa ${item.title}`}
                disabled={busy || saving}
                onClick={() => {
                  setDeleting(item.id);
                  setEditing(null);
                  setError("");
                }}
              >
                Xóa
              </button>
            </div>
          </li>
        ))}
      </ul>
      {history.hasMore && (
        <button disabled={history.loading} onClick={() => history.refresh(true)}>
          Xem lịch sử cũ hơn
        </button>
      )}
      {editing && (
        <form onSubmit={rename}>
          <label>
            Tên cuộc trò chuyện
            <input
              value={title}
              maxLength={120}
              disabled={saving}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <button disabled={saving || !title.trim()}>Lưu tên</button>
          <button type="button" disabled={saving} onClick={() => setEditing(null)}>
            Hủy đổi tên
          </button>
        </form>
      )}
      {deleting && (
        <div role="group" aria-label="Xác nhận xóa cuộc trò chuyện">
          <p>Xóa lịch sử cuộc trò chuyện này?</p>
          <button disabled={saving} onClick={remove}>
            Xác nhận xóa
          </button>
          <button disabled={saving} onClick={() => setDeleting(null)}>
            Giữ lại
          </button>
        </div>
      )}
    </aside>
  );
}
