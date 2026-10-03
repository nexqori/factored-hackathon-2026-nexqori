# Validación local

Fecha de cierre: 2026-10-02, America/Lima.

## Implementado y desplegado

Laboratorio independiente en `security-lab/`, seis servicios Compose y dos volúmenes propios. Interfaz en `http://localhost:5190`, aplicación principal en 5180. No se publicó externamente ni se hicieron llamadas a proveedores durante esta tarea. El objetivo separado usa rules sin claves externas.

## Resultados comprobados

| Comprobación | Resultado |
|---|---|
| Backend del laboratorio | 22 pruebas aprobadas, también dentro de la imagen Docker final |
| Frontend del laboratorio | Paridad ES/EN/PT aprobada; TypeScript/Vite compila |
| Catálogo | 66 casos: 56 métodos de fuente y diez escenarios Nexqori |
| Evaluación HTTP real | 13 aprobados, 13 pendientes de revisión manual, 31 bloqueados/inconclusos, nueve no aplicables; cero errores de infraestructura |
| UI del laboratorio | ES/EN/PT, móvil, ejecución por formulario, revisión, hallazgo/retest, exportaciones y persistencia tras reinicio; ocho comprobaciones axe sin hallazgos, cero errores de página |
| Reporte HTML final | Exportación autenticada como lector, HTML hostil escapado, CSP, presentación inspeccionada y sin desbordamiento |
| Frontend principal | `npm test`: nueve pruebas descubiertas (ocho originales y una del laboratorio); `npm run build` correcto |
| Backend principal | 53 aprobadas y una omitida localmente; 54 aprobadas en el objetivo PostgreSQL con proveedores falsos |
| UI principal | 56 vistas, seis consultas, cinco comprobaciones de accesibilidad sin hallazgos; cero errores de página |
| Secretos y Git | `.env` y `.local` ignorados; búsqueda de secretos generados del laboratorio en 46 archivos compartibles: cero coincidencias; diff sin errores de espacios |
| Cuentas de verificación | Todas desactivadas, sesiones revocadas; cero usuarios temporales activos al cierre |

Ejecución completa de referencia: `6874f126-93af-44e6-a6c1-4c6a1d8ade19`. Retest DEMO verificado: `316de5d8-4696-44b6-8c86-c33a2470a85c`. Fallo deliberado DEMO: `dbbd2018-405a-430e-97a1-d06de754e47d`. Los registros sintéticos de demostración no se cuentan como hallazgos reales.

## Evidencias locales

`security-lab/.local/verification/` contiene `real-results.json`, `ui-results.json`, reportes JSON/CSV/HTML, captura `report-print.png` y capturas de dashboard ES/EN/PT, detalle y móvil. Permanecen fuera de Git. `initial-ui-results.json` conserva el diagnóstico inicial de accesibilidad, corregido después.

La regresión principal está en `security-lab/.local/main-ui-verification/`; creó la solicitud ficticia `UI verification NQ-9B47E785B9`. Se usó rules temporalmente y se restauró la configuración original en finally; se verificó `CHAT_AGENT_MODE=agent` y `CHAT_AGENT_ALLOW_EXTERNAL_DATA=true` al terminar. El laboratorio nunca heredó esas claves ni permisos de envío.

La pausa por límite de uso no perdió las evidencias: los volúmenes permanecieron y el laboratorio se reinició conservando nueve ejecuciones. Tras reanudar se repitieron las 22 pruebas del laboratorio y la comprobación de exportación lectora. El último ajuste fue exclusivamente de presentación del reporte, con su prueba de evidencia/exportación repetida satisfactoriamente.

## Límites

No se ejecutaron las 31 pruebas que necesitan componentes/modelo autorizado en el objetivo ni se completaron las 13 revisiones humanas por el mero hecho de crear el panel. La cobertura ejecutada no se presenta como completa. Las nueve exclusiones tienen justificación. MITRE ATLAS conserva identificadores pendientes de verificación. Las sondas HTTP no aportan telemetría de detección ni tokens/coste: esos campos muestran sin datos.

Existe una advertencia no bloqueante de deprecación Starlette/TestClient-httpx en las pruebas. No se migraron dependencias del proyecto principal para resolverla. Las pruebas y axe no certifican seguridad, precisión general de un modelo ni accesibilidad total.

Para empezar a usar el panel, el propietario debe crear su administrador mediante la CLI interactiva del README; no se deja una contraseña prefijada ni un administrador temporal activo.
