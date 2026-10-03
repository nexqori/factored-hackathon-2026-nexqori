"""Printable HTML, with escaped untrusted content and no scripts or remote assets."""
import html
import json
from datetime import datetime
from zoneinfo import ZoneInfo

LABELS={
 "es":dict(report="Informe de evaluación",scope="Alcance y metodología",results="Resultados",coverage="Cobertura por categoría",findings="Hallazgos y recomendaciones",appendix="Evidencia y versiones",date="Fecha",mode="Modo",target="Destino",status="Estado",case="Caso",verdict="Veredicto",count="Casos",asr="Éxito de ataques",detection="Detección",false_positives="Falsos positivos",conclusive="Concluyentes",noData="Sin datos",limits="Límites y exclusiones",empty="Sin hallazgos registrados en esta evaluación.",warning="Objetivo local sintético en modo rules. No certifica seguridad ni mide resistencia de un LLM. DEMO es simulación. Las revisiones requieren evidencia humana.",next="Reevaluar los casos afectados al cambiar permisos, prompts, modelos, fuentes o herramientas. Verificar correcciones con un retest enlazado."),
 "en":dict(report="Assessment report",scope="Scope and methodology",results="Results",coverage="Coverage by category",findings="Findings and recommendations",appendix="Evidence and versions",date="Date",mode="Mode",target="Target",status="Status",case="Case",verdict="Verdict",count="Cases",asr="Attack success",detection="Detection",false_positives="False positives",conclusive="Conclusive",noData="No data",limits="Limits and exclusions",empty="No findings recorded in this assessment.",warning="Synthetic local target in rules mode. Does not certify security or measure LLM resistance. DEMO is simulation. Reviews require human evidence.",next="Reassess affected cases after changes to permissions, prompts, models, sources or tools. Verify fixes with a linked retest."),
 "pt":dict(report="Relatório de avaliação",scope="Escopo e metodologia",results="Resultados",coverage="Cobertura por categoria",findings="Achados e recomendações",appendix="Evidência e versões",date="Data",mode="Modo",target="Alvo",status="Estado",case="Caso",verdict="Veredito",count="Casos",asr="Sucesso de ataques",detection="Detecção",false_positives="Falsos positivos",conclusive="Conclusivos",noData="Sem dados",limits="Limites e exclusões",empty="Sem achados registrados nesta avaliação.",warning="Alvo local sintético em modo rules. Não certifica segurança nem mede resistência de LLM. DEMO é simulação. Revisões requerem evidência humana.",next="Reavaliar casos afetados após alterações em permissões, prompts, modelos, fontes ou ferramentas. Verificar correções com reteste vinculado."),
}


def render(data):
    locale=data["locale"];labels=LABELS[locale]
    esc=lambda value:html.escape(str(value))
    t=lambda key:esc(labels[key])
    def rate(value):
        v=labels["noData"] if value["value"] is None else f'{value["value"]*100:.1f}%'
        return esc(f'{v} ({value["numerator"]}/{value["denominator"]})')
    metrics=data["metrics"]
    cases={c["id"]:c for c in data["catalog"]}
    rows="".join(f'<tr><td>{esc(r["case_id"])}</td><td>{esc(cases[r["case_id"]]["title"][locale])}</td><td>{esc(r["status"])}</td><td>{esc(r["verdict"])}</td></tr>' for r in data["results"])
    coverage="".join(f'<tr><td>{esc(k)}</td><td>{rate(v)}</td></tr>' for k,v in metrics["categories"].items())
    findings="".join(f'<article><h3>{esc(f["case_id"])} · {esc(f["severity"])} · {esc(f["status"])}</h3><pre>{esc(json.dumps(f,ensure_ascii=False,indent=2))}</pre></article>' for f in data["findings"]) or f'<p>{t("empty")}</p>'
    when=datetime.fromtimestamp(data["created"],ZoneInfo("America/Lima")).isoformat()
    scope={k:v for k,v in data["spec"].items() if k not in ("cases","target_id","parent_id")}
    return f'''<!doctype html><html lang="{locale}"><head><meta charset="utf-8"><title>Nexqori Security Lab</title>
<style>body{{font:15px/1.6 system-ui;color:#392c27;max-width:1100px;margin:3rem auto;padding:0 2rem;background:#fffcf9}}h1{{font:36px Georgia;color:#9a4b32}}h2{{margin-top:2rem;border-bottom:1px solid #d4b9a8}}.brand{{letter-spacing:3px;font-size:12px;color:#9a4b32}}.notice{{background:#f2d8c8;padding:1rem}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{text-align:left;border-bottom:1px solid #e6dcd5;padding:10px;vertical-align:top}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.5 monospace}}article{{break-inside:avoid}}@media print{{body{{background:white;margin:0;padding:0;max-width:none}}h2{{break-after:avoid}}thead{{display:table-header-group}}}}</style></head><body>
<p class="brand">NEXQORI / SECURITY LAB</p><h1>{t("report")}</h1><p>{esc(data["id"])}</p><p class="notice">{t("warning")}</p>
<h2>{t("scope")}</h2><p>{t("date")}: {esc(when)} · America/Lima<br>{t("mode")}: {esc(data["mode"])} · {t("target")}: {esc(data["target_id"])}<br>{t("status")}: {esc(data["status"])} · {t("count")}: {len(data["results"])}</p>
<p>{esc(' · '.join(f'{k}: {v}' for k,v in scope.items()))}</p>
<h2>{t("results")}</h2><table><tbody>{''.join(f'<tr><th>{t(k)}</th><td>{rate(metrics[k])}</td></tr>' for k in ("asr","detection","false_positives","conclusive"))}</tbody></table>
<h2>{t("coverage")}</h2><table><tbody>{coverage}</tbody></table><table><thead><tr><th>ID</th><th>{t("case")}</th><th>{t("status")}</th><th>{t("verdict")}</th></tr></thead><tbody>{rows}</tbody></table>
<h2>{t("findings")}</h2>{findings}<h2>{t("limits")}</h2><p>{t("warning")}</p><p>{t("next")}</p>
<h2>{t("appendix")}</h2><pre>{esc(json.dumps(data["versions"],ensure_ascii=False,indent=2))}</pre><details><summary>{t("appendix")} · JSON</summary><pre>{esc(json.dumps(data,ensure_ascii=False,indent=2))}</pre></details></body></html>'''
