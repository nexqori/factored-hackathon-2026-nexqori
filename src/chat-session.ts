export const CHAT_FEEDBACK_DELAY_MS = 5 * 60 * 1000;

export function scheduleChatFeedback(onPrompt: () => void) {
  const timer = setTimeout(onPrompt, CHAT_FEEDBACK_DELAY_MS);

  return () => clearTimeout(timer);
}
