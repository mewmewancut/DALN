export default function DateRangeFields({ range, onChange, required = true }) {
  return (
    <>
      <label>
        Từ ngày
        <input
          type="date"
          value={range.from}
          onChange={(event) => onChange({ ...range, from: event.target.value })}
          required={required}
        />
      </label>
      <label>
        Đến ngày
        <input
          type="date"
          value={range.to}
          onChange={(event) => onChange({ ...range, to: event.target.value })}
          required={required}
        />
      </label>
    </>
  );
}
