import { useEffect, useRef, useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";
import useChatHistory from "./useChatHistory.js";

export default function useChatbot(sessionKey, enabled) {
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
  const history = useChatHistory(sessionKey, enabled && !!config);
  const refreshHistory = history.refresh;
  const [selected, setSelected] = useState(null);
  const [opening, setOpening] = useState(false);
  const [canResume, setCanResume] = useState(true);
  const [hasOlder, setHasOlder] = useState(false);
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
    if (!enabled) return;
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
  }, [sessionKey, reload, enabled]);

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

  return {
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
    reloadConfig: () => setReload((n) => n + 1),
    retryResult: () => {
      setError("");
      setRetry((n) => n + 1);
    },
  };
}
