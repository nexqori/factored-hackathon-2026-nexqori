import { describe, expect, it } from 'vitest';
import { chatSurveyScores, chooseChatSurvey } from './chat-survey';

describe('chat survey selection and score ranges', () => {
  it('randomly selects each supported metric', () => {
    expect(chooseChatSurvey(() => 0)).toBe('nps');
    expect(chooseChatSurvey(() => 0.4)).toBe('csat');
    expect(chooseChatSurvey(() => 0.9)).toBe('ces');
  });

  it('provides the score range appropriate to each metric', () => {
    expect(chatSurveyScores('nps')).toEqual(Array.from({ length: 11 }, (_, index) => index));
    expect(chatSurveyScores('csat')).toEqual([1, 2, 3, 4, 5]);
    expect(chatSurveyScores('ces')).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });
});
