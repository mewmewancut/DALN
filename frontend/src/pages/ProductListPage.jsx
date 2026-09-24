import { useEffect, useState } from "react";
import { Link } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import SiteLayout from "../components/SiteLayout.jsx";
import { formatCurrency } from "../components/formatCurrency.js";

const PAGE_SIZE = 20;

export default function ProductListPage() {
  const [filtersOpen, setFiltersOpen] = useState(false);
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

  function resetFilters() {
    setFilters({
      keyword: "",
      category_id: "",
      min_price: "",
      max_price: "",
      sort: "newest",
      page: 1,
    });
  }

  const totalPages = Math.max(1, Math.ceil(result.total / result.page_size));
  const activeFilterCount = [
    filters.keyword,
    filters.category_id,
    filters.min_price,
    filters.max_price,
  ].filter(Boolean).length;

  return (
    <SiteLayout wide>
      <header className="catalog-hero">
        <div>
          <p className="eyebrow">Bộ sưu tập chọn lọc</p>
          <h1>Phong cách của bạn, lựa chọn của bạn.</h1>
          <p className="catalog-lead">
            Khám phá sản phẩm từ nhiều gian hàng, xem đúng giá và tồn kho của từng biến thể.
          </p>
        </div>
        <div className="catalog-proof" aria-label="Thông tin catalog">
          <strong>{result.total}</strong>
          <span>sản phẩm đang hiển thị</span>
        </div>
      </header>
      <div className="catalog-mobile-toolbar">
        <button
          type="button"
          className="filter-toggle"
          aria-expanded={filtersOpen}
          aria-controls="catalog-filters"
          onClick={() => setFiltersOpen((current) => !current)}
        >
          Bộ lọc{activeFilterCount ? ` (${activeFilterCount})` : ""}
        </button>
        <span>{result.total} sản phẩm</span>
      </div>
      <div className="catalog-layout">
        <aside
          id="catalog-filters"
          className={`catalog-filters${filtersOpen ? " is-open" : ""}`}
          aria-label="Bộ lọc sản phẩm"
        >
          <div className="filter-heading">
            <div>
              <p className="eyebrow">Tinh chỉnh</p>
              <h2>Bộ lọc</h2>
            </div>
            {activeFilterCount > 0 && (
              <button type="button" className="text-button" onClick={resetFilters}>
                Xóa lọc
              </button>
            )}
          </div>
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
        </aside>
        <section className="catalog-results" aria-label="Danh sách sản phẩm">
          <div className="results-heading">
            <div>
              <p className="eyebrow">Sản phẩm</p>
              <strong>
                {loading
                  ? "Đang tải sản phẩm..."
                  : error
                    ? "Không tải được sản phẩm"
                    : `${result.total} kết quả`}
              </strong>
            </div>
            <label className="sort-field">
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
          </div>
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
                  <div className="product-card-media">
                    {product.image_url ? (
                      <img src={product.image_url} alt={product.name} />
                    ) : (
                      <div className="product-image-placeholder">Chưa có ảnh</div>
                    )}
                    <span className="view-product">Xem chi tiết</span>
                  </div>
                  <div className="product-card-body">
                    <p className="product-shop">{product.shop_name}</p>
                    <h2>{product.name}</h2>
                    <strong className="product-price">
                      {product.price_from == null
                        ? "Chưa có giá"
                        : `Từ ${formatCurrency(product.price_from)}`}
                    </strong>
                    <p className="product-rating">
                      <span aria-hidden="true">★</span>{" "}
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
              <strong>{filters.page}</strong> / {totalPages}
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
