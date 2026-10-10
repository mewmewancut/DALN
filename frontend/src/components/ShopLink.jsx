import { Link } from "react-router";

export default function ShopLink({ shopId, children }) {
  return shopId == null ? (
    children
  ) : (
    <Link className="shop-link" to={`/shops/${shopId}`}>
      {children}
    </Link>
  );
}
