import type { Transaction } from './types';
import { validDate } from './navigation';
import type { SpendingInsight } from './SpendingTrend';

export function bankDate(value:string){return new Intl.DateTimeFormat('en-CA',{timeZone:'America/Mexico_City',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));}
export function filterMovements(rows:Transaction[],params:URLSearchParams,insights:SpendingInsight[]=[]){
  const start=params.get('start'),end=params.get('end'),product=params.get('product'),status=params.get('status'),search=(params.get('q')||'').toLocaleLowerCase();
  if(start&&!validDate(start)||end&&!validDate(end)||start&&end&&start>end)return [];
  const trend=params.get('trend');const matches=new Set(insights.filter(i=>i.classification===trend).map(i=>i.transactionId));
  const transaction=params.get('transaction'),category=params.get('category'),amount=params.get('amountMinor');
  return rows.filter(row=>(!transaction||row.id===transaction)&&(!category||row.category===category)&&(amount===null||row.amountMinor===-Number(amount))&&(!trend||trend==='all'||matches.has(row.id))&&(!product||row.productId===product)&&(!status||status==='all'||row.status===status)&&(!start||bankDate(row.date)>=start)&&(!end||bankDate(row.date)<=end)&&(row.merchant+' '+row.id).toLocaleLowerCase().includes(search));
}
