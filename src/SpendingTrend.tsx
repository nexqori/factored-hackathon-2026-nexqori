import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from './api';
import { formatDate, formatMoney } from './components';
import type { Locale } from './i18n';
import './spending.css';

export type SpendingInsight = { transactionId: string; classification: 'unusual' | 'comparable' | 'limited' | 'exceptional'; canRecognizeException?:boolean; comparison: {
  recognizedException?:boolean; status: string; reason?: string; basis?: string; currency: string; count?: number; averageMinor?: number;
  minMinor?: number; maxMinor?: number; differencePercent?: string; unusualIncrease: boolean;
  providerNotice?: { status:string; observation?: {priceMinor:number; previousPriceMinor:number|null; currency:string; planName:string; effectiveDate:string; fetchedAt:string; sourceUrl:string} };
  serviceAgreement?: {status:string; monthlyMinor?:number; billAmountMinor:number; differenceMinor?:number; currency:string; validFrom?:string; validUntil?:string; taxesIncluded?:boolean; extrasRequireApproval?:boolean; planName?:string};
  samples: { transactionId: string; amountMinor: number; date: string }[];
} };
export type SpendingPage = { items: SpendingInsight[]; nextOffset: number | null };

export function SpendingTrend({ transactionId, onChanged }: { transactionId: string; onChanged?:()=>void }) {
  const {t, i18n} = useTranslation(); const locale = i18n.language as Locale;
  const [value, setValue] = useState<SpendingInsight | null>(null); const [error, setError] = useState(false);
  const [confirming,setConfirming]=useState(false);const [saving,setSaving]=useState(false);const [saveError,setSaveError]=useState(false);
  useEffect(() => {
    const abort = new AbortController(); setValue(null); setError(false);setConfirming(false);setSaveError(false);
    void api<SpendingInsight>('/movements/'+encodeURIComponent(transactionId)+'/trend','GET',undefined,abort.signal)
      .then(setValue).catch(()=>{if(!abort.signal.aborted)setError(true);});
    return ()=>abort.abort();
  },[transactionId]);
  async function recognize(){
    if(saving)return;setSaving(true);setSaveError(false);
    try{setValue(await api<SpendingInsight>('/movements/'+encodeURIComponent(transactionId)+'/recognize-exception','POST',{confirmed:true}));setConfirming(false);onChanged?.();}
    catch{setSaveError(true);}finally{setSaving(false);}
  }
  const c=value?.comparison;
  return <section className="spending-detail" aria-label={t('spending.title')}>
    <h3>{t('spending.title')}</h3>
    {!c && <p role="status">{t(error?'spending.error':'loading')}</p>}
    {c && <>
      <p className={c.unusualIncrease?'spending-warning':''}>{t(c.recognizedException?'spending.exceptionSaved':c.reason==='bill_amount_mismatch'?'spending.billMismatch':
        c.reason==='partial_payment'?'spending.partial':c.reason==='not_a_charge'?'spending.notCharge':
        c.unusualIncrease?'spending.unusualDetail':c.status==='sufficient'?'spending.comparableDetail':'spending.limitedDetail')}</p>
      {!!c.count && <><dl className="detail-list"><div><dt>{t('spending.average')}</dt><dd>{formatMoney(c.averageMinor!,locale,c.currency)}</dd></div>
        <div><dt>{t('spending.range')}</dt><dd>{formatMoney(c.minMinor!,locale,c.currency)} – {formatMoney(c.maxMinor!,locale,c.currency)}</dd></div>
        <div><dt>{t('spending.change')}</dt><dd>{Number(c.differencePercent)>0?'+':''}{new Intl.NumberFormat(locale,{maximumFractionDigits:1}).format(Number(c.differencePercent))} %</dd></div></dl>
        <p className="muted">{t(c.basis==='bill-reference'?'spending.billBasis':'spending.merchantBasis',{count:c.count})}</p>
        <details><summary>{t('spending.history',{count:c.count})}</summary><ul className="spending-history">{c.samples.map(s=><li key={s.transactionId}><span>{formatDate(s.date,locale)}</span><strong>{formatMoney(s.amountMinor,locale,c.currency)}</strong></li>)}</ul></details></>}
      <p className="muted">{t('spending.rule')}</p>
      {c.recognizedException&&<p className="spending-recognized" role="status">{t('spending.excluded')}</p>}
      {value?.canRecognizeException&&<div className="spending-recognition">
        {confirming?<><p>{t('spending.exceptionConfirm')}</p><div className="service-form-actions"><button className="button primary" disabled={saving} onClick={()=>void recognize()}>{t(saving?'loading':'spending.confirmException')}</button><button className="button secondary" disabled={saving} onClick={()=>setConfirming(false)}>{t('cancel')}</button></div></>
          :<button className="button secondary" onClick={()=>setConfirming(true)}>{t('spending.recognizeException')}</button>}
        {saveError&&<p role="alert">{t('error.generic')}</p>}
      </div>}
      {c.serviceAgreement&&<div className="spending-source spending-agreement"><h4>{t('spending.conditionsTitle')}</h4>
        {c.serviceAgreement.monthlyMinor===undefined?<p>{t('spending.conditionsMissing')}</p>:<>
          <p>{c.serviceAgreement.planName}</p>
          <dl className="detail-list">
            <div><dt>{t('spending.conditionsBase')}</dt><dd>{formatMoney(c.serviceAgreement.monthlyMinor,locale,c.serviceAgreement.currency)}</dd></div>
            <div><dt>{t('spending.conditionsBill')}</dt><dd>{formatMoney(c.serviceAgreement.billAmountMinor,locale,c.serviceAgreement.currency)}</dd></div>
            <div><dt>{t('spending.conditionsDifference')}</dt><dd>{formatMoney(Math.max(0,c.serviceAgreement.differenceMinor||0),locale,c.serviceAgreement.currency)}</dd></div>
          </dl>
          <p>{t('spending.conditionsValidity',{from:c.serviceAgreement.validFrom,until:c.serviceAgreement.validUntil})}</p>
          {c.serviceAgreement.taxesIncluded&&<p>{t('spending.conditionsTaxes')}</p>}
          {c.serviceAgreement.extrasRequireApproval&&<p>{t('spending.conditionsExtras')}</p>}
          <p>{t('spending.conditionsLimit')}</p>
        </>}
      </div>}
      {c.providerNotice?.status==='candidate'&&c.providerNotice.observation&&<div className="spending-source"><h4>{t('spending.providerTitle')}</h4>
        <p>{t('spending.providerPrice',{plan:c.providerNotice.observation.planName,price:formatMoney(c.providerNotice.observation.priceMinor,locale,c.providerNotice.observation.currency),date:c.providerNotice.observation.effectiveDate})}</p>
        {c.providerNotice.observation.previousPriceMinor!==null&&<p>{t('spending.providerBefore',{price:formatMoney(c.providerNotice.observation.previousPriceMinor,locale,c.providerNotice.observation.currency)})}</p>}
        <p>{t('spending.providerLimit')}</p>
        <small>{t('spending.providerChecked',{date:formatDate(c.providerNotice.observation.fetchedAt,locale)})}</small>
      </div>}
    </>}
  </section>;
}
