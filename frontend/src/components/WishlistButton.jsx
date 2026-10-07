import UiIcon from "./UiIcon.jsx";

export default function WishlistButton({
  isFavorite,
  isBusy = false,
  productName,
  onClick,
  className = "",
}) {
  const action = isFavorite ? "Bỏ" : "Thêm";

  return (
    <button
      type="button"
      className={`wishlist-button${isFavorite ? " is-favorite" : ""}${className ? ` ${className}` : ""}`}
      aria-label={`${action} ${productName} ${isFavorite ? "khỏi" : "vào"} danh sách yêu thích`}
      aria-pressed={isFavorite}
      disabled={isBusy}
      onClick={onClick}
    >
      <UiIcon name="heart" />
    </button>
  );
}
