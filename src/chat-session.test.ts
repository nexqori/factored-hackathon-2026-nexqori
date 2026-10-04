import { afterEach, describe, expect, it, vi } from 'vitest';
import { CHAT_FEEDBACK_DELAY_MS, scheduleChatFeedback } from './chat-session';

describe('chat feedback prompt', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('asks for feedback after five minutes', () => {
    vi.useFakeTimers();
    expect(CHAT_FEEDBACK_DELAY_MS).toBe(15 * 60 * 1000);
    const onPrompt = vi.fn();
    scheduleChatFeedback(onPrompt);

    vi.advanceTimersByTime(CHAT_FEEDBACK_DELAY_MS - 1);
    expect(onPrompt).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onPrompt).toHaveBeenCalledOnce();
  });

  it('cancels the prompt when activity resumes', () => {
    vi.useFakeTimers();
    const onPrompt = vi.fn();
    const cancel = scheduleChatFeedback(onPrompt);
    vi.advanceTimersByTime(CHAT_FEEDBACK_DELAY_MS - 1);

    cancel();
    vi.advanceTimersByTime(1);

    expect(onPrompt).not.toHaveBeenCalled();
  });
});
