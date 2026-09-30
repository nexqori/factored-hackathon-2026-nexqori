"""Ejecuta con el Python actual sin instalar kernels globales; conserva errores."""
import os
import sys
import json
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter

out=Path(__file__).resolve().parent
runtime=out/'runtime'
kernel=runtime/'jupyter/kernels/nexqori-intentions'
kernel.mkdir(parents=True,exist_ok=True)
(kernel/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],'display_name':'Nexqori intentions','language':'python'}),encoding='utf-8')
os.environ['JUPYTER_PATH']=str(runtime/'jupyter')
os.environ['JUPYTER_RUNTIME_DIR']=str(runtime/'jupyter-runtime')
os.environ['IPYTHONDIR']=str(runtime/'ipython')
os.environ['MPLCONFIGDIR']=str(runtime/'matplotlib')
path=out/'INTENTIONS_EDA.ipynb'
nb=nbformat.read(path,as_version=4)
def progress(cell,cell_index,**kwargs):
    print(f'Celda {cell_index+1}/{len(nb.cells)} completada',flush=True)
client=NotebookClient(nb,timeout=3600,kernel_name='nexqori-intentions',resources={'metadata':{'path':str(out)}},on_cell_executed=progress)
try:
    client.execute()
finally:
    nbformat.write(nb,path)
html,_=HTMLExporter().from_notebook_node(nb)
(out/'INTENTIONS_EDA.html').write_text(html,encoding='utf-8')
print('Notebook y HTML guardados.',flush=True)
