import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router";

import { useAuth } from "../../auth/AuthContext.jsx";
import UiIcon from "../UiIcon.jsx";
import { useChatbotSession } from "./ChatbotSession.jsx";
import ChatbotWorkspace from "./ChatbotWorkspace.jsx";
import "./chatbotWidget.css";

export default function ChatbotWidget() {
  const { session } = useAuth();
  const { pathname } = useLocation();
  const { sending, pending } = useChatbotSession();
  const [open, setOpen] = useState(false);
  const launcher = useRef(null);
  const panel = useRef(null);
  const chatPath = session.role === "ADMIN" ? "/admin/chatbot" : "/shop/chatbot";
  const fullPage = pathname.replace(/\/$/, "") === chatPath;

  useEffect(() => {
    if (open && !fullPage) panel.current?.focus();
  }, [open, fullPage]);

  function close() {
    setOpen(false);
    launcher.current?.focus();
  }

  if (fullPage) return null;

  return (
    <div className="genie-widget">
      {open && (
        <section
          id="genie-widget-panel"
          className="genie-widget-panel"
          role="dialog"
          aria-label="Chatbot Genie"
          tabIndex={-1}
          ref={panel}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.stopPropagation();
              close();
            }
          }}
        >
          <header className="genie-widget-header">
            <span>
              <UiIcon name="chat" /> Chatbot Genie
            </span>
            <div>
              <Link to={chatPath}>Mở rộng</Link>
              <button
                type="button"
                className="secondary"
                onClick={close}
                aria-label="Thu gọn chatbot"
              >
                Thu gọn
              </button>
            </div>
          </header>
          <div className="genie-widget-body">
            <ChatbotWorkspace compact />
          </div>
        </section>
      )}
      <button
        type="button"
        className="genie-widget-launcher"
        aria-label={open ? "Thu gọn chatbot" : "Mở chatbot"}
        aria-expanded={open}
        aria-controls={open ? "genie-widget-panel" : undefined}
        ref={launcher}
        onClick={() => (open ? close() : setOpen(true))}
      >
        <UiIcon name="chat" />
        <span>{sending || pending ? "Genie đang xử lý…" : "Chatbot Genie"}</span>
      </button>
    </div>
  );
}
