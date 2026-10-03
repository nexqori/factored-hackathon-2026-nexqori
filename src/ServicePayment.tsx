import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowRight, ReceiptText } from 'lucide-react';
import { api, ApiError } from './api';
import { formatMoney } from './components';
import { parseAmount } from './catalog';
import type { Dashboard, ServiceItem } from './types';
import { localeTags, type Locale } from './i18n';
import './bank-flow.css';

type Bill = { id:string; reference:string; provider:string; period:string; dueDate:string; amountMinor:number; paidMinor:number; outstandingMinor:number; allowPartial:boolean; currency:string; paymentId:string|null; pendingMinor?:number; pendingPaymentId?:string|null; paymentStatus?:'unpaid'|'partial'|'pending'|'completed'; processingOptions?:('immediate'|'pending')[] };

export function ServicePayment({ item, data, saved }: { item:ServiceItem; data:Dashboard; saved:(id:string)=>Promise<void> }) {
  const {t,i18n}=useTranslation(); const locale=i18n.language as Locale; const navigate=useNavigate();
  const hintId=useId(); const amountErrorId=useId(); const resultHeading=useRef<HTMLHeadingElement>(null);
  const [reference,setReference]=useState(''); const [references,setReferences]=useState<string[]>([]);
  const [bills,setBills]=useState<Bill[]|null>(null); const [billId,setBillId]=useState('');
  const accounts=data.products.filter(p=>p.type!=='card'&&p.currency==='MXN');
  const [accountId,setAccountId]=useState(accounts[0]?.id||''); const [mode,setMode]=useState<'total'|'partial'>('total'); const [amount,setAmount]=useState('');
  const [processingMode,setProcessingMode]=useState<'immediate'|'pending'>('immediate');
  const [review,setReview]=useState(false); const [confirmed,setConfirmed]=useState(false); const [busy,setBusy]=useState(false); const locked=useRef(false);
  const [error,setError]=useState(''); const attempt=useRef<{signature:string;key:string}|null>(null);
  useEffect(()=>{ const c=new AbortController(); void api<{references:{serviceId:string;reference:string}[]}>('/service-bills/references','GET',undefined,c.signal).then(r=>setReferences(r.references.filter(v=>v.serviceId===item.id).map(v=>v.reference))).catch(()=>{}); return()=>c.abort(); },[item.id]);
  const bill=bills?.find(b=>b.id===billId); const account=accounts.find(p=>p.id===accountId);
  const canDefer=item.id==='phone-bill'&&bill?.processingOptions?.includes('pending');
  const deferred=!!canDefer&&processingMode==='pending';
  const pendingMinor=bill?.pendingMinor||0; const inProcessing=pendingMinor>0&&bill?.outstandingMinor===0;
  const paying=mode==='total'?bill?.outstandingMinor:parseAmount(amount);
  const invalidAmount=mode==='partial'&&!!amount&&(!paying||!!bill&&paying>bill.outstandingMinor);
  const insufficient=!!account&&!!paying&&paying>(account.balanceMinor||0);
  const ready=!!bill&&!!account&&!!paying&&paying<=bill.outstandingMinor&&!insufficient;
  const needsRefresh=error==='error.bill_changed'||error==='error.bill_already_paid'||error==='error.bill_in_processing';
  useEffect(()=>{if(billId)resultHeading.current?.focus();},[billId,review]);
  function fail(e:unknown){setError('error.'+(e instanceof ApiError?e.code:'generic'));}
  async function lookup(value=reference){
    if(locked.current)return; locked.current=true;setBusy(true);setError('');setReview(false);setConfirmed(false);setBills(null);setBillId('');setReference(value);setMode('total');setAmount('');setProcessingMode('immediate');
    try {const r=await api<{bills:Bill[]}>('/service-bills/lookup','POST',{serviceId:item.id,reference:value});setBills(r.bills);setBillId(r.bills.find(b=>b.outstandingMinor>0)?.id||r.bills[0]?.id||'');}
    catch(e){fail(e);} finally{locked.current=false;setBusy(false);}
  }
  function prepare(e:FormEvent){e.preventDefault();setError('');if(!ready){setError(insufficient?'error.insufficient_funds':'error.payment_exceeds_bill');return;}setReview(true);setConfirmed(false);}
  async function pay(e:FormEvent){
    e.preventDefault();if(!bill||!confirmed||!ready||needsRefresh||locked.current)return;locked.current=true;setBusy(true);setError('');
    const body={accountId,confirmed:true,mode,expectedOutstandingMinor:bill.outstandingMinor,...(mode==='partial'?{amountMinor:paying}:{}),...(deferred?{processingMode:'pending'}:{})};
    const signature=JSON.stringify({billId:bill.id,...body});if(attempt.current?.signature!==signature)attempt.current={signature,key:crypto.randomUUID()};
    try {const r=await api<{id:string}>('/service-bills/'+encodeURIComponent(bill.id)+'/pay','POST',{...body,requestKey:attempt.current.key});navigate('/payments/'+r.id);void saved(r.id).catch(()=>{});}
    catch(e){fail(e);}finally{locked.current=false;setBusy(false);}
  }
  return <div className="service-workspace"><Link className="text-link" to="/services/payments">{t('allServices')}</Link><div className="service-page-header"><span className="round-icon"><ReceiptText size={28}/></span><div><p className="eyebrow">{item.provider}</p><h1>{item.title}</h1><p>{t('bills.intro')}</p></div></div>
    <section className="panel phone-bill" aria-busy={busy}>
      {!review&&<form className="form-stack bill-lookup" onSubmit={e=>{e.preventDefault();void lookup();}}><label>{t('catalogReference_'+item.referenceKind)}<input value={reference} minLength={3} maxLength={64} required disabled={busy} inputMode={item.referenceKind==='phone'?'tel':'text'} autoComplete="off" spellCheck={false} aria-describedby={hintId} onChange={e=>{setReference(e.target.value);setBills(null);setBillId('');setError('');}}/></label><p className="muted" id={hintId}>{t('bills.lookupHint')}</p><button className="button primary" disabled={busy||reference.trim().length<3}>{t(busy?'loading':'bills.lookup')}</button>{references.length>0&&<div className="saved-references"><p>{t('bills.saved')}</p>{references.map(r=><button type="button" className="button secondary" key={r} disabled={busy} onClick={()=>{void lookup(r);}}>{r}</button>)}</div>}</form>}
      {bills?.length===0&&<p role="status">{t('bills.empty')}</p>}
      {bill&&<div className="bill-result"><h2 ref={resultHeading} tabIndex={-1}>{t(review?'pay.review':'pay.bill')}</h2>{!review&&bills!.length>1&&<label>{t('pay.bill')}<select value={billId} disabled={busy} onChange={e=>{setBillId(e.target.value);setMode('total');setAmount('');setProcessingMode('immediate');setError('');}}>{bills!.map(b=><option key={b.id} value={b.id}>{b.period} · {t(b.paymentStatus==='pending'?'pay.pendingTitle':b.outstandingMinor===0?'pay.paid':'pay.due')}</option>)}</select></label>}
        <div className="bill-total"><span>{t(inProcessing?'pay.pendingTitle':bill.outstandingMinor===0?'pay.paid':'bills.outstanding')}</span><strong>{formatMoney(inProcessing?pendingMinor:bill.outstandingMinor===0?bill.amountMinor:bill.outstandingMinor,locale)}</strong></div>
        <dl className="detail-list"><div><dt>{t('catalogReference_'+item.referenceKind)}</dt><dd>{bill.reference}</dd></div><div><dt>{t('pay.period')}</dt><dd>{bill.period}</dd></div><div><dt>{t('pay.dueDate')}</dt><dd>{new Intl.DateTimeFormat(localeTags[locale],{dateStyle:'medium',timeZone:'UTC'}).format(new Date(bill.dueDate+'T12:00:00Z'))}</dd></div><div><dt>{t('bills.original')}</dt><dd>{formatMoney(bill.amountMinor,locale,bill.currency)}</dd></div>{bill.paidMinor>0&&<div><dt>{t('bills.paidAmount')}</dt><dd>{formatMoney(bill.paidMinor,locale,bill.currency)}</dd></div>}</dl>
        {pendingMinor>0&&<div className="bill-pending-note"><p>{t('pay.pendingAmount',{amount:formatMoney(pendingMinor,locale,bill.currency)})}</p><p className="muted">{t('pay.pendingBillHint')}</p>{bill.pendingPaymentId&&bill.outstandingMinor>0&&<Link className="text-link" to={'/payments/'+bill.pendingPaymentId}>{t('pay.pendingReceipt')}</Link>}</div>}
        {bill.paymentId?<Link className="button primary" to={'/payments/'+(inProcessing&&bill.pendingPaymentId?bill.pendingPaymentId:bill.paymentId)}>{t(inProcessing?'pay.pendingReceipt':'pay.receipt')}</Link>:!review?<form className="form-stack" onSubmit={prepare}>
          <label>{t('catalogSourceAccount')}<select value={accountId} onChange={e=>setAccountId(e.target.value)} required disabled={busy}>{accounts.map(p=><option key={p.id} value={p.id}>{t(p.type)} · •••• {p.last4} · {formatMoney(p.balanceMinor||0,locale)}</option>)}</select></label>
          {!accounts.length&&<p role="status">{t('noProducts')}</p>}
          {canDefer&&<fieldset className="payment-mode payment-processing" disabled={busy}><legend>{t('pay.processing')}</legend><label><input type="radio" name="processing-mode" checked={processingMode==='immediate'} onChange={()=>setProcessingMode('immediate')}/>{t('pay.immediate')}</label><label><input type="radio" name="processing-mode" checked={processingMode==='pending'} onChange={()=>setProcessingMode('pending')}/>{t('pay.deferred')}</label>{deferred&&<p className="muted">{t('pay.deferredHint')}</p>}</fieldset>}
          <fieldset className="payment-mode" disabled={busy}><legend>{t('bills.howMuch')}</legend><label><input type="radio" name="pay-mode" value="total" checked={mode==='total'} onChange={()=>setMode('total')}/>{t('bills.total')}</label>{bill.allowPartial&&<label><input type="radio" name="pay-mode" value="partial" checked={mode==='partial'} onChange={()=>setMode('partial')}/>{t('bills.partial')}</label>}</fieldset>
          {mode==='partial'&&<label>{t('bills.partialAmount')}<input required inputMode="decimal" value={amount} disabled={busy} aria-invalid={!!invalidAmount} aria-describedby={invalidAmount?amountErrorId:undefined} onChange={e=>setAmount(e.target.value)} maxLength={14}/></label>}
          {invalidAmount&&<p className="error-text" id={amountErrorId}>{t('error.payment_exceeds_bill')}</p>}{insufficient&&<p className="error-text" role="status">{t('error.insufficient_funds')}</p>}
          <p className="muted">{t(bill.allowPartial?'bills.partialHint':'bills.totalOnly')}</p><button className="button primary" disabled={busy||!ready}>{t('pay.review')}<ArrowRight size={18}/></button>
        </form>:<form className="form-stack" onSubmit={pay}><div className="bill-total review-total"><span>{t('bills.toPay')}</span><strong>{formatMoney(paying||0,locale,bill.currency)}</strong></div><p>{t('pay.debitFrom',{account:account?.last4})}</p>{deferred?<p className="bill-pending-note">{t('pay.deferredHint')}</p>:<p>{t('bills.after',{amount:formatMoney(bill.outstandingMinor-(paying||0),locale,bill.currency)})}</p>}<label className="checkbox-label"><input type="checkbox" checked={confirmed} disabled={busy||needsRefresh} onChange={e=>setConfirmed(e.target.checked)}/>{t(deferred?'pay.deferredConfirmCheck':'pay.confirmCheck')}</label><div className="service-form-actions"><button className="button secondary" type="button" disabled={busy} onClick={()=>{setReview(false);setConfirmed(false);}}>{t('catalogEdit')}</button><button className="button primary" disabled={!confirmed||busy||needsRefresh}>{t(busy?'loading':deferred?'pay.deferredConfirm':'pay.confirm')}</button></div></form>}
      </div>}{error&&<div className="bank-form-error"><p className="error-text" role="alert">{t(error)}</p>{needsRefresh&&<button className="button secondary" type="button" disabled={busy} onClick={()=>{void lookup();}}>{t('bills.lookup')}</button>}</div>}
    </section>
  </div>;
}
