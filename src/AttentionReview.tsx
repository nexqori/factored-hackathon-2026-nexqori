import { useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api, ApiError } from './api';
import { chatSurveyScores } from './chat-survey';
import type { Locale } from './i18n';
import './attention-review.css';

type Scores = { nps: number | null; csat: number | null; ces: number | null; comment: string; locale?: Locale };
type Review = { id: string; status: 'scheduled' | 'closed' | 'reopened'; summary: string; dueAt: number; closedAt: number | null; answers: Partial<Scores>; revision: number; submittedAt: number | null; snapshots: { processedAt: number; feedback: string; missing: string[] }[] };
type Result = { review: Review | null; pending: boolean; canResolve: boolean; serverTime: number };
type Props = { source: 'requests' | 'conversations'; identity: string; admin?: boolean; onChange?: () => void };
const blank: Scores = { nps: null, csat: null, ces: null, comment: '' };

export function AttentionReview(props: Props) {
  return <ReviewPanel key={`${props.admin}:${props.source}:${props.identity}`} {...props} />;
}

function ReviewPanel({ source, identity, admin = false, onChange }: Props) {
  const { t, i18n } = useTranslation(); const id = useId();
  const [data, setData] = useState<Result | null>(null);
  const [answers, setAnswers] = useState<Scores>(blank);
  const [summary, setSummary] = useState(''); const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const [form, setForm] = useState(false); const [dirty, setDirty] = useState(false); const [saved, setSaved] = useState(false);
  const dirtyRef = useRef(false); dirtyRef.current = dirty;
  const path = `${admin ? '/admin' : ''}/attention/${source}/${encodeURIComponent(identity)}`;
  const control = useRef<AbortController | null>(null);
  function accept(value: Result) { setData(value); setAnswers({ ...blank, ...value.review?.answers }); setDirty(false); }
  useEffect(() => {
    const c = new AbortController(); control.current = c;
    void api<Result>(path, 'GET', undefined, c.signal).then(accept).catch(e => { if (!c.signal.aborted) setError(e instanceof ApiError ? e.code : 'generic'); });
    return () => c.abort();
  }, [path]);
  useEffect(() => {
    if (data?.review?.status !== 'scheduled') return;
    const c = new AbortController();
    const timer = setInterval(() => { void api<Result>(path, 'GET', undefined, c.signal).then(value => {
      if (!dirtyRef.current) accept(value); else setData(value);
    }).catch(() => {}); }, 30000);
    return () => { clearInterval(timer); c.abort(); };
  }, [path, data?.review?.status]);
  async function act(action: string, body: unknown, method = 'POST') {
    setBusy(true); setError(''); setSaved(false);
    try {
      const value = await api<Result>(path + action, method, body, control.current?.signal);
      accept(value); onChange?.(); if (action === '/feedback') setSaved(true);
    } catch (e) { if (!control.current?.signal.aborted) setError(e instanceof ApiError ? e.code : 'generic'); }
    finally { if (!control.current?.signal.aborted) setBusy(false); }
  }
  const review = data?.review;
  const time = (n: number) => new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(n * 1000));
  const update = (change: Partial<Scores>) => { setAnswers(old => ({ ...old, ...change })); setDirty(true); setSaved(false); };
  return <section className="attention-review" aria-labelledby={id + '-title'} data-attention-ready={!!data}>
    <h3 id={id + '-title'}>{t('attention.title')}</h3>
    {error && <p role="alert" className="error-text">{t('error.' + error, { defaultValue: t('error.generic') })}</p>}
    {!data && !error && <p role="status">{t('loading')}</p>}
    {data && <>
      {review && <><p className="attention-status"><strong>{t('attention.' + review.status)}</strong>{review.status === 'scheduled' && <span>{t('attention.due', { date: time(review.dueAt) })}</span>}{review.status === 'closed' && review.closedAt && <span>{time(review.closedAt)}</span>}</p><p className="trace-text">{review.summary}</p>
        {review.snapshots.length > 0 && <p className="muted">{t('attention.snapshot.' + review.snapshots.at(-1)!.feedback)}</p>}
      </>}
      {(!review || review.status === 'reopened') && <>
        <p>{t(data.pending ? 'attention.pending' : admin ? 'attention.adminHelp' : source === 'requests' ? 'attention.waitAdmin' : 'attention.queryHelp')}</p>
        {data.canResolve && <div className="form-stack">
          {admin && <label>{t('attention.summary')}<textarea maxLength={1000} value={summary} onChange={e => setSummary(e.target.value)} disabled={busy}/></label>}
          <label className="confirmation"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} disabled={busy}/>{t('attention.confirm')}</label>
          <button type="button" className="button primary" disabled={busy || !confirmed || (admin && summary.trim().length < 10)} onClick={() => void act('/resolve', { confirmed: true, noPending: true, summary: admin ? summary : t('attention.querySummary') })}>{t('attention.resolve')}</button>
        </div>}
      </>}
      {review && <>
        <p className="muted">{t('attention.scope')}</p>
        {!admin && <div className="survey-actions"><button type="button" className="button secondary" onClick={() => setForm(!form)} aria-expanded={form} disabled={busy}>{t(review.submittedAt ? 'attention.viewAnswers' : 'attention.answer')}</button>
          {review.status !== 'reopened' && <button type="button" className="text-link" disabled={busy} onClick={() => void act('/reopen', { confirmed: true })}>{t('attention.needHelp')}</button>}
        </div>}
        {admin ? <dl className="detail-list">{(['nps', 'csat', 'ces'] as const).map(metric => <div key={metric}><dt>{t(metric + 'Label')}</dt><dd>{review.answers[metric] ?? t('attention.unanswered')}</dd></div>)}<div><dt>{t('attention.comment')}</dt><dd className="trace-text">{review.answers.comment || t('attention.unanswered')}</dd></div><div><dt>{t('status')}</dt><dd>{t(review.submittedAt ? 'attention.submitted' : 'attention.draft')}</dd></div></dl> : form && <div className="chat-survey">
          <p>{t('attention.formHelp')}</p>
          {(['nps', 'csat', 'ces'] as const).map(metric => <fieldset key={metric} disabled={busy || !!review.submittedAt}>
            <legend id={`${id}-${metric}`}>{t(metric === 'nps' ? 'surveyNpsQuestion' : metric === 'csat' ? 'surveyCsatQuestion' : 'surveyCesQuestion')}{metric === 'ces' && ` (${t('attention.optional')})`}</legend>
            <div className={'survey-scale survey-scale-' + metric} role="radiogroup" aria-labelledby={`${id}-${metric}`}>
              {chatSurveyScores(metric).map(score => <label className="survey-score" key={score}>
                <input type="radio" name={`${id}-${metric}`} value={score} checked={answers[metric] === score} onChange={() => update({ [metric]: score })}/>
                <span aria-hidden="true">{metric === 'csat' ? ['😡', '😕', '😐', '🙂', '😄'][score - 1] : score}</span><small>{metric === 'csat' ? t('surveyCsat' + score) : score}</small>
              </label>)}
            </div>
            {metric !== 'csat' && <div className="survey-endpoints"><span>{t(metric === 'nps' ? 'surveyNpsLow' : 'surveyCesLow')}</span><span>{t(metric === 'nps' ? 'surveyNpsHigh' : 'surveyCesHigh')}</span></div>}
          </fieldset>)}
          <label>{t('attention.comment')}<textarea maxLength={1000} value={answers.comment} disabled={busy || !!review.submittedAt} onChange={e => update({ comment: e.target.value })}/></label>
          {!review.submittedAt && <div className="survey-actions"><button type="button" className="button secondary" disabled={busy || !dirty} onClick={() => void act('/feedback', { ...answers, locale: i18n.language, revision: review.revision, submit: false }, 'PUT')}>{t('attention.saveDraft')}</button><button type="button" className="button primary" disabled={busy || answers.nps === null || answers.csat === null} onClick={() => void act('/feedback', { ...answers, locale: i18n.language, revision: review.revision, submit: true }, 'PUT')}>{t('submitSurvey')}</button></div>}
          {(saved || review.submittedAt) && <p role="status">{t(review.submittedAt ? 'surveyThanks' : 'attention.saved')}</p>}{dirty && <p className="muted">{t('attention.unsaved')}</p>}
        </div>}
      </>}
    </>}
  </section>;
}
