import { useEffect, useRef } from "react";

import { useChatbotSession } from "./ChatbotSession.jsx";
import ChatHistory from "./ChatHistory.jsx";
import ChatResult from "./ChatResult.jsx";
import "./chatbot.css";

const SUGGESTIONS = [
  "Doanh thu tháng này là bao nhiêu?",
  "Sản phẩm nào bán chạy nhất?",
  "Những sản phẩm nào đang có tồn kho thấp?",
  "Tỷ lệ hủy đơn là bao nhiêu?",
];

export default function ChatbotWorkspace({ compact = false }) {
  const {
    activate,
    config,
    question,
    setQuestion,
    messages,
    conversationToken,
    pending,
    sending,
    error,
    paused,
    history,
    selected,
    opening,
    canResume,
    hasOlder,
    openHistory,
    send,
    reset,
    reloadConfig,
    retryResult,
  } = useChatbotSession();
  const bottom = useRef(null);
  useEffect(() => {
    activate();
  }, [activate]);
  useEffect(() => {
    if (messages.length || sending)
      bottom.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }, [messages, sending]);
  const historyPanel = (
    <ChatHistory
      history={history}
      selected={selected}
      busy={sending || !!pending || opening}
      onSelect={openHistory}
      onDeleted={(id) => {
        if (selected === id) reset();
      }}
    />
  );

  return (
    <section className="genie-chat">
      <div className="genie-workspace">
        {compact ? (
          <details className="genie-compact-history">
            <summary>Lịch sử trò chuyện</summary>
            {historyPanel}
          </details>
        ) : (
          historyPanel
        )}
        <div className="genie-main">
          <div className="genie-message-area">
            <div className="page-heading">
              <div>{compact ? <h2>Trợ lý dữ liệu</h2> : <h1>Chatbot Genie</h1>}</div>
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
                Cấu hình chatbot đã thay đổi. Bạn vẫn xem được lịch sử; hãy tạo cuộc trò chuyện mới
                để hỏi tiếp.
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
              <button type="button" onClick={reloadConfig}>
                Tải lại
              </button>
            )}
            {pending && paused && (
              <button type="button" onClick={retryResult}>
                Kiểm tra lại kết quả
              </button>
            )}
            {(config?.available || messages.length > 0) && (
              <>
                {!messages.length && (
                  <div className="genie-welcome">
                    <h2>Bạn muốn tìm hiểu điều gì?</h2>
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
              </>
            )}
            {compact && config?.available && (
              <p className="genie-note">
                Kết quả dùng dữ liệu tại lần cập nhật gần nhất. Xếp hạng sản phẩm tính trên toàn
                thời gian.
              </p>
            )}
          </div>
          {config?.available && (
            <>
              <form onSubmit={send} className="genie-form">
                <label>
                  Câu hỏi
                  <textarea
                    value={question}
                    maxLength={2000}
                    rows={compact ? 2 : 3}
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
              {!compact && (
                <p className="genie-note">
                  Kết quả dùng dữ liệu tại lần cập nhật gần nhất. Xếp hạng sản phẩm tính trên toàn
                  thời gian.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
