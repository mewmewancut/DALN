import { useState } from "react";
import ProductImage from "./ProductImage.jsx";
import "./productGallery.css";

export default function ProductGallery({ product }) {
  const [selected, setSelected] = useState(0);
  const images = [product.image_url, ...(product.detail_image_urls ?? [])];
  return (
    <div className="detail-media">
      <ProductImage
        src={images[selected]}
        alt={product.name}
        className="detail-image"
        loading="eager"
      />
      {images.length > 1 && (
        <div className="product-thumbnails" aria-label="Ảnh sản phẩm">
          {images.map((src, index) => (
            <button
              type="button"
              key={index}
              aria-label={index === 0 ? "Xem ảnh chính" : `Xem ảnh chi tiết ${index}`}
              aria-pressed={selected === index}
              onClick={() => setSelected(index)}
            >
              <ProductImage src={src} alt={index === 0 ? "Ảnh chính" : `Ảnh chi tiết ${index}`} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
