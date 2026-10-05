import { describe,expect,it } from 'vitest';
import { filterMovements } from './movementFilters';
import type {Transaction} from './types';
import type {SpendingInsight} from './SpendingTrend';

const tx=(id:string,date:string,productId='a',status:Transaction['status']='completed'):Transaction=>({id,date,productId,status,amountMinor:-100,currency:'MXN',merchant:'Teléfono',category:'phone'});
describe('Movement filters',()=>{
  it('combines server classifications with search and status without treating unassessed rows as normal',()=>{
    const rows=[tx('high','2026-10-03T12:00:00Z'),tx('normal','2026-10-02T12:00:00Z'),tx('unassessed','2026-10-01T12:00:00Z')];
    const insights=[{transactionId:'high',classification:'unusual'},{transactionId:'normal',classification:'comparable'}] as SpendingInsight[];
    expect(filterMovements(rows,new URLSearchParams('trend=unusual&q=Teléfono&status=completed'),insights)).toEqual([rows[0]]);
    expect(filterMovements(rows,new URLSearchParams('trend=comparable'),insights)).toEqual([rows[1]]);
    expect(filterMovements(rows,new URLSearchParams('trend=limited'),insights)).toEqual([]);
    expect(filterMovements(rows,new URLSearchParams('trend=unusual'),[])).toEqual([]);
    expect(filterMovements(rows,new URLSearchParams('trend=all'),[])).toEqual(rows);
  });
  it('uses the same inclusive Mexico City dates as the PDF, together with account and status',()=>{
    const rows=[tx('before','2026-09-01T05:59:59Z'),tx('start','2026-09-01T06:00:00Z'),tx('end','2026-10-01T05:59:59Z'),tx('after','2026-10-01T06:00:00Z'),tx('other','2026-09-04T12:00:00Z','b'),tx('pending','2026-09-04T12:00:00Z','a','pending')];
    expect(filterMovements(rows,new URLSearchParams('start=2026-09-01&end=2026-09-30&product=a&status=completed')).map(r=>r.id)).toEqual(['start','end']);
    expect(filterMovements(rows,new URLSearchParams('q=pending'))).toEqual([rows[5]]);
    expect(filterMovements(rows,new URLSearchParams('start=2026-02-30'))).toEqual([]);
  });
});
