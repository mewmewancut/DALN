import { useMemo } from "react";
import { useSearchParams } from "react-router";

const DEFAULTS = {
  keyword: "",
  category_id: "",
  min_price: "",
  max_price: "",
  sort: "newest",
  page: 1,
};

// Filter luôn nằm trên URL để ô tìm kiếm ở header và thẻ danh mục mở đúng kết quả.
export default function useCatalogFilters() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => {
    const page = Number(searchParams.get("page"));
    const sort = searchParams.get("sort");
    return {
      keyword: searchParams.get("keyword") ?? "",
      category_id: searchParams.get("category_id") ?? "",
      min_price: searchParams.get("min_price") ?? "",
      max_price: searchParams.get("max_price") ?? "",
      sort: ["newest", "price_asc", "price_desc"].includes(sort) ? sort : "newest",
      page: Number.isSafeInteger(page) && page > 0 ? page : 1,
    };
  }, [searchParams]);

  function setFilters(update) {
    const next = typeof update === "function" ? update(filters) : update;
    const params = new URLSearchParams();
    for (const key of Object.keys(DEFAULTS)) {
      if (next[key] !== DEFAULTS[key]) params.set(key, String(next[key]));
    }
    setSearchParams(params, { replace: true });
  }

  return [filters, setFilters];
}
