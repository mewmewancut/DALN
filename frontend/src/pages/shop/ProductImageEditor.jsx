import { useState } from "react";
import ProductImage from "../../components/ProductImage.jsx";
import { uploadProductImage } from "../../api/productImages.js";
import { errorMessage } from "../../api/errorMessage.js";
import "../../components/productGallery.css";

const ACCEPT = "image/jpeg,image/png,image/webp";

export default function ProductImageEditor({
  mainImage,
  detailImages,
  onChange,
  onBusyChange,
  disabled,
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function upload(event, main) {
    const files = [...event.target.files];
    event.target.value = "";
    if (!files.length || busy || disabled) return;
    setError("");
    if (!main && detailImages.length + files.length > 10) {
      setError("Chỉ được chọn tối đa 10 ảnh chi tiết.");
      return;
    }
    if (
      files.some((file) => file.size > 5 * 1024 * 1024 || !ACCEPT.split(",").includes(file.type))
    ) {
      setError("Chọn ảnh JPEG, PNG hoặc WebP, tối đa 5 MB mỗi ảnh.");
      return;
    }
    setBusy(true);
    onBusyChange(true);
    let details = [...detailImages];
    try {
      for (const file of files) {
        const url = await uploadProductImage(file);
        if (main) onChange(url, details);
        else {
          details = [...details, url];
          onChange(mainImage, details);
        }
      }
    } catch (requestError) {
      setError(`Không tải được ảnh: ${errorMessage(requestError)}`);
    } finally {
      setBusy(false);
      onBusyChange(false);
    }
  }

  return (
    <fieldset className="image-editor" disabled={disabled || busy}>
      <legend>Ảnh sản phẩm</legend>
      <p className="muted">
        Ảnh chính bắt buộc khi tạo mới. Thêm tối đa 10 ảnh chi tiết. JPEG, PNG, WebP; tối đa 5
        MB/ảnh.
      </p>
      <label>
        Ảnh chính
        <input type="file" accept={ACCEPT} onChange={(event) => upload(event, true)} />
      </label>
      {mainImage && (
        <ProductImage src={mainImage} alt="Ảnh chính đã chọn" className="image-editor-preview" />
      )}
      <label>
        {`Ảnh chi tiết (${detailImages.length}/10)`}
        <input
          type="file"
          multiple
          accept={ACCEPT}
          disabled={detailImages.length >= 10}
          onChange={(event) => upload(event, false)}
        />
      </label>
      <div className="image-editor-details">
        {detailImages.map((url, index) => (
          <div key={`${url}-${index}`}>
            <ProductImage
              src={url}
              alt={`Ảnh chi tiết ${index + 1}`}
              className="image-editor-preview"
            />
            <button
              type="button"
              onClick={() =>
                onChange(
                  mainImage,
                  detailImages.filter((_, position) => position !== index),
                )
              }
            >
              Bỏ ảnh chi tiết {index + 1}
            </button>
          </div>
        ))}
      </div>
      {busy && <p role="status">Đang tải ảnh...</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </fieldset>
  );
}
