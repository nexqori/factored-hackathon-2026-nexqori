"""Ejecuta con el Python activo y exporta HTML, sin registrar kernels globales."""
import json
import os
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

ROOT = Path(__file__).resolve().parents[1]
kernel_dir = ROOT / "dataset" / "_eda_problemas" / "kernels" / "factored-eda"
kernel_dir.mkdir(parents=True, exist_ok=True)
(kernel_dir / "kernel.json").write_text(json.dumps({
    "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
    "display_name": "Python (Factored EDA)", "language": "python"
}), encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["MPLBACKEND"] = "module://matplotlib_inline.backend_inline"
km = KernelManager(kernel_name="factored-eda", kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernel_dir.parent)]))
path = ROOT / "notebooks" / "EDA_PROBLEMAS.ipynb"
nb = nbformat.read(path, as_version=4)
client = NotebookClient(nb, km=km, timeout=600, resources={"metadata":{"path":str(ROOT)}}, allow_errors=False)
try:
    client.execute()
finally:
    if km.has_kernel:
        km.shutdown_kernel(now=True)
nbformat.validate(nb)
errors = [o for c in nb.cells if c.cell_type=="code" for o in c.get("outputs",[]) if o.output_type=="error"]
assert not errors
assert all(c.execution_count is not None for c in nb.cells if c.cell_type=="code")
nbformat.write(nb,path)
html,_ = HTMLExporter(template_name="lab", exclude_input=True).from_notebook_node(nb)
(path.with_suffix(".html")).write_text(html,encoding="utf-8")
images = sum("image/png" in o.get("data",{}) for c in nb.cells for o in c.get("outputs",[]))
print(f"Notebook ejecutado: {len(nb.cells)} celdas, {images} gráficos incrustados, sin errores. HTML exportado.")
