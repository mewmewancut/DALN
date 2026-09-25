import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

const frontendRoot = fileURLToPath(new URL(".", import.meta.url));

function runTool(binary, args, source) {
  const result = spawnSync(
    process.execPath,
    [fileURLToPath(new URL(`./node_modules/${binary}`, import.meta.url)), ...args],
    { cwd: frontendRoot, input: source, encoding: "utf8", timeout: 20000 },
  );

  if (result.error) throw result.error;
  return result;
}

function lint(source) {
  return runTool(
    "eslint/bin/eslint.js",
    ["--stdin", "--stdin-filename", "src/quality-probe.jsx", "--max-warnings=0"],
    source,
  );
}

it.each([
  ["export const price = missingPrice;", "no-undef"],
  ["export function Page() { return <MissingCard />; }", "no-undef"],
  [
    'import { useState } from "react"; export function Page({ enabled }) { if (enabled) useState(0); return null; }',
    "react-hooks/rules-of-hooks",
  ],
  [
    'import { useEffect } from "react"; export function Page({ name }) { useEffect(() => { document.title = name; }, []); return null; }',
    "react-hooks/exhaustive-deps",
  ],
])(
  "ESLint rejects invalid code: %s",
  (source, diagnostic) => {
    const result = lint(source);
    expect(result.status, result.stderr).toBe(1);
    expect(result.stdout).toContain(diagnostic);
  },
  20000,
);

it("ESLint accepts JSX imports and unconditional hooks", () => {
  const result = lint(
    'import { useState } from "react"; import { Link } from "react-router"; export function Page() { const [count] = useState(0); return <Link to="/">{count}</Link>; }',
  );

  expect(result.status, result.stdout + result.stderr).toBe(0);
});

it("Prettier check rejects unformatted code and accepts formatted output", () => {
  const binary = "prettier/bin/prettier.cjs";
  const args = ["--stdin-filepath", "src/quality-probe.js"];
  const source = "export const total=(price,quantity)=>price*quantity";

  const rejected = runTool(binary, [...args, "--check"], source);
  expect(rejected.status, rejected.stdout + rejected.stderr).toBe(1);

  const formatted = runTool(binary, args, source);
  expect(formatted.status, formatted.stderr).toBe(0);

  const accepted = runTool(binary, [...args, "--check"], formatted.stdout);
  expect(accepted.status, accepted.stdout + accepted.stderr).toBe(0);
});