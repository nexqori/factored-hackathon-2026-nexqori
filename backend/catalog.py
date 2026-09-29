"""Curated service definitions; search never executes an operation."""
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name("service_catalog.json").read_text(encoding="utf-8"))
SERVICES = {item["id"]: item for item in CATALOG["items"]}
CATEGORIES = tuple(dict.fromkeys(item["category"] for item in SERVICES.values()))
STOP_WORDS = set("quiero quisiera necesito como para puedo mi mis una uno con del los las por que pagar pago factura servicio servicios consultar consulta ver revisar necesito please want would like need how can could the my a an to of for with pay bill service services check about eu quero preciso como para meu minha uma um com dos das por que pagar pagamento conta fatura serviço serviços consultar ver revisar".split())
STOP_WORDS.update({"el", "la", "lo", "de", "un", "do", "da", "os", "as", "me", "servico", "servicos"})
STOP_WORDS.update({"busca", "buscar", "buscame", "encuentra", "donde", "hacer", "gustaria", "find", "search", "where", "please", "onde", "procurar", "procure", "gostaria", "pagos", "payments", "bills", "pagamentos"})


def normalize(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))


def search_services(query="", category=None, locale="es"):
    query = normalize(query).strip()
    tokens = [w for w in re.findall(r"[a-z0-9]+", query) if len(w) > 1 and w not in STOP_WORDS]
    results = []
    for item in SERVICES.values():
        if category and item["category"] != category:
            continue
        if not tokens and re.search(r"\b(pagar|pago|pagos|pay|payment|payments|bill|bills|pagamento|pagamentos)\b",query) and item["category"]!="payments":
            continue
        content = normalize(" ".join([item.get("provider") or "", *[copy["title"]+" "+copy["keywords"] for copy in item["copy"].values()]]))
        words = set(re.findall(r"[a-z0-9]+", content))
        matches = sum(1 if token in words else 0.8 if len(token) >= 5 and any(SequenceMatcher(None, token, word).ratio() >= 0.86 for word in words) else 0 for token in tokens)
        if query and tokens and matches < max(1, len(tokens) * 0.6):
            continue
        # Exact provider/title takes precedence; ordering otherwise follows the curated registry.
        exact = bool(query and (query == normalize(item["copy"][locale]["title"]) or query == normalize(item.get("provider") or "")))
        results.append((matches + (5 if exact else 0), item))
    return [item for _, item in sorted(results, key=lambda row: -row[0])]


def service_view(item, locale):
    return {**{key: item[key] for key in ("id", "category", "kind", "icon", "provider", "referenceKind", "target", "reason")},
            "title": item["copy"][locale]["title"], "summary": item["copy"][locale]["summary"]}
