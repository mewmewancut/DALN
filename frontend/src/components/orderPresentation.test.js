import { expect, it } from "vitest";
import { formatDateTime } from "./orderPresentation.js";

it("renders Vietnam delivery dates even across a UTC date boundary", () => {
  expect(formatDateTime("2026-09-30T18:05:00Z")).toContain("01:05");
  expect(formatDateTime("2026-09-30T18:05:00Z")).toContain("1/10/26");
  expect(formatDateTime(null)).toBe("—");
});
