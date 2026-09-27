export function tokenFromHash(hash) {
  if (!hash?.startsWith("#")) return "";
  return new URLSearchParams(hash.slice(1)).get("token") ?? "";
}
