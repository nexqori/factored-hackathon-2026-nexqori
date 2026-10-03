"""Adapted from Santiago Leyva’s PDF renderer (3d85c57). See docs/consultas-y-documentos.md."""
from io import BytesIO
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from xml.sax.saxutils import escape
import json

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

TEMPLATES = Path(__file__).with_name('document_templates')
DOCUMENT_TYPES = {'statement', 'products_summary', 'requests_summary'}

def require(condition, code, message):
    if not condition: raise ValueError(code)

def generar_pdf(packet, *, customer_name, language='es'):
    require(packet['type'] in DOCUMENT_TYPES and language in {'es', 'en', 'pt'}, 'INVALID_DOCUMENT', 'Plantilla o idioma inválido.')
    template = json.loads((TEMPLATES / (packet['type'] + '.json')).read_text(encoding='utf-8'))
    labels = json.loads((TEMPLATES / 'labels.json').read_text(encoding='utf-8'))[language]
    def local_date(value):
        dt=datetime.fromisoformat(value)
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(ZoneInfo('America/Mexico_City'))
    date_format='%m/%d/%Y' if language=='en' else '%d/%m/%Y'
    zone_label={'es':'Horario de Ciudad de México','en':'Mexico City time','pt':'Horário da Cidade do México'}[language]
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('Cell', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#392C27'), wordWrap='CJK'))
    styles.add(ParagraphStyle('SmallNQ', parent=styles['Cell'], fontSize=9, leading=13))
    styles.add(ParagraphStyle('TitleNQ', fontName='Helvetica-Bold', fontSize=23, leading=27, textColor=colors.HexColor('#9A4B32'), spaceAfter=14))
    def p(value, style='Cell'):
        return Paragraph(escape(str(value if value is not None else labels['unavailable'])).replace('\n', '<br/>'), styles[style])
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=(595.28, 841.89), rightMargin=42, leftMargin=42,
        topMargin=104, bottomMargin=65, title=template['title'][language], author='Nexqori')
    def chrome(canvas, document):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor('#9A4B32'))
        canvas.roundRect(42, 774, 32, 32, 8, fill=1, stroke=0)
        canvas.setFillColor(colors.white); canvas.setFont('Helvetica-Bold', 23); canvas.drawString(50, 781, 'n')
        canvas.setFillColor(colors.HexColor('#392C27')); canvas.setFont('Helvetica-Bold', 21); canvas.drawString(85, 783, 'nexqori')
        canvas.setStrokeColor(colors.HexColor('#F2D8C8')); canvas.line(42, 758, 553, 758)
        canvas.setFont('Helvetica', 8); canvas.drawString(42, 35, labels['footer'])
        canvas.drawRightString(553, 35, f"{labels['page']} {document.page}")
        canvas.restoreState()
    fields = packet['fields']
    story = [p(template['title'][language], 'TitleNQ'), p(customer_name, 'SmallNQ'),
             p(labels['generated'] + ': ' + local_date(packet['generated_at']).strftime(date_format+' %H:%M')+' · '+zone_label, 'SmallNQ'), Spacer(1, 10)]
    if packet['type'] == 'statement':
        period = labels['all_history'] if fields.get('all_history') else local_date(fields['start']).strftime(date_format)+' — '+(local_date(fields['end'])-timedelta(days=1)).strftime(date_format)
        story += [p(labels['period'] + ': ' + period, 'SmallNQ'), Spacer(1, 10)]
    story += [p(template['note'][language], 'SmallNQ'), Spacer(1, 18)]
    for section in template['sections']:
        rows = [f['values'] for f in packet['facts'] if f['source_ref'].split(':', 1)[0] == section['table']]
        story += [p(labels[section['table']], 'Heading2'), Spacer(1, 6)]
        if not rows:
            story += [p(labels['empty'], 'SmallNQ'), Spacer(1, 16)]
            continue
        cols = section['columns']
        data = [[p(labels[c]) for c in cols]]
        for row in rows:
            cells = []
            for c in cols:
                value = row.get(c)
                if c in {'type', 'status', 'service'}:
                    value = labels.get(str(value), value)
                elif c in {'occurred_at', 'created_at', 'updated_at'} and value:
                    value = local_date(value).strftime(date_format+'\n%H:%M')
                cells.append(p(value))
            data.append(cells)
        width = 511 / len(cols)
        table = Table(data, colWidths=[511 * w for w in section['widths']] if 'widths' in section else [width] * len(cols), repeatRows=1, hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F2D8C8')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFCF9'), colors.white]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 9), ('LINEBELOW', (0, 0), (-1, -1), .3, colors.HexColor('#F2D8C8'))]))
        story += [table, Spacer(1, 18)]
    doc.build(story, onFirstPage=chrome, onLaterPages=chrome)
    return buf.getvalue()
