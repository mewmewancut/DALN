export default function BarList({ rows, emptyMessage }) {
  const max = Math.max(0, ...rows.map((row) => row.value));
  if (!max) return <p className="dashboard-empty">{emptyMessage}</p>;
  return (
    <ol className="dashboard-bars">
      {rows.map((row) => (
        <li key={row.key} data-tone={row.tone}>
          <div>
            <span>{row.label}</span>
            <strong>{row.formatted ?? row.value.toLocaleString("vi-VN")}</strong>
          </div>
          <div className="bar-track" aria-hidden="true">
            <div style={{ width: `${(100 * row.value) / max}%` }} />
          </div>
          {row.detail && <small>{row.detail}</small>}
        </li>
      ))}
    </ol>
  );
}
