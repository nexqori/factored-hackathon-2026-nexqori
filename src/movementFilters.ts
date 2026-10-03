import type { Transaction } from './types';
import { validDate } from './navigation';

export function bankDate(value:string){return new Intl.DateTimeFormat('en-CA',{timeZone:'America/Mexico_City',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));}
export function filterMovements(rows:Transaction[],params:URLSearchParams){
  const start=params.get('start'),end=params.get('end'),product=params.get('product'),status=params.get('status'),search=(params.get('q')||'').toLocaleLowerCase();
  if(start&&!validDate(start)||end&&!validDate(end)||start&&end&&start>end)return [];
  return rows.filter(row=>(!product||row.productId===product)&&(!status||status==='all'||row.status===status)&&(!start||bankDate(row.date)>=start)&&(!end||bankDate(row.date)<=end)&&(row.merchant+' '+row.id).toLocaleLowerCase().includes(search));
}
