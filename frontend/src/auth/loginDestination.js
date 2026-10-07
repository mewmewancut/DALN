import { homeForRole } from "./session.js";
import { readCheckoutSelection, readGuestCart } from "../cart/guestCart.js";

export function loginDestination(role) {
  return role === "BUYER" && (readGuestCart().items.length > 0 || readCheckoutSelection().resume)
    ? "/cart"
    : homeForRole(role);
}
