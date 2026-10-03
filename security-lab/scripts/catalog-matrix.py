"""Regenerate the documentation matrix from the versioned catalog."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lab.catalog import CATALOG, VERSION, CONSULTED

root=Path(__file__).resolve().parents[1]
lines=[f"# Matriz de cobertura v{VERSION}","",f"Consulta: {CONSULTED}, America/Lima. Fuente, pasos, prerrequisitos y límites completos están en el catálogo autenticado y los reportes JSON. Esta tabla describe capacidad, no resultados ejecutados.","","| Caso | Fuente / método | Categoría | Implementación | Evidencia / límite |","|---|---|---|---|---|"]
for case in CATALOG:
    source=case["source"]
    url=source["url"] if source["url"].startswith("https:") else "../../docs/agente.md"
    lines.append(f'| {case["id"]} | [{source["method"]}]({url}) | {case["category"]} | {case["executor"] or case["mode"]} | {case["reason"]["es"]} |')
(root/"docs/coverage.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
