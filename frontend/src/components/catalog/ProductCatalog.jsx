import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import { useAuth } from "../../auth/AuthContext.jsx";
import ProductCard from "../ProductCard.jsx";
import RecommendedProducts from "../RecommendedProducts.jsx";
import useWishlist from "../useWishlist.js";
import useCatalogFilters from "./useCatalogFilters.js";

const PAGE_SIZE = 20;

export default function ProductCatalog({ shopId = null }) {
  const navigate = useNavigate();
  const { session } = useAuth();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [keywordDraft, setKeywordDraft] = useState("");
  const keywordTimer = useRef(null);
  const priceTimer = useRef(null);
  const [priceDraft, setPriceDraft] = useState({ min_price: "", max_price: "" });
  const isComposing = useRef(false);
  const [filters, setFilters] = useCatalogFilters(shopId != null);
  const [categories, setCategories] = useState([]);
  const [categoryError, setCategoryError] = useState("");
  const [result, setResult] = useState({
    items: [],
    total: 0,
    page: 1,
    page_size: PAGE_SIZE,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [fallbackProducts, setFallbackProducts] = useState([]);
  const [fallbackLoading, setFallbackLoading] = useState(false);

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

    const params = {
      sort: filters.sort,
      page: filters.page,
      page_size: PAGE_SIZE,
      ...(shopId == null ? {} : { shop_id: shopId }),
    };

    for (const key of ["keyword", "category_id", "min_price", "max_price"]) {
      if (filters[key] !== "") {
        params[key] = filters[key];
      }
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
  }, [filters, refreshKey, shopId]);

  useEffect(() => {
    if (
      shopId != null ||
      loading ||
      error ||
      result.items.length > 0 ||
      !filters.keyword.trim()
    ) {
      setFallbackProducts([]);
      setFallbackLoading(false);
      return;
    }

    let active = true;
    const controller = new AbortController();

    async function loadFallback() {
      setFallbackLoading(true);
      setFallbackProducts([]);

      try {
        const words = filters.keyword
          .trim()
          .split(/\s+/)
          .filter((word) => word.length >= 2);

        let products = [];

        for (const word of [...words].sort((a, b) => b.length - a.length)) {
          const response = await client.get("/products", {
            params: {
              keyword: word,
              page: 1,
              page_size: 6,
            },
            signal: controller.signal,
          });

          products = response.data.items || [];
          if (products.length > 0) break;
        }

        if (products.length === 0) {
          const response = await client.get("/products", {
            params: {
              sort: "newest",
              page: 1,
              page_size: 6,
            },
            signal: controller.signal,
          });

          products = response.data.items || [];
        }

        if (active) setFallbackProducts(products);
      } catch (requestError) {
        if (active) setFallbackProducts([]);
      } finally {
        if (active) setFallbackLoading(false);
      }
    }

    loadFallback();

    return () => {
      active = false;
      controller.abort();
    };
  }, [shopId, loading, error, result, filters.keyword]);
  useEffect(() => {
    setKeywordDraft(filters.keyword);
  }, [filters.keyword]);

  useEffect(() => {
    return () => clearTimeout(keywordTimer.current);
  }, []);
  useEffect(() => {
    setPriceDraft({
      min_price: filters.min_price,
      max_price: filters.max_price,
    });
  }, [filters.min_price, filters.max_price]);

  useEffect(() => {
    return () => clearTimeout(priceTimer.current);
  }, []);

  function changePrice(key, value) {
    setPriceDraft((previous) => ({ ...previous, [key]: value }));
    clearTimeout(priceTimer.current);

    priceTimer.current = setTimeout(() => {
      changeFilter(key, value);
    }, 600);
  }

  function changeFilter(key, value) {
    setFilters((previous) => ({
      ...previous,
      [key]: value,
      page: 1,
    }));
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
    <>
      {shopId == null && (
  <header className="fashion-hero">
    <div className="fashion-hero-content">
      <span className="fashion-eyebrow">
        FASHION MARKETPLACE
      </span>

      <h1>
        Khám phá phong cách
        <br />
        của riêng bạn.
      </h1>

      <p>
        Những thiết kế thời trang hiện đại, tinh tế
        dành cho phong cách riêng của bạn.
      </p>

      <a href="#catalog-products" className="fashion-hero-button">
        Khám phá bộ sưu tập
      </a>
    </div>

    <div className="fashion-hero-art" aria-hidden="true">
      <span>THE NEW EDIT</span>
      <strong>STYLE / 2026</strong>
    </div>
  </header>
)}

            {/* DALN FEATURED CATEGORIES */}
      {shopId == null && categories.length > 0 && (
        <section className="daln-featured-categories">
          <div className="daln-category-heading">
            <span>KHÁM PHÁ PHONG CÁCH</span>
            <h2>Danh mục nổi bật</h2>
            <p>Khám phá những lựa chọn thời trang dành cho bạn.</p>
          </div>

          <div className="daln-category-grid">
            {categories.slice(0, 3).map((category, index) => (
              <a
                key={category.id}
                href={`/?category_id=${encodeURIComponent(category.id)}#catalog-products`}
                className={`daln-category-card daln-category-${index + 1}`}
              >
                <div className="daln-category-card-content">
                  <span>COLLECTION 0{index + 1}</span>
                  <h3>{category.name}</h3>
                  <span className="daln-category-explore">
                    Khám phá bộ sưu tập →
                  </span>
                </div>
              </a>
            ))}
          </div>
        </section>
      )}
      {shopId == null && session?.role === "BUYER" && (
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
                value={keywordDraft}
                onChange={(event) => {
                  const value = event.target.value;
                  setKeywordDraft(value);
                  clearTimeout(keywordTimer.current);

                  if (isComposing.current || event.nativeEvent.isComposing) {
                    return;
                  }

                  keywordTimer.current = setTimeout(() => {
                    changeFilter("keyword", value);
                  }, 500);
                }}
                onCompositionStart={() => {
                  isComposing.current = true;
                  clearTimeout(keywordTimer.current);
                }}
                onCompositionEnd={(event) => {
                  isComposing.current = false;
                  const value = event.currentTarget.value;
                  setKeywordDraft(value);
                  clearTimeout(keywordTimer.current);

                  keywordTimer.current = setTimeout(() => {
                    changeFilter("keyword", value);
                  }, 500);
                }}
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
              max="1000000000"
              value={priceDraft.min_price}
              onChange={(event) => changePrice("min_price", event.target.value)}
            />
          </label>

          <label>
            Giá đến (₫)
            <input
              type="number"
              min="0"
              max="1000000000"
              value={priceDraft.max_price}
              onChange={(event) => changePrice("max_price", event.target.value)}
            />
          </label>
        </aside>

        <section id="catalog-products" className="catalog-results" aria-label="Danh sách sản phẩm">
          <div className="results-heading">
            {/* DALN PRODUCT SECTION HEADING */}
            {shopId == null && (
              <div className="daln-product-heading">
                <span>DALN COLLECTION</span>
                <h2>Khám phá sản phẩm</h2>
                <p>Những lựa chọn thời trang dành cho phong cách của bạn.</p>
              </div>
            )}
            <div>
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

          {wishlistError && (
            <p className="form-error" role="alert">
              Không cập nhật được yêu thích: {wishlistError}
            </p>
          )}

          {loading ? (
            <div className="product-grid" aria-label="Đang tải sản phẩm" aria-busy="true">
              {Array.from({ length: 8 }, (_, index) => (
                <div key={index} className="product-card product-card-skeleton" aria-hidden="true">
                  <div className="skeleton skeleton-product-image" />

                  <div className="product-card-body">
                    <div className="skeleton skeleton-shop" />
                    <div className="skeleton skeleton-title" />
                    <div className="skeleton skeleton-price" />
                    <div className="skeleton skeleton-rating" />
                  </div>
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="catalog-state catalog-state-error">
              <strong>Không thể tải sản phẩm</strong>
              <p className="form-error" role="alert">
                {error}
              </p>
              <button type="button" onClick={() => setRefreshKey((value) => value + 1)}>
                Thử lại
              </button>
            </div>
          ) : result.items.length === 0 ? (
            <>
              <div className="catalog-state">
              <strong>
                {shopId != null && activeFilterCount === 0
                  ? "Shop chưa có sản phẩm đang bán"
                  : "Không tìm thấy sản phẩm phù hợp"}
              </strong>

              <p>
                {shopId != null && activeFilterCount === 0
                  ? "Bạn có thể quay lại sau hoặc khám phá sản phẩm từ các shop khác."
                  : "Thử thay đổi từ khóa, danh mục hoặc khoảng giá để xem thêm kết quả."}
              </p>

              {activeFilterCount > 0 && (
                <button type="button" onClick={resetFilters}>
                  Xóa bộ lọc
                </button>
              )}
            </div>

              {shopId == null && filters.keyword.trim() && (
                <div className="catalog-fallback">
                  <h2>Có thể bạn sẽ thích</h2>
                  <p>Khám phá những sản phẩm khác dành cho bạn.</p>

                  {fallbackLoading ? (
                    <p>Đang tải gợi ý...</p>
                  ) : fallbackProducts.length > 0 ? (
                    <div className="product-grid">
                      {fallbackProducts.map((product) => (
                        <ProductCard
                          key={product.id}
                          product={product}
                          isFavorite={favoriteIds.has(product.id)}
                          isBusy={wishlistLoading || busyIds.has(product.id)}
                          onToggleFavorite={toggleFavorite}
                        />
                      ))}
                    </div>
                  ) : (
                    <p>Hiện chưa có sản phẩm đề xuất.</p>
                  )}
                </div>
              )}
            </>
          ) : (
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
              onClick={() =>
                setFilters((previous) => ({
                  ...previous,
                  page: previous.page - 1,
                }))
              }
            >
              Trang trước
            </button>

            <span>
              <strong>{filters.page}</strong> / {totalPages}
            </span>

            <button
              type="button"
              disabled={loading || !!error || filters.page >= totalPages}
              onClick={() =>
                setFilters((previous) => ({
                  ...previous,
                  page: previous.page + 1,
                }))
              }
            >
              Trang sau
            </button>
          </div>
        </section>
      </div>
    </>
  );
}
