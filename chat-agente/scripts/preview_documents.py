"""Genera tres muestras ficticias locales para revisar plantillas; sin DB ni APIs."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nexqori_chat.codigo6_documentos import generar_pdf

out = Path(__file__).resolve().parents[2] / '.local/verification/pdf-templates'
out.mkdir(parents=True, exist_ok=True)
facts = [
    {'source_ref': 'products:VER-01', 'values': {'id':'VER-01', 'type':'account', 'last4':'1234', 'balance_display':'24850.00 MXN'}},
    {'source_ref': 'products:VER-02', 'values': {'id':'VER-02', 'type':'savings', 'last4':'4321', 'balance_display':'1250.00 MXN'}},
    {'source_ref': 'requests:VER-REQ', 'values': {'id':'VER-REQ','service':'accounts','status':'in_review','created_at':'2026-10-01T10:00:00-05:00','updated_at':'2026-10-02T10:00:00-05:00'}},
]
facts += [{'source_ref':f'transactions:VER-{i}', 'values': {'id':f'VER-{i}', 'product_id':'VER-01', 'occurred_at':'2026-09-28T10:30:00-05:00',
    'merchant':f'Comercio de verificación {i}', 'amount_display':'-125.50 MXN','status':'completed'}} for i in range(30)]
for kind in ('statement','products_summary','requests_summary'):
    packet = {'type':kind,'generated_at':'2026-10-02T12:00:00-05:00','fields':{'all_history':True},'facts':facts}
    (out/(kind+'.pdf')).write_bytes(generar_pdf(packet,customer_name='Cliente de verificación - datos ficticios',language='es'))
print('Tres muestras PDF ficticias en .local/verification/pdf-templates')
