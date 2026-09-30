# Tarjetas y correspondencia con el dataset

## Qué contiene PostgreSQL

La base de la app **se creó de cero mediante Alembic**, con fixtures coherentes en `backend/seed.py`. No se importaron las 13 tablas ni los registros individuales del organizador. Antes de esta ampliación se verificaron ocho tablas de aplicación (`users`, `sessions`, `products`, `transactions`, `requests`, `audit_events`, `conversations`, `messages`) y `alembic_version`. Se añade `card_profiles`, preservando las anteriores.

El dataset permanece local, con su análisis separado. El catálogo toma categorías y evidencia agregada; eso no implica correspondencia fila a fila entre Andrea y un cliente fuente.

| Dataset | Base operativa | Correspondencia y límite |
|---|---|---|
| `customers.customer_id` | `users.id` | Conceptual; IDs y perfiles locales nuevos. No hay importación ni mapeo individual. Credenciales/roles/sesiones propios de la app. |
| `products.product_id`, `customer_id` | `products.id`, `user_id` | Relación propia validada por FK; no conserva IDs originales. |
| `products.product_number` | `products.last4` + referencia de proveedor en `card_profiles` | Antes sólo se guardaba terminación. No copiar ni inferir PAN completo desde cuatro dígitos. El proveedor local entrega un número no operativo de prueba. |
| `products.expiration_date` | `card_profiles.expiry_month`, `expiry_year` | El campo existe en la fuente, pero no se ha importado. Vigencia 12/2029 pertenece al fixture, no al dataset. Valores ausentes se muestran como no disponibles. |
| CVV / CVV dinámico | Sin columna | No existe en el esquema fuente revisado. El código temporal no se persiste; no reconstruirlo de otros campos. |
| `products.product_status` | Sin equivalencia completa aún | El modelo base no conserva todos los estados fuente; no asumir bloqueo/activación funcional. Revelación rechaza vigencia expirada. |
| `products.current_balance`, `currency` | `balance_minor`, `currency` | Importes enteros en unidades menores; fixtures MXN, no conversión automática de las tres monedas fuente. |
| `transactions` | `transactions` | Modelo reducido, propietario coherente. `Approved` → `completed` es correspondencia conceptual; `Reversed` requiere un estado adicional antes de importar. |
| `complaints` | `requests` | Solicitudes propias, sin importar vínculos inconsistentes. `received/in_review/handed_off` no representan todas las resoluciones fuente. |
| Interacciones y transcripciones | `conversations`, `messages` | Historial generado en la app; cinco originales sintéticos sólo en el LAB local, sin importar al banco. |
| `digital_events` | Sin equivalente operativo | No son logs de intento/pasarela verificados. No convertirlos en evidencia de liquidación. |
| Auditoría, sesión, idempotencia | Tablas de aplicación | Nuevas necesidades del aplicativo, no datos del organizador. |

Fuente verificable: `notebooks/resultados_integral/column_profile.csv` incluye `product_number` y `expiration_date` en productos y no contiene CVV. Su perfil inicial cubre 400.000 filas muestreadas; los porcentajes de ese archivo no deben presentarse como censo completo. El censo y problemas de enlaces están documentados en [servicios basados en datos](servicios-basados-en-datos.md).

## Contrato de tarjetas implementado

- `GET /api/cards`: sesión de cliente; sólo tarjetas del titular, número enmascarado, titular y vigencia cuando exista. Administradores no obtienen credenciales de clientes.
- `POST /api/cards/{id}/reveal`: sesión, origen permitido, CSRF, tarjeta propia y contraseña válida. Cinco intentos por titular cada 15 minutos en el proceso local; errores sin secretos. Devuelve número, CVV y `expiresAt`; respuesta `Cache-Control: no-store`.
- El navegador conserva la respuesta sólo en memoria; la oculta al cumplirse 60 segundos, perder foco, ocultar pestaña o abandonar el componente. No se copia al portapapeles ni se persiste en localStorage, chat o auditoría.
- Auditoría registra `card_details_viewed`, actor y hora; nunca valores revelados. Contraseña se vacía del formulario al enviar. No registrar cuerpos de estas peticiones en proxies/telemetría futuros.
- Migración `d92e6047f831` añade metadatos y sólo reconoce la tarjeta fixture conocida `card-01`/Andrea/8942. Una tarjeta sin referencia de proveedor no recibe datos inventados.

## Límite del proveedor local

Compose habilita explícitamente `CARD_PROVIDER=local_fixture`. El número `0000000000008942` y los códigos aleatorios son **valores de prueba no utilizables para pagar**. El tiempo de 60 segundos es una regla de ocultación local, no un contrato de una red de tarjetas. No hay validación de compra, criptograma, HSM, rotación compartida de emisor ni garantía de unicidad entre códigos aleatorios de tres dígitos. Ningún PAN del dataset se utiliza.

Esto permite evaluar la experiencia solicitada. La integración real debe sustituir el adaptador por un emisor que controle emisión, vigencia y validación del CVV, autenticación reforzada y revocación. No bastaría convertir este generador local en un endpoint público. La interfaz mantiene el tono natural acordado; los límites se documentan aquí.

Referencia funcional: [BBVA, tarjeta digital](https://www.bbva.mx/educacion-financiera/banca-digital/como-se-genera-una-tarjeta-digital.html), consultada el 29/09/2026. Los tiempos y reglas locales no se atribuyen a BBVA.

## Si luego se decide importar el dataset

Crear una zona separada de staging, registrar IDs de origen y versión/lote, validar titularidad y moneda, aislar filas inconsistentes y transformar estados con reglas explícitas. El importador y la carga de las 13 tablas **no están implementados ni son necesarios para la vista actual**. No borrar fixtures o reemplazar usuarios para aparentar un match inexistente.
