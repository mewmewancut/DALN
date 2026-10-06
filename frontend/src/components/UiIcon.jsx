const paths = {
  chat: "M3 4h18v13H8l-5 4V4Zm4 5h10M7 13h6",
  bag: "M6 7h12l1 13H5L6 7Zm3 0V5a3 3 0 0 1 6 0v2",
  heart:
    "M20.8 4.6a5.4 5.4 0 0 0-7.6 0L12 5.8l-1.2-1.2a5.4 5.4 0 0 0-7.6 7.6L12 21l8.8-8.8a5.4 5.4 0 0 0 0-7.6Z",
  user: "M20 21v-2a7 7 0 0 0-14 0v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
  grid: "M3 3h7v7H3V3Zm11 0h7v7h-7V3ZM3 14h7v7H3v-7Zm11 0h7v7h-7v-7Z",
  orders: "M6 3h12v18l-3-2-3 2-3-2-3 2V3Zm3 5h6M9 12h6",
  settings: "M4 7h16M4 17h16M8 4v6M16 14v6",
  box: "m12 3 9 5v8l-9 5-9-5V8l9-5Zm0 9v9M3 8l9 4 9-4M7.5 5.5l9 5",
  alert: "m12 3 10 18H2L12 3Zm0 6v5M12 17v1",
  truck:
    "M3 6h11v12H3V6Zm11 5h4l3 4v3h-7M7 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm11 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
  store: "M4 10v11h16V10M2 10l3-7h14l3 7M2 10h20M9 21v-7h6v7",
  shirt: "m8 3-6 4 3 5 3-2v11h8V10l3 2 3-5-6-4a4 4 0 0 1-8 0Z",
};

export default function UiIcon({ name }) {
  return (
    <svg
      className="ui-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={paths[name] ?? paths.grid} />
    </svg>
  );
}
