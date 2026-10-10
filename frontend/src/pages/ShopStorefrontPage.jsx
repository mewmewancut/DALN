import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import ProductCatalog from "../components/catalog/ProductCatalog.jsx";
import SiteLayout from "../components/SiteLayout.jsx";
import UiIcon from "../components/UiIcon.jsx";
import "./shopStorefront.css";

function ShopStorefront({ id }) {
  const [shop, setShop] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [unavailable, setUnavailable] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const validId = /^\d+$/.test(id) && Number.isSafeInteger(Number(id)) && Number(id) > 0;

  useEffect(() => {
    let active = true;
    if (!validId)
      return () => {
        active = false;
      };
    setLoading(true);
    setShop(null);
    setError("");
    setUnavailable(false);
    client
      .get(`/shops/${id}`)
      .then(({ data }) => {
        if (active) setShop(data);
      })
      .catch((requestError) => {
        if (!active) return;
        if (requestError.response?.status === 404) setUnavailable(true);
        else setError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id, refreshKey, validId]);

  return (
    <SiteLayout wide>
      <nav className="breadcrumb" aria-label="Điều hướng gian hàng">
        <Link to="/">Sản phẩm</Link>
        <span aria-hidden="true">/</span>
        <span>{shop?.name ?? "Gian hàng"}</span>
      </nav>
      {!validId || unavailable ? (
        <section className="catalog-state">
          <h1>Gian hàng không khả dụng</h1>
          <p>Shop có thể đã ngừng hoạt động hoặc đường dẫn không tồn tại.</p>
          <p>Bạn vẫn có thể xem lịch sử đơn hàng đã mua trong mục Đơn hàng.</p>
          <Link to="/">Khám phá sản phẩm khác</Link>
        </section>
      ) : loading ? (
        <p role="status">Đang tải gian hàng...</p>
      ) : error ? (
        <section className="catalog-state catalog-state-error">
          <h1>Không thể tải gian hàng</h1>
          <p className="form-error" role="alert">
            {error}
          </p>
          <button type="button" onClick={() => setRefreshKey((value) => value + 1)}>
            Thử lại
          </button>
        </section>
      ) : (
        shop && (
          <>
            <header className="shop-storefront-hero">
              <div className="shop-storefront-mark" aria-hidden="true">
                <UiIcon name="store" />
              </div>
              <div className="shop-storefront-info">
                <p className="eyebrow">Gian hàng thời trang</p>
                <h1>{shop.name}</h1>
                <p className="shop-storefront-description">
                  {shop.description?.trim() || "Shop chưa cập nhật phần giới thiệu."}
                </p>
                <p className="muted">
                  Tham gia từ{" "}
                  {new Intl.DateTimeFormat("vi-VN", {
                    timeZone: "Asia/Ho_Chi_Minh",
                    month: "2-digit",
                    year: "numeric",
                  }).format(new Date(shop.created_at))}
                </p>
              </div>
            </header>
            <h2 className="shop-storefront-products">Sản phẩm của shop</h2>
            <ProductCatalog shopId={shop.id} />
          </>
        )
      )}
    </SiteLayout>
  );
}

export default function ShopStorefrontPage() {
  const { id } = useParams();
  return <ShopStorefront key={id} id={id} />;
}
