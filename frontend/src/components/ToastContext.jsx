import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null);
  const timerRef = useRef(null);

  const hideToast = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    setToast(null);
  }, []);

  const showToast = useCallback((message, type = "success") => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    setToast({
      message,
      type,
    });

    timerRef.current = setTimeout(() => {
      setToast(null);
      timerRef.current = null;
    }, 3500);
  }, []);

  useEffect(
    () => () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    },
    [],
  );

  return (
    <ToastContext.Provider value={{ showToast, hideToast }}>
      {children}

      {toast && (
        <div
          className={`app-toast app-toast-${toast.type}`}
          role="status"
          aria-live="polite"
        >
          <span>{toast.message}</span>
          <button
            type="button"
            className="app-toast-close"
            onClick={hideToast}
            aria-label="Đóng thông báo"
          >
            ×
          </button>
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);

  if (!context) {
    throw new Error("useToast phải được sử dụng bên trong ToastProvider.");
  }

  return context;
}