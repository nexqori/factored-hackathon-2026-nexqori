export type VoiceFragment = {
  id: string;
  speaker: 'user' | 'assistant';
  text: string;
  startMs: number | null;
  endMs: number | null;
};

// Use provider timing, not packet arrival order. Keep delta text verbatim.
export function groupVoiceTranscript(fragments: VoiceFragment[]): VoiceFragment[] {
  const ordered = [...fragments].sort((a, b) =>
    a.startMs !== null && b.startMs !== null ? a.startMs - b.startMs : 0);
  const rows: VoiceFragment[] = [];
  for (const fragment of ordered) {
    const last = rows.at(-1);
    const pause = last?.endMs !== null && last?.endMs !== undefined && fragment.startMs !== null
      ? fragment.startMs - last.endMs : 0;
    if (last && last.speaker === fragment.speaker && pause <= 2000) {
      last.text += fragment.text;
      last.endMs = fragment.endMs;
    } else rows.push({...fragment});
  }
  return rows;
}
