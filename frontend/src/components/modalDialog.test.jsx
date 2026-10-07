// @vitest-environment jsdom
import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import ModalDialog from "./ModalDialog.jsx";

let container;
let root;
beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.restoreAllMocks();
  delete globalThis.IS_REACT_ACT_ENVIRONMENT;
});

function Example({ busy = false, error, onClose = () => {} }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>Mở</button>
      {open && (
        <ModalDialog
          aria-label="Sửa sản phẩm"
          closeDisabled={busy}
          error={error}
          onClose={() => {
            onClose();
            setOpen(false);
          }}
        >
          <label>
            Tên sản phẩm
            <input />
          </label>
          <button onClick={() => setOpen(false)}>Đóng</button>
        </ModalDialog>
      )}
    </>
  );
}

async function open(props = {}) {
  await act(async () => root.render(<Example {...props} />));
  const opener = container.querySelector("button");
  opener.focus();
  await act(async () => opener.click());
  return opener;
}

it("focuses the form, handles native Escape cancellation and restores the opener", async () => {
  const opener = await open();
  const dialog = container.querySelector("dialog");
  expect(dialog.open).toBe(true);
  expect(document.activeElement).toBe(dialog.querySelector("input"));
  const cancel = new Event("cancel", { cancelable: true });
  await act(async () => dialog.dispatchEvent(cancel));
  expect(cancel.defaultPrevented).toBe(true);
  expect(container.querySelector("dialog")).toBeNull();
  expect(document.activeElement).toBe(opener);
});

it("keeps the dialog open while its operation is pending", async () => {
  const onClose = vi.fn();
  await open({ busy: true, onClose });
  await act(async () =>
    container.querySelector("dialog").dispatchEvent(new Event("cancel", { cancelable: true })),
  );
  expect(onClose).not.toHaveBeenCalled();
  expect(container.querySelector("dialog").open).toBe(true);
});

it("presents request failures inside the open dialog", async () => {
  await open({ error: "Không thể lưu, hãy thử lại." });
  expect(container.querySelector('dialog [role="alert"]').textContent).toBe(
    "Không thể lưu, hãy thử lại.",
  );
  expect(container.querySelector("dialog").open).toBe(true);
});

it("opens in the browser top layer and closes the native dialog on unmount", async () => {
  const showModal = vi.fn(function () {
    this.setAttribute("open", "");
  });
  const close = vi.fn();
  const originalShowModal = Object.getOwnPropertyDescriptor(
    HTMLDialogElement.prototype,
    "showModal",
  );
  const originalClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "close");
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: showModal,
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", { configurable: true, value: close });
  try {
    await open();
    expect(showModal).toHaveBeenCalledOnce();
    await act(async () => container.querySelector("dialog button").click());
    expect(close).toHaveBeenCalledOnce();
  } finally {
    if (originalShowModal)
      Object.defineProperty(HTMLDialogElement.prototype, "showModal", originalShowModal);
    else delete HTMLDialogElement.prototype.showModal;
    if (originalClose) Object.defineProperty(HTMLDialogElement.prototype, "close", originalClose);
    else delete HTMLDialogElement.prototype.close;
  }
});
