---
name: nexqori-brand
description: Crea o adapta la interfaz, los idiomas y la navegación del agente de Nexqori con su identidad Terracota suave. Úsala en la base React, FastAPI y PostgreSQL de Nexqori o en sus materiales de marca; no cambia marcas de otros proyectos.
---

# Nexqori

Nexqori es una experiencia bancaria cercana, clara y tranquila. Bryan eligió el nombre y la paleta P11 el 28 de septiembre de 2026. La identidad guía la presentación; no presupone integraciones bancarias o IA terminadas.

## Identidad que conservar

| Función | Color |
| --- | --- |
| Principal: acciones y marca | `#9A4B32` |
| Acento: fondos suaves y selección | `#F2D8C8` |
| Fondo: blanco cálido | `#FFFCF9` |
| Texto principal | `#392C27` |

Usa el nombre **Nexqori** en interfaz y `nexqori` en identificadores técnicos. No inventes una etimología, registro de marca ni disponibilidad de dominio.

## Aplicación de la identidad

- Consulta el objetivo y la estructura del proyecto antes de crear pantallas. Conserva componentes y tecnología existentes; adapta el diseño al encargo.
- Para CSS usa [assets/tokens.css](assets/tokens.css). En esta app la copia activa es `src/tokens.css`; si cambias tokens, sincroniza ambas. En otro proyecto adapta los nombres sin imponer el stack.
- Utiliza [assets/nexqori.svg](assets/nexqori.svg) como marca vectorial inicial. No es un logotipo registrado.
- Lee [references/interface.md](references/interface.md) para decisiones sobre tipografía, jerarquía, estados y comunicación bancaria.
- Usa superficies cálidas, espacio generoso y bordes sutiles. Reserva terracota para jerarquía, selección y acciones principales.
- Comprueba contraste en cada combinación real. Terracota con texto blanco cálido y texto oscuro sobre acento son las combinaciones preferidas. El acento no sirve como texto sobre blanco.
- Mantén acceso por teclado, foco visible, etiquetas, estados más allá del color y controles cómodos. Adapta a móvil y respeta movimiento reducido.

## Lenguaje y límites del producto

Escribe con cercanía, sin infantilizar. Ofrece el siguiente paso y explica el estado: solicitado, recibido, en revisión o resuelto. No prometas reembolso, bloqueo ni resolución si el servicio no lo ha confirmado.

La interfaz debe sentirse natural, como un producto bancario: por instrucción de Bryan, no añadir etiquetas de demo, modo demo, simulación o datos ficticios a las pantallas. Usar mensajes de producto que expliquen la consulta o solicitud realmente registrada. Mantener las limitaciones técnicas en la documentación; no inventar operaciones completadas, devoluciones, un operador conectado o un modelo de IA disponible. Español (`es`), inglés (`en`) y portugués (`pt`) tienen igual prioridad en toda la base: login, menús, formularios, errores, estados, agente, accesibilidad y administración. No conviertas moneda al cambiar idioma.

## Stack, idiomas y agente

- Mantén React con TypeScript, FastAPI, SQLAlchemy/Alembic y PostgreSQL. Docker Compose es el arranque local acordado. Consulta [references/architecture.md](references/architecture.md) para contratos y límites.
- Guarda textos de interfaz en `src/locales/{es,en,pt}.json`; verifica paridad de claves y variables. Traduce errores por código, no exponiendo excepciones del servidor. Formatea importes y fechas con locale; conserva moneda, referencia y nombres propios.
- Persiste el idioma en el perfil autenticado; la preferencia de navegador sirve antes del login. Marca el idioma de cada mensaje histórico, sin fingir que se tradujo.
- El agente navega con `navigate_in_app` y destinos enumerados; conserva contexto con un identificador de pantalla. Sin URL libre, SQL, credenciales ni cambios de rol procedentes de la conversación.
- Para una petición ambigua pide precisión. Para gestiones abre un formulario revisable y espera confirmación del usuario. La navegación nunca ejecuta pagos, transferencias, bloqueos ni contrataciones.
- Prueba un recorrido representativo ES/EN/PT y el aislamiento entre cliente y administrador al cambiar herramientas. Si se conecta un modelo, conserva las mismas validaciones y prueba sus fallos, sin retirar la ruta guiada disponible.

Para operaciones futuras conserva confirmación explícita, permisos en el servidor y trazabilidad. La identidad no autoriza publicar repositorios, ejecutar operaciones ni enviar mensajes. Valida los recorridos afectados y declara qué fue implementado, probado y desplegado.
