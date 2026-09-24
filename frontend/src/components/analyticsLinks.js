// Databricks AI/BI Dashboard and Genie are built in Planning E5–E6; the URLs are
// deployment configuration, so an unset value means the tool is not available yet.
export function analyticsLinks() {
  return [
    {
      key: "dashboard",
      label: "Databricks Dashboard",
      url: import.meta.env.VITE_DATABRICKS_DASHBOARD_URL?.trim() || null,
    },
    {
      key: "genie",
      label: "Genie",
      url: import.meta.env.VITE_DATABRICKS_GENIE_URL?.trim() || null,
    },
  ];
}
