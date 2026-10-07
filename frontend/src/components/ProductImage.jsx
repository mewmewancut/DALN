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

  const sampleImage = /^https?:\/\/placehold\.co(?:\/|$)/i.test(src ?? "");
  const illustration = /váy/i.test(alt)
    ? "dress"
    : /quần/i.test(alt)
      ? "pants"
      : /giày/i.test(alt)
        ? "shoe"
        : /túi/i.test(alt)
          ? "bag"
          : "shirt";

  if (!src || sampleImage || failedSource === src) {
    return (
      <div className={placeholderClassName} role="img" aria-label={`${alt}: chưa có ảnh`}>
        <UiIcon name={illustration} />
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
