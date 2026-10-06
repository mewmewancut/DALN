import { useCallback, useEffect, useRef, useState } from "react";

import client from "../../api/client.js";
import { errorMessage } from "../../api/errorMessage.js";

export default function useChatHistory(sessionKey, enabled = true) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const version = useRef(null);
  const offset = useRef(0);
  const refresh = useCallback(async (more = false) => {
    const current = version.current;
    setLoading(true);
    try {
      const { data } = await client.get("/analytics/chat/conversations", {
        params: { limit: 30, offset: more ? offset.current : 0 },
      });
      if (version.current !== current) return;
      setItems((previous) => (more ? [...previous, ...data] : data));
      offset.current = (more ? offset.current : 0) + data.length;
      setHasMore(data.length === 30);
      setError("");
    } catch (failure) {
      if (version.current === current) setError(errorMessage(failure));
    } finally {
      if (version.current === current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    version.current = Symbol("history-session");
    setItems([]);
    setError("");
    offset.current = 0;
    if (enabled) refresh();
    return () => {
      version.current = Symbol("history-closed");
    };
  }, [sessionKey, enabled, refresh]);
  return { items, error, loading, hasMore, refresh };
}
