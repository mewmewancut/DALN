export default function Pagination({ page, total, pageSize, loading, onChange }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="pagination">
      <button type="button" disabled={loading || page <= 1} onClick={() => onChange(page - 1)}>
        Trang trước
      </button>
      <span>
        Trang {page}/{totalPages}
      </span>
      <button
        type="button"
        disabled={loading || page >= totalPages}
        onClick={() => onChange(page + 1)}
      >
        Trang sau
      </button>
    </div>
  );
}
