const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  return (
    <main className="shell">
      <section className="card">
        <p className="eyebrow">Fashion E-Commerce Platform</p>
        <h1>Nền móng dự án đã sẵn sàng</h1>
        <p>
          React/Vite đang hoạt động. FastAPI được cấu hình tại{" "}
          <a href={`${API_URL}/docs`}>{API_URL}/docs</a>.
        </p>
      </section>
    </main>
  );
}
