export default function DashboardPanel({ title, description, action, children, className = "" }) {
  return (
    <section className={`dashboard-panel ${className}`}>
      <div className="dashboard-panel-heading">
        <h2>{title}</h2>
        {action}
      </div>
      <p className="dashboard-description">{description}</p>
      {children}
    </section>
  );
}
