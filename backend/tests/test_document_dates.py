from io import BytesIO
import pytest
from pypdf import PdfReader
from backend.document_renderer import generar_pdf

@pytest.mark.parametrize('locale,period,day',[('es','01/09/2026 — 30/09/2026','30/09/2026'),('en','09/01/2026 — 09/30/2026','09/30/2026'),('pt','01/09/2026 — 30/09/2026','30/09/2026')])
def test_pdf_displays_customer_inclusive_period_and_local_transaction_date(locale,period,day):
    packet={'type':'statement','generated_at':'2026-10-03T16:00:00+00:00','fields':{'start':'2026-09-01T06:00:00+00:00','end':'2026-10-01T06:00:00+00:00'},'facts':[{'source_ref':'transactions:date-check','values':{'id':'date-check','product_id':'own','occurred_at':'2026-10-01T05:59:00+00:00','merchant':'Servicio','amount_display':'MXN -10.00','status':'completed'}}]}
    pdf=generar_pdf(packet,customer_name='Fecha de verificación',language=locale)
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert period in text and day in text and '23:59' in text
    assert '+00:00' not in text and 'exclusive' not in text and 'exclusivo' not in text
