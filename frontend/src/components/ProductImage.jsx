import { useState } from "react";

import UiIcon from "./UiIcon.jsx";

export default function ProductImage({
  src,
  alt,
  className,
  placeholderClassName = "product-image-placeholder",
  loading = "lazy",
}) {
  const [failedSource, setFailedSource] = useState(null);

  if (!src || failedSource === src) {
    return (
      <div className={placeholderClassName} role="img" aria-label={`${alt}: chưa có ảnh`}>
        <UiIcon name="shirt" />
        <span>Chưa có ảnh</span>
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      width="600"
      height="800"
      loading={loading}
      onError={() => setFailedSource(src)}
    />
  );
}
