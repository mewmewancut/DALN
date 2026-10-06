import DateRangeFields from "../DateRangeFields.jsx";
import { lastDays } from "../dateRange.js";

export default function DashboardToolbar({ range, onChange, loading, onRefresh }) {
  return (
    <div className="dashboard-toolbar">
      <div className="dashboard-presets" aria-label="Khoảng thời gian nhanh">
        {[7, 30, 90].map((days) => (
          <button key={days} type="button" onClick={() => onChange(lastDays(days))}>
            {days} ngày
          </button>
        ))}
      </div>
      <DateRangeFields range={range} onChange={onChange} />
      <button type="button" disabled={loading} onClick={onRefresh}>
        Làm mới số liệu
      </button>
    </div>
  );
}
