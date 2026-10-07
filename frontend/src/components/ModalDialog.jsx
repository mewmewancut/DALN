import { useEffect, useRef } from "react";

export default function ModalDialog({
  children,
  onClose,
  closeDisabled = false,
  error,
  className = "dialog",
  ...props
}) {
  const dialog = useRef(null);
  useEffect(() => {
    const node = dialog.current;
    const previousFocus = document.activeElement;
    if (typeof node.showModal === "function") node.showModal();
    else {
      node.setAttribute("open", "");
      node.querySelector("input, select, textarea, button, a[href]")?.focus();
    }
    return () => {
      node.close?.();
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);

  return (
    <dialog
      {...props}
      ref={dialog}
      className={className}
      role="dialog"
      aria-modal="true"
      onCancel={(event) => {
        event.preventDefault();
        if (!closeDisabled) onClose();
      }}
    >
      {children}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </dialog>
  );
}
