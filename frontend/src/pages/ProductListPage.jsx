import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import { useAuth } from "../auth/AuthContext.jsx";
import ProductCard from "../components/ProductCard.jsx";
import RecommendedProducts from "../components/RecommendedProducts.jsx";
import SiteLayout from "../components/SiteLayout.jsx";
import useWishlist from "../components/useWishlist.js";

const PAGE_SIZE = 20;

export default function ProductListPage() {
  const navigate = useNavigate();
  const { session } = useAuth();
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
  const { favoriteIds, busyIds, wishlistError, wishlistLoading, toggleWishlist } = useWishlist(
    session?.role === "BUYER",
  );

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

  function toggleFavorite(event, productId) {
    event.preventDefault();
    event.stopPropagation();
    if (!session) {
      navigate("/login");
      return;
    }
    toggleWishlist(productId);
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
      {session?.role === "BUYER" && (
        <RecommendedProducts
          key={session.token}
          favoriteIds={favoriteIds}
          busyIds={busyIds}
          wishlistLoading={wishlistLoading}
          wishlistError={wishlistError}
          onToggleFavorite={toggleFavorite}
        />
      )}
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
          {wishlistError && (
            <p className="form-error" role="alert">
              Không cập nhật được yêu thích: {wishlistError}
            </p>
          )}
          {!loading && !error && (
            <div className="product-grid">
              {result.items.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  isFavorite={favoriteIds.has(product.id)}
                  isBusy={wishlistLoading || busyIds.has(product.id)}
                  onToggleFavorite={toggleFavorite}
                />
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
