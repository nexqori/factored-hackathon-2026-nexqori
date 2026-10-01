import { BookOpen, ShieldCheck } from 'lucide-react';
import { translate, type Language } from './locales';

export type ToolPlan = {
  version: string;
  source: string;
  family: 'query' | 'problem' | 'service' | 'clarification';
  status: 'proposed' | 'needs_clarification' | 'unavailable';
  intent: string | null;
  contract: {id: string; version: string} | null;
  tools: {id: string; kind: 'read' | 'prepare'; titles: Record<Language, string>; reference: string | null; gates: string[]; status: string}[];
  executed_tools: unknown[];
  executed_operations: unknown[];
};

export function ToolPlanPanel({plan, language}: {plan: ToolPlan; language: Language}) {
  const t = (key: Parameters<typeof translate>[1]) => translate(language, key);
  const familyTitle = t(plan.family === 'query' ? 'queryFlow' : plan.family === 'problem' ? 'problemFlow' : plan.family === 'service' ? 'serviceFlow' : 'clarificationFlow');
  return <section className="tool-plan" aria-label={t('toolPlanTitle')} data-tool-family={plan.family}>
    <div className="tool-plan-heading"><h3>{t('toolPlanTitle')}</h3><span>{t(plan.source === 'reference' ? 'toolPlanReference' : 'toolPlanJev')}</span></div>
    <div className="tool-flow-options">
      <div className={plan.family === 'query' ? 'selected' : ''}><BookOpen size={18}/><span>{t('queryFlow')}</span>{plan.family === 'query' && <strong>{t('selectedFlow')}</strong>}</div>
      <div className={plan.family === 'problem' ? 'selected' : ''}><ShieldCheck size={18}/><span>{t('problemFlow')}</span>{plan.family === 'problem' && <strong>{t('selectedFlow')}</strong>}</div>
    </div>
    <p className="tool-path">{plan.source === 'reference' ? t('expectedLabel') : 'Jev'} → <strong>{familyTitle}</strong>{plan.contract && <> → {t('problemProcedure')} v{plan.contract.version}</>}</p>
    {plan.status === 'unavailable' ? <p role="status">{t('toolPlanUnavailable')}</p> : plan.tools.length === 0 ? <p>{t('toolPlanClarify')}</p> : <>
      <ul className="tool-list">{plan.tools.map(item => <li key={item.id} data-tool-id={item.id}>
        <div><strong>{item.titles[language]}</strong><span>{t(item.kind === 'read' ? 'toolRead' : 'toolPrepare')}</span></div>
        <p>{t(item.kind === 'read' ? 'toolAwaitingSession' : 'toolAwaitingConfirmation')}{item.reference && <> · {t(item.reference === 'requestId' ? 'toolRequestRef' : item.reference === 'transactionId' ? 'toolTransactionRef' : 'toolCardRef')}</>}{item.gates.includes('administrator_approval') && <> · {t('toolAdminApproval')}</>}</p>
      </li>)}</ul>
      <p className="small-note">{t('toolPlanBoundary')}</p>
    </>}
  </section>;
}
