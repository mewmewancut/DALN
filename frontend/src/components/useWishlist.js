import { useEffect, useState } from "react";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";

export default function useWishlist(enabled) {
  const [favoriteIds, setFavoriteIds] = useState(new Set());
  const [busyIds, setBusyIds] = useState(new Set());
  const [wishlistError, setWishlistError] = useState("");
  const [wishlistLoading, setWishlistLoading] = useState(Boolean(enabled));

  useEffect(() => {
    let active = true;
    if (!enabled) {
      setFavoriteIds(new Set());
      setWishlistError("");
      setWishlistLoading(false);
      return () => {
        active = false;
      };
    }

    setWishlistLoading(true);
    client
      .get("/wishlist")
      .then((response) => {
        const items = Array.isArray(response.data) ? response.data : [];
        if (active) setFavoriteIds(new Set(items.map((item) => item.product_id)));
      })
      .catch((requestError) => {
        if (active) setWishlistError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setWishlistLoading(false);
      });
    return () => {
      active = false;
    };
  }, [enabled]);

  async function toggleWishlist(productId) {
    const wasFavorite = favoriteIds.has(productId);
    setBusyIds((current) => new Set(current).add(productId));
    setWishlistError("");
    try {
      if (wasFavorite) {
        await client.delete(`/wishlist/items/${productId}`);
      } else {
        await client.put(`/wishlist/items/${productId}`);
      }
      setFavoriteIds((current) => {
        const next = new Set(current);
        if (wasFavorite) next.delete(productId);
        else next.add(productId);
        return next;
      });
    } catch (requestError) {
      setWishlistError(errorMessage(requestError));
    } finally {
      setBusyIds((current) => {
        const next = new Set(current);
        next.delete(productId);
        return next;
      });
    }
  }

  return { favoriteIds, busyIds, wishlistError, wishlistLoading, toggleWishlist };
}
