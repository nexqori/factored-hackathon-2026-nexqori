# Trabajo del equipo en GitHub

Acuerdo del 3 de octubre de 2026, a partir de la recomendación del hackathon compartida por Bryan.

1. Actualiza `main` y crea una rama para un cambio concreto. En Codex se usa `codex/descripcion`; conserva los nombres que indique el equipo.
2. Mantén el PR centrado en un caso de uso o una corrección. Incluye implementación, traducciones ES/EN/PT y pruebas pertinentes.
3. Escribe commits que expliquen el resultado, por ejemplo `fix(chat): conserva el movimiento al aclarar el reclamo`. Evita títulos como «cambios» o «final».
4. Describe en el PR el problema, el comportamiento resultante, las comprobaciones y los límites. Fusiona después de las comprobaciones automáticas y la revisión acordada.
5. Etiqueta una entrega comprobada con `vMAJOR.MINOR.PATCH`. Una corrección compatible aumenta PATCH; una función compatible aumenta MINOR. Actualiza la versión del paquete y de la API junto con la entrega. No reutilices ni muevas etiquetas publicadas.
6. Para mantener `bryan` igual que la entrega de `main`, actualízala por avance rápido si no tiene cambios propios pendientes. Si los tiene, intégralos y valida; no fuerces ni sobrescribas la rama.

No subas `.env`, claves, accesos de prueba, datos originales, PDFs privados ni respaldos. Las guías de casos y scripts reproducibles sí forman parte del repositorio. Cargar cinco usuarios localmente no publica su base ni sus contraseñas.

La entrega `v0.2.0` reúne selección y resumen de reclamos, documentos preparados desde la conversación y cinco perfiles para pruebas UX. Para las siguientes mejoras, usa un PR por caso cuando puedan probarse de forma independiente. El estado operativo sigue en [ESTADO.md](../ESTADO.md); la guía de ejecución está en [INICIO-EQUIPO.md](../INICIO-EQUIPO.md).
