export const CHAT_SURVEY_METRICS = ['nps', 'csat', 'ces'] as const;
export type ChatSurveyMetric = typeof CHAT_SURVEY_METRICS[number];

export function chooseChatSurvey(random = Math.random): ChatSurveyMetric {
  const index = Math.min(CHAT_SURVEY_METRICS.length - 1, Math.floor(Math.max(0, random()) * CHAT_SURVEY_METRICS.length));
  return CHAT_SURVEY_METRICS[index];
}

export function chatSurveyScores(metric: ChatSurveyMetric): number[] {
  const maximum = metric === 'nps' ? 10 : metric === 'csat' ? 5 : 7;
  return Array.from({ length: maximum - (metric === 'nps' ? 0 : 1) + 1 }, (_, index) => index + (metric === 'nps' ? 0 : 1));
}
