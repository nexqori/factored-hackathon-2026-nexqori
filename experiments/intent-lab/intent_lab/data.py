from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT.parents[1] / "backend" / "service_catalog.json"
LANGUAGES = ("es", "en", "pt")
FALLBACKS = {
    "needs-clarification": ["Pedir aclaración", "Ask for clarification", "Pedir esclarecimento"],
    "multiple-intents": ["Varias intenciones", "Multiple intents", "Várias intenções"],
    "out-of-scope": ["Fuera de alcance", "Out of scope", "Fora do escopo"],
}
FALLBACK_DESCRIPTIONS = {
    "needs-clarification": ["Solicitud bancaria vaga o sin información suficiente para elegir servicio.", "Vague banking request without enough information to choose a service.", "Pedido bancário vago, sem informação suficiente para escolher um serviço."],
    "multiple-intents": ["Dos o más solicitudes bancarias distintas y activas, no una negada.", "Two or more distinct active banking requests, not a negated request.", "Dois ou mais pedidos bancários distintos e ativos, não um pedido negado."],
    "out-of-scope": ["Tema no bancario o petición no admitida, como revelar secretos o datos ajenos.", "Non-banking or unsupported request, such as revealing secrets or other people's data.", "Assunto não bancário ou pedido não permitido, como revelar segredos ou dados de terceiros."],
}


# This query is a regression discovered in dialogue evaluation, outside the frozen NLP corpus.
LAB_QUERIES = [{"id": "request-status", "copy": {
    "es": {"title": "Consultar el estado de una solicitud", "summary": "Consultar únicamente el seguimiento o estado de un folio o reclamo existente. No revisar de nuevo el importe de un cargo ni diagnosticar un pago."},
    "en": {"title": "Check an existing request", "summary": "Only check the status or progress of an existing reference or complaint. Not a renewed dispute of a charge amount or a payment diagnosis."},
    "pt": {"title": "Consultar uma solicitação existente", "summary": "Consultar apenas o andamento ou status de um protocolo ou reclamação existente. Não revisar novamente o valor de uma cobrança nem diagnosticar um pagamento."},
}}]

LAB_QUERIES.append({'id':'documents','copy':{
    'es':{'title':'Obtener un documento PDF','summary':'Descargar un estado de cuenta informativo, un resumen de productos o seguimiento de solicitudes propios en PDF. No es un reclamo ni un certificado firmado.'},
    'en':{'title':'Get a PDF document','summary':'Download an informational account statement, own product summary or request tracking PDF. This is not a complaint or a signed certificate.'},
    'pt':{'title':'Obter um documento PDF','summary':'Baixar um extrato informativo, resumo de produtos próprios ou acompanhamento de solicitações em PDF. Não é uma reclamação nem um certificado assinado.'},
}})


def taxonomy(*, include_lab_queries=True):
    items = json.loads(CATALOG.read_text(encoding="utf-8"))["items"]
    result = [{"id": item["id"], "copy": item["copy"]} for item in items]
    if include_lab_queries:
        result.extend(LAB_QUERIES)
    for label, titles in FALLBACKS.items():
        result.append({"id": label, "copy": {lang: {"title": titles[i], "summary": FALLBACK_DESCRIPTIONS[label][i]} for i, lang in enumerate(LANGUAGES)}})
    return result


def normalized(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    return re.sub(r"\W+", " ", "".join(c for c in text if not unicodedata.combining(c))).strip()


def corpus():
    source = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    rows = []
    for label, families in source["families"].items():
        for idx, translations in enumerate(families):
            split = ("train", "validation", "test", "test")[idx]
            for lang, text in zip(LANGUAGES, translations, strict=True):
                rows.append({"id": f"{label}-{idx}-{lang}", "family": f"{label}-{idx}", "text": text, "language": lang, "expected": label, "split": split, "source": source["provenance"], "review": "pending", "slice": "challenge" if idx == 3 else "standard"})
    for item in taxonomy(include_lab_queries=False):
        for lang, copy in item["copy"].items():
            rows.append({"id": f"{item['id']}-definition-{lang}", "family": f"{item['id']}-definition", "text": f"{copy['title']}. {copy['summary']}", "language": lang, "expected": item["id"], "split": "train", "source": "catalog_definition", "review": "pending", "slice": "definition"})
    validate(rows)
    return rows


def validate(rows):
    ids, families, texts = set(), {}, {}
    labels = {item["id"] for item in taxonomy()}
    for row in rows:
        if row["id"] in ids or row["expected"] not in labels or row["language"] not in LANGUAGES:
            raise ValueError("Invalid identifier, label or language")
        if row["split"] not in ("train", "validation", "test") or not row["text"].strip():
            raise ValueError("Invalid split or empty text")
        ids.add(row["id"])
        for mapping, key in ((families, row["family"]), (texts, normalized(row["text"]))):
            if key in mapping and mapping[key] != row["split"]:
                raise ValueError("Text or translated family crosses splits")
            mapping[key] = row["split"]


def digest():
    return hashlib.sha256(json.dumps(corpus(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
