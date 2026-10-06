import { useEffect, useRef, useState } from "react";

import client from "../api/client.js";
import { errorMessage } from "../api/errorMessage.js";
import { useAuth } from "../auth/AuthContext.jsx";
import ChatHistory from "../components/chatbot/ChatHistory.jsx";
import useChatHistory from "../components/chatbot/useChatHistory.js";
import ChatResult from "../components/chatbot/ChatResult.jsx";
import "../components/chatbot/chatbot.css";

const SUGGESTIONS = [
  "Doanh thu tháng này là bao nhiêu?",
  "Sản phẩm nào bán chạy nhất?",
  "Những sản phẩm nào đang có tồn kho thấp?",
  "Tỷ lệ hủy đơn là bao nhiêu?",
];

export default function ChatbotPage() {
  const { session } = useAuth();
  const [config, setConfig] = useState(null);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [conversationToken, setConversationToken] = useState(null);
  const [pending, setPending] = useState(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [paused, setPaused] = useState(false);
  const [retry, setRetry] = useState(0);
  const [reload, setReload] = useState(0);
  const generation = useRef(null);
  const history = useChatHistory(session?.token, !!config);
  const refreshHistory = history.refresh;
  const [selected, setSelected] = useState(null);
  const [opening, setOpening] = useState(false);
  const [canResume, setCanResume] = useState(true);
  const [hasOlder, setHasOlder] = useState(false);
  const bottom = useRef(null);

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  useEffect(() => {
    if (!config?.provisioning || config.available) return;
    const timer = setTimeout(() => setReload((n) => n + 1), 5000);
    return () => clearTimeout(timer);
  }, [config]);

  async function openHistory(id, older = false) {
    if (sending || pending || opening) return;
    const current = generation.current;
    setOpening(true);
    setError("");
    try {
      const { data } = await client.get(`/analytics/chat/conversations/${id}`, {
        params: older ? { before_id: messages[0]?.saved_id } : {},
      });
      if (generation.current !== current) return;
      setSelected(id);
      setMessages((items) => (older ? [...data.messages, ...items] : data.messages));
      setConversationToken(data.conversation_token);
      setCanResume(data.can_resume);
      setHasOlder(data.has_more);
      setQuestion("");
      const waiting = data.messages.find((item) => item.status === "PENDING");
      if (waiting && data.can_resume)
        setPending({ ...waiting, conversation_token: data.conversation_token });
    } catch (failure) {
      if (generation.current === current) setError(errorMessage(failure));
    } finally {
      if (generation.current === current) setOpening(false);
    }
  }

  useEffect(() => {
    const current = Symbol("chat-session");
    generation.current = current;
    const controller = new AbortController();
    setSelected(null);
    setOpening(false);
    setCanResume(true);
    setHasOlder(false);
    setConfig(null);
    setMessages([]);
    setConversationToken(null);
    setPending(null);
    setSending(false);
    setError("");
    setPaused(false);
    client
      .get("/analytics/chat/config", { signal: controller.signal })
      .then(({ data }) => {
        if (generation.current === current) setConfig(data);
      })
      .catch((failure) => {
        if (!controller.signal.aborted && generation.current === current)
          setError(errorMessage(failure));
      });
    return () => {
      controller.abort();
      generation.current = null;
    };
  }, [session.token, reload]);

  useEffect(() => {
    if (!pending) return;
    const controller = new AbortController();
    let timer;
    let attempts = 0;
    setPaused(false);

    async function poll() {
      try {
        const { data } = await client.post(
          `/analytics/chat/messages/${pending.message_id}`,
          {
            conversation_token: pending.conversation_token,
          },
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        if (data.status === "PENDING") {
          if (++attempts >= 60) {
            setPaused(true);
            setError("Genie đang xử lý lâu hơn dự kiến. Bạn có thể kiểm tra lại kết quả.");
          } else {
            timer = setTimeout(poll, 2000);
          }
          return;
        }
        setMessages((items) =>
          items.map((m) => (m.message_id === pending.message_id ? { ...m, ...data } : m)),
        );
        setPending(null);
        refreshHistory();
        setError("");
      } catch (failure) {
        if (!controller.signal.aborted) {
          setPaused(true);
          setError(errorMessage(failure));
        }
      }
    }
    timer = setTimeout(poll, 2000);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [pending, retry, refreshHistory]);

  async function send(event) {
    event.preventDefault();
    const content = question.trim();
    if (!content || sending || pending || opening || !canResume || !config?.available) return;
    const current = generation.current;
    setSending(true);
    setError("");
    try {
      const { data } = await client.post("/analytics/chat/messages", {
        question: content,
        ...(conversationToken ? { conversation_token: conversationToken } : {}),
      });
      if (generation.current !== current) return;
      setMessages((items) => [...items, { ...data, question: content }]);
      if (data.conversation_id) setSelected(data.conversation_id);
      refreshHistory();
      setConversationToken(data.conversation_token);
      setQuestion("");
      if (data.status === "PENDING") setPending(data);
    } catch (failure) {
      if (generation.current === current) setError(errorMessage(failure));
    } finally {
      if (generation.current === current) setSending(false);
    }
  }

  function reset() {
    setSelected(null);
    setCanResume(true);
    setOpening(false);
    setHasOlder(false);
    generation.current = Symbol("new-conversation");
    setMessages([]);
    setConversationToken(null);
    setPending(null);
    setQuestion("");
    setError("");
    setPaused(false);
  }

  return (
    <section className="genie-chat">
      <div className="genie-workspace">
        <ChatHistory
          history={history}
          selected={selected}
          busy={sending || !!pending || opening}
          onSelect={openHistory}
          onDeleted={(id) => {
            if (selected === id) reset();
          }}
        />
        <div className="genie-main">
          <div className="page-heading">
            <div>
              <p className="eyebrow">Trợ lý dữ liệu</p>
              <h1>Chatbot Genie</h1>
            </div>
            <button
              type="button"
              className="secondary"
              onClick={reset}
              disabled={sending || opening || (!messages.length && !conversationToken)}
            >
              Cuộc trò chuyện mới
            </button>
          </div>
          {opening && <p role="status">Đang mở cuộc trò chuyện…</p>}
          {!canResume && (
            <p className="genie-note">
              Cấu hình chatbot đã thay đổi. Bạn vẫn xem được lịch sử; hãy tạo cuộc trò chuyện mới để
              hỏi tiếp.
            </p>
          )}
          {hasOlder && (
            <button
              disabled={opening || sending || !!pending}
              onClick={() => openHistory(selected, true)}
            >
              Xem tin nhắn cũ hơn
            </button>
          )}
          {config ? (
            <p className="genie-scope">
              <strong>Phạm vi: {config.scope}.</strong> {config.message}
            </p>
          ) : (
            !error && <p role="status">Đang tải chatbot…</p>
          )}
          {error && <p role="alert">{error}</p>}
          {!config && error && (
            <button type="button" onClick={() => setReload((n) => n + 1)}>
              Tải lại
            </button>
          )}
          {pending && paused && (
            <button
              type="button"
              onClick={() => {
                setError("");
                setRetry((n) => n + 1);
              }}
            >
              Kiểm tra lại kết quả
            </button>
          )}
          {(config?.available || messages.length > 0) && (
            <>
              {!messages.length && (
                <div className="genie-welcome">
                  <h2>Bạn muốn tìm hiểu điều gì?</h2>
                  <p>Hỏi về doanh thu, sản phẩm bán chạy hoặc tồn kho thấp.</p>
                  <div className="genie-suggestions">
                    {SUGGESTIONS.map((text) => (
                      <button
                        key={text}
                        className="secondary"
                        type="button"
                        disabled={sending || !!pending || opening || !canResume}
                        onClick={() => setQuestion(text)}
                      >
                        {text}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div
                className="genie-transcript"
                aria-live="polite"
                aria-busy={sending || (!!pending && !paused)}
              >
                {messages.map((message) => (
                  <ChatResult key={message.message_id} message={message} />
                ))}
                <div ref={bottom} />
                {sending && <p role="status">Đang gửi câu hỏi…</p>}
              </div>
              {config?.available && (
                <>
                  <form onSubmit={send} className="genie-form">
                    <label>
                      Câu hỏi
                      <textarea
                        value={question}
                        maxLength={2000}
                        rows={3}
                        onChange={(event) => setQuestion(event.target.value)}
                        onKeyDown={(event) => {
                          if (
                            event.key === "Enter" &&
                            !event.shiftKey &&
                            !event.nativeEvent.isComposing &&
                            event.keyCode !== 229
                          ) {
                            send(event);
                          }
                        }}
                        placeholder="Ví dụ: Doanh thu tháng này là bao nhiêu?"
                        disabled={sending || !!pending || opening || !canResume}
                      />
                    </label>
                    <button
                      type="submit"
                      disabled={!question.trim() || sending || !!pending || opening || !canResume}
                    >
                      Gửi câu hỏi
                    </button>
                  </form>
                  <p className="genie-note">Enter để gửi · Shift + Enter để xuống dòng.</p>
                  <p className="genie-note">
                    Kết quả dùng dữ liệu tại lần cập nhật gần nhất. Chatbot chưa hỗ trợ số đơn đang
                    giao hoặc xếp hạng sản phẩm theo kỳ.
                  </p>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
