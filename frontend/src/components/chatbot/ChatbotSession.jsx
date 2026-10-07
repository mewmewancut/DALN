import { createContext, useCallback, useContext, useState } from "react";

import { useAuth } from "../../auth/AuthContext.jsx";
import ChatbotWidget from "./ChatbotWidget.jsx";
import useChatbot from "./useChatbot.js";

const ChatbotContext = createContext(null);

function ChatbotProvider({ children, sessionKey }) {
  const [activated, setActivated] = useState(false);
  const activate = useCallback(() => setActivated(true), []);
  const chatbot = useChatbot(sessionKey, activated);

  return (
    <ChatbotContext.Provider value={{ ...chatbot, activate }}>
      {children}
      <ChatbotWidget />
    </ChatbotContext.Provider>
  );
}

export default function ChatbotSession({ children }) {
  const { session } = useAuth();
  if (!session || !["ADMIN", "SHOP_OWNER"].includes(session.role)) return children;
  if (session.role === "SHOP_OWNER" && session.shop_id == null) return children;

  return (
    <ChatbotProvider
      key={`${session.token}:${session.role}:${session.shop_id}`}
      sessionKey={session.token}
    >
      {children}
    </ChatbotProvider>
  );
}

export function useChatbotSession() {
  return useContext(ChatbotContext);
}
