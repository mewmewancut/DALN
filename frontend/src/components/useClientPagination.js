import { useEffect, useMemo, useState } from "react";

export const CLIENT_PAGE_SIZE = 10;

export function matchesSearch(keyword, ...values) {
  const normalizedKeyword = keyword.trim().toLocaleLowerCase("vi-VN");
  if (!normalizedKeyword) return true;
  return values.some((value) =>
    String(value ?? "")
      .toLocaleLowerCase("vi-VN")
      .includes(normalizedKeyword),
  );
}

export default function useClientPagination(items, pageSize = CLIENT_PAGE_SIZE) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const pageItems = useMemo(() => {
    const start = (page - 1) * pageSize;
    return items.slice(start, start + pageSize);
  }, [items, page, pageSize]);

  return {
    page,
    pageItems,
    pageSize,
    setPage,
    total: items.length,
  };
}
