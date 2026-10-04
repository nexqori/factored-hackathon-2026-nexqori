// UI reminder utility only. Durable closure is owned by backend/attention.py.
export const CHAT_FEEDBACK_DELAY_MS = 15 * 60 * 1000;

export function scheduleChatFeedback(onPrompt: () => void) {
  const timer = setTimeout(onPrompt, CHAT_FEEDBACK_DELAY_MS);

  return () => clearTimeout(timer);
}
