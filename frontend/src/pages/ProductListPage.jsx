import { useEffect, useState } from "react";
import { Link } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import SiteLayout from "../components/SiteLayout.jsx";
import { formatCurrency } from "../components/formatCurrency.js";

const PAGE_SIZE = 20;

export default function ProductListPage() {
  const [filters, setFilters] = useState({
    keyword: "",
    category_id: "",
    min_price: "",
    max_price: "",
    sort: "newest",
    page: 1,
  });
  const [categories, setCategories] = useState([]);
  const [categoryError, setCategoryError] = useState("");
  const [result, setResult] = useState({ items: [], total: 0, page: 1, page_size: PAGE_SIZE });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    client
      .get("/categories")
      .then((response) => {
        if (active) setCategories(response.data);
      })
      .catch((requestError) => {
        if (active) setCategoryError(errorMessage(requestError));
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    const params = { sort: filters.sort, page: filters.page, page_size: PAGE_SIZE };
    for (const key of ["keyword", "category_id", "min_price", "max_price"]) {
      if (filters[key] !== "") params[key] = filters[key];
    }
    client
      .get("/products", { params })
      .then((response) => {
        if (active) setResult(response.data);
      })
      .catch((requestError) => {
        if (active) setError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [filters]);

  function changeFilter(key, value) {
    setFilters((previous) => ({ ...previous, [key]: value, page: 1 }));
  }

  const totalPages = Math.max(1, Math.ceil(result.total / result.page_size));

  return (
    <SiteLayout wide>
      <p className="eyebrow">Bộ sưu tập</p>
      <h1>Khám phá thời trang</h1>
      <div className="catalog-layout">
        <aside className="catalog-filters" aria-label="Bộ lọc sản phẩm">
          <label>
            Tìm sản phẩm
            <input
              type="search"
              value={filters.keyword}
              onChange={(event) => changeFilter("keyword", event.target.value)}
              placeholder="Tên sản phẩm"
            />
          </label>
          <label>
            Danh mục
            <select
              value={filters.category_id}
              onChange={(event) => changeFilter("category_id", event.target.value)}
            >
              <option value="">Tất cả</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>
          {categoryError && (
            <p className="form-error" role="alert">
              Không tải được danh mục: {categoryError}
            </p>
          )}
          <label>
            Giá từ (₫)
            <input
              type="number"
              min="0"
              value={filters.min_price}
              onChange={(event) => changeFilter("min_price", event.target.value)}
            />
          </label>
          <label>
            Giá đến (₫)
            <input
              type="number"
              min="0"
              value={filters.max_price}
              onChange={(event) => changeFilter("max_price", event.target.value)}
            />
          </label>
          <label>
            Sắp xếp
            <select
              value={filters.sort}
              onChange={(event) => changeFilter("sort", event.target.value)}
            >
              <option value="newest">Mới nhất</option>
              <option value="price_asc">Giá tăng dần</option>
              <option value="price_desc">Giá giảm dần</option>
            </select>
          </label>
        </aside>
        <section className="catalog-results" aria-label="Danh sách sản phẩm">
          <p>
            {loading
              ? "Đang tải sản phẩm..."
              : error
                ? "Không tải được sản phẩm"
                : `${result.total} sản phẩm`}
          </p>
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : !loading && result.items.length === 0 ? (
            <p>Không tìm thấy sản phẩm phù hợp.</p>
          ) : null}
          {!loading && !error && (
            <div className="product-grid">
              {result.items.map((product) => (
                <Link key={product.id} to={`/products/${product.id}`} className="product-card">
                  {product.image_url ? (
                    <img src={product.image_url} alt={product.name} />
                  ) : (
                    <div className="product-image-placeholder">Chưa có ảnh</div>
                  )}
                  <div className="product-card-body">
                    <h2>{product.name}</h2>
                    <p>{product.shop_name}</p>
                    <strong>
                      {product.price_from == null
                        ? "Chưa có giá"
                        : `Từ ${formatCurrency(product.price_from)}`}
                    </strong>
                    <p>
                      ★{" "}
                      {product.rating_average == null
                        ? "Chưa có đánh giá"
                        : Number(product.rating_average).toFixed(1)}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          )}
          <div className="pagination">
            <button
              type="button"
              disabled={loading || !!error || filters.page <= 1}
              onClick={() => setFilters((previous) => ({ ...previous, page: previous.page - 1 }))}
            >
              Trang trước
            </button>
            <span>
              Trang {filters.page}/{totalPages}
            </span>
            <button
              type="button"
              disabled={loading || !!error || filters.page >= totalPages}
              onClick={() => setFilters((previous) => ({ ...previous, page: previous.page + 1 }))}
            >
              Trang sau
            </button>
          </div>
        </section>
      </div>
    </SiteLayout>
  );
}
