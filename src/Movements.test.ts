import { describe,expect,it } from 'vitest';
import { filterMovements } from './movementFilters';
import type {Transaction} from './types';

const tx=(id:string,date:string,productId='a',status:Transaction['status']='completed'):Transaction=>({id,date,productId,status,amountMinor:-100,currency:'MXN',merchant:'Teléfono',category:'phone'});
describe('Movement filters',()=>{
  it('uses the same inclusive Mexico City dates as the PDF, together with account and status',()=>{
    const rows=[tx('before','2026-09-01T05:59:59Z'),tx('start','2026-09-01T06:00:00Z'),tx('end','2026-10-01T05:59:59Z'),tx('after','2026-10-01T06:00:00Z'),tx('other','2026-09-04T12:00:00Z','b'),tx('pending','2026-09-04T12:00:00Z','a','pending')];
    expect(filterMovements(rows,new URLSearchParams('start=2026-09-01&end=2026-09-30&product=a&status=completed')).map(r=>r.id)).toEqual(['start','end']);
    expect(filterMovements(rows,new URLSearchParams('q=pending'))).toEqual([rows[5]]);
    expect(filterMovements(rows,new URLSearchParams('start=2026-02-30'))).toEqual([]);
  });
});
