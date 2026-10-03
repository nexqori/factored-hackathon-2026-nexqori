"""Render reproducible fictitious samples of Santiago's adapted PDF templates.

Run with .venv-app/Scripts/python.exe scripts/verify-query-pdfs.py.
Files stay in the ignored .local folder; no account or model access is required.
"""
from pathlib import Path
import sys
import json
from io import BytesIO
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.document_renderer import generar_pdf
from pypdf import PdfReader

folder=Path('.local/verification/query-pdfs');folder.mkdir(parents=True,exist_ok=True)
facts=[{'source_ref':'products:verification-account','values':{'id':'verification-account','type':'account','last4':'4821','balance_display':'MXN 12,450.00'}}]
for i in range(45):
    facts.append({'source_ref':f'transactions:verification-{i}','values':{'id':f'TX-VERIFICATION-{i:03d}',
        'product_id':'verification-account','occurred_at':'2026-09-28T18:30:00+00:00',
        'merchant':'Comercio de verificación con nombre largo & <texto literal>' if i%3==0 else 'Servicios del hogar',
        'amount_display':'MXN -1,250.50','status':'completed'}})
    facts.append({'source_ref':f'requests:verification-{i}','values':{'id':f'NQ-VERIFICATION-{i:03d}',
        'service':'payments','status':'in_review','created_at':'2026-09-28T18:30:00+00:00','updated_at':'2026-09-29T18:30:00+00:00'}})
report=[]
for kind,lang in [('statement','es'),('products_summary','en'),('requests_summary','pt')]:
    packet={'type':kind,'generated_at':'2026-10-02T15:00:00+00:00','fields':{'all_history':True},'facts':facts}
    raw=generar_pdf(packet,customer_name='María José Fernández — Verificación',language=lang)
    name=f'{kind}-{lang}.pdf';(folder/name).write_bytes(raw)
    pages=PdfReader(BytesIO(raw)).pages
    text='\n'.join(page.extract_text() for page in pages)
    assert 'María José Fernández' in text
    compact=''.join(text.split())
    if kind=='statement':assert '<textoliteral>' in compact and 'TX-VERIFICATION-044' in compact
    if kind=='requests_summary':assert 'NQ-VERIFICATION-044' in compact
    report.append({'file':name,'pages':len(pages),'bytes':len(raw),'textChecked':True})
(folder/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'folder':str(folder),'documents':report},ensure_ascii=True))
