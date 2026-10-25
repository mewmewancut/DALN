import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import client from "../api/client.js";
import ProductImage from "./ProductImage.jsx";
import { formatCurrency } from "./formatCurrency.js";

export default function HeaderSearch() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [keyword, setKeyword] = useState(
    searchParams.get("keyword") || ""
  );
  const [suggestions, setSuggestions] = useState([]);
  const [relatedProducts, setRelatedProducts] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const searchRef = useRef(null);

  useEffect(() => {
    setKeyword(searchParams.get("keyword") || "");
  }, [searchParams]);

  useEffect(() => {
    const query = keyword.trim();

    if (query.length < 2 || !open) {
      setSuggestions([]);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const response = await client.get("/products", {
          params: {
            keyword: query,
            page: 1,
            page_size: 5,
          },
          signal: controller.signal,
        });
        const matches = response.data.items || [];
        setSuggestions(matches);
        setRelatedProducts([]);

        if (matches.length === 0) {
          const words = query.split(/\s+/).filter((word) => word.length >= 2);
          let related = [];

          for (const word of [...words].sort((a, b) => b.length - a.length)) {
            if (controller.signal.aborted) return;

            const relatedResponse = await client.get("/products", {
              params: {
                keyword: word,
                page: 1,
                page_size: 5,
              },
              signal: controller.signal,
            });

            related = relatedResponse.data.items || [];

            if (related.length > 0) break;
          }

          if (related.length === 0) {
            const fallbackResponse = await client.get("/products", {
              params: {
                sort: "newest",
                page: 1,
                page_size: 5,
              },
              signal: controller.signal,
            });

            related = fallbackResponse.data.items || [];
          }

          if (!controller.signal.aborted) {
            setRelatedProducts(related);
          }
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setSuggestions([]);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }, 300);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [keyword, open]);

  useEffect(() => {
    function handleOutside(event) {
      if (!searchRef.current?.contains(event.target)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutside);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
    };
  }, []);

  function submitSearch(event) {
    event.preventDefault();
    const query = keyword.trim();
    setOpen(false);
    navigate(query ? `/?keyword=${encodeURIComponent(query)}` : "/");
  }

  function selectProduct(productId) {
    setOpen(false);
    navigate(`/products/${productId}`);
  }

  return (
    <div className="header-search" ref={searchRef}>
      <form className="header-search-form" onSubmit={submitSearch}>
        <span className="header-search-icon" aria-hidden="true">
          ⌕
        </span>

        <input
          type="search"
          value={keyword}
          placeholder="Tìm sản phẩm, phong cách..."
          aria-label="Tìm kiếm sản phẩm"
          onChange={(event) => {
            setKeyword(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false);
          }}
        />

        <button type="submit">Tìm kiếm</button>
      </form>

      {open && keyword.trim().length >= 2 && (
        <div className="header-search-dropdown">
          <div className="header-search-dropdown-title">
            Gợi ý sản phẩm
          </div>

          {loading ? (
            <p className="header-search-empty">Đang tìm kiếm...</p>
          ) : suggestions.length === 0 && relatedProducts.length === 0 ? (
            <p className="header-search-empty">
              Không tìm thấy sản phẩm phù hợp
            </p>
          ) : (
            <>
              {suggestions.length === 0 && (
                <p className="header-search-empty">
                  Không tìm thấy chính xác. Có thể bạn sẽ thích:
                </p>
              )}
              {(suggestions.length > 0 ? suggestions : relatedProducts).map((product) => (
              <button
                key={product.id}
                type="button"
                className="header-search-suggestion"
                onClick={() => selectProduct(product.id)}
              >
                <span className="header-search-thumb">
                  <ProductImage
                    src={product.image_url}
                    alt={product.name}
                  />
                </span>

                <span className="header-search-info">
                  <strong>{product.name}</strong>
                  <small>
                    {product.price_from == null
                      ? "Chưa có giá"
                      : formatCurrency(product.price_from)}
                  </small>
                </span>
              </button>
              ))}
            </>
          )}

          <button
            type="button"
            className="header-search-all"
            onClick={submitSearch}
          >
            Xem tất cả kết quả →
          </button>
        </div>
      )}
    </div>
  );
}
