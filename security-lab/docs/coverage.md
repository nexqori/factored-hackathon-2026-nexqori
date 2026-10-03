# Matriz de cobertura v1.0.0

Consulta: 2026-10-02, America/Lima. Fuente, pasos, prerrequisitos y límites completos están en el catálogo autenticado y los reportes JSON. Esta tabla describe capacidad, no resultados ejecutados.

| Caso | Fuente / método | Categoría | Implementación | Evidencia / límite |
|---|---|---|---|---|
| LLM01-01 | [Direct injection](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM01:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM01-02 | [Indirect injection](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM01:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM01-03 | [Multi-turn manipulation](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM01:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM01-04 | [Encoding bypass](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM01:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM01-05 | [Jailbreak testing](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM01:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM01-06 | [System prompt extraction](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM01:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM02-01 | [System prompt extraction](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM02:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM02-02 | [Training data extraction](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM02:2025 | not_applicable | Requiere acceso autorizado al corpus de entrenamiento y pruebas de pertenencia |
| LLM02-03 | [PII leakage](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM02:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM02-04 | [Cross-tenant leakage](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM02:2025 | isolation | Prueba HTTP real del contrato; no mide resistencia semántica de un LLM. |
| LLM02-05 | [API response analysis](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM02:2025 | errors | Prueba HTTP real del contrato; no mide resistencia semántica de un LLM. |
| LLM03-01 | [Model provenance](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM03:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM03-02 | [Plugin/tool audit](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM03:2025 | manual | Requiere evidencia revisada por una persona. |
| LLM03-03 | [Dependency analysis](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM03:2025 | manual | Requiere evidencia revisada por una persona. |
| LLM03-04 | [Third-party API review](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM03:2025 | manual | Requiere evidencia revisada por una persona. |
| LLM03-05 | [Embedding model integrity](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM03:2025 | not_applicable | No hay modelo de embeddings desplegado en el objetivo rules |
| LLM04-01 | [RAG poisoning](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM04:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM04-02 | [Training data audit](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM04:2025 | not_applicable | No existe entrenamiento operativo en esta instancia |
| LLM04-03 | [Fine-tuning integrity](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM04:2025 | not_applicable | No existe pipeline de ajuste desplegado |
| LLM04-04 | [Backdoor detection](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM04:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM04-05 | [Data source authentication](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM04:2025 | manual | Requiere evidencia revisada por una persona. |
| LLM05-01 | [SQL injection via output](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM05:2025 | manual | Requiere evidencia revisada por una persona. |
| LLM05-02 | [XSS via output](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM05:2025 | manual | Requiere evidencia revisada por una persona. |
| LLM05-03 | [Command injection via output](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM05:2025 | manual | Requiere evidencia revisada por una persona. |
| LLM05-04 | [SSRF via output](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM05:2025 | manual | Requiere evidencia revisada por una persona. |
| LLM05-05 | [Code injection](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM05:2025 | manual | Requiere evidencia revisada por una persona. |
| LLM06-01 | [Capability inventory](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM06:2025 | manual | Requiere evidencia revisada por una persona. |
| LLM06-02 | [Permission escalation](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM06:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM06-03 | [Least privilege validation](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM06:2025 | manual | Requiere evidencia revisada por una persona. |
| LLM06-04 | [Action confirmation](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM06:2025 | confirmation | Prueba HTTP real del contrato; no mide resistencia semántica de un LLM. |
| LLM06-05 | [Scope boundary testing](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM06:2025 | scope | Prueba HTTP real del contrato; no mide resistencia semántica de un LLM. |
| LLM07-01 | [Direct request](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM07:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM07-02 | [Rephrasing](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM07:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM07-03 | [Translation](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM07:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM07-04 | [Role reversal](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM07:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM07-05 | [Completion](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM07:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM07-06 | [Encoding](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM07:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM07-07 | [Summarization](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM07:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM07-08 | [Negation](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM07:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM07-09 | [Hypothetical](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM07:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM07-10 | [Multi-turn](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM07:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM08-01 | [Cross-tenant isolation](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM08:2025 | not_applicable | No existe almacén vectorial; la recuperación actual usa SQL fijo |
| LLM08-02 | [Access control bypass](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM08:2025 | not_applicable | No existe almacén vectorial; la recuperación actual usa SQL fijo |
| LLM08-03 | [Adversarial retrieval](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM08:2025 | not_applicable | No existe almacén vectorial; la recuperación actual usa SQL fijo |
| LLM08-04 | [Embedding inversion](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM08:2025 | not_applicable | No existe almacén vectorial; la recuperación actual usa SQL fijo |
| LLM08-05 | [Vector store enumeration](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM08:2025 | not_applicable | No existe almacén vectorial; la recuperación actual usa SQL fijo |
| LLM09-01 | [Hallucination rate](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM09:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM09-02 | [Confidence calibration](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM09:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM09-03 | [Citation verification](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM09:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM09-04 | [Adversarial misinformation](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM09:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM09-05 | [RAG faithfulness](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM09:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM10-01 | [Maximum token generation](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM10:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM10-02 | [Recursive tool calling](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM10:2025 | manual | Requiere evidencia revisada por una persona. |
| LLM10-03 | [Rate limit testing](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM10:2025 | manual | Requiere evidencia revisada por una persona. |
| LLM10-04 | [Cost estimation attacks](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM10:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
| LLM10-05 | [Concurrent request flooding](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) | LLM10:2025 | concurrency | Prueba HTTP real del contrato; no mide resistencia semántica de un LLM. |
| NQ-auth | [auth](../../docs/agente.md) | LLM06:2025 | auth | Prueba HTTP real del contrato; no mide resistencia semántica de un LLM. |
| NQ-csrf | [csrf](../../docs/agente.md) | LLM06:2025 | csrf | Prueba HTTP real del contrato; no mide resistencia semántica de un LLM. |
| NQ-idempotency | [idempotency](../../docs/agente.md) | LLM06:2025 | idempotency | Prueba HTTP real del contrato; no mide resistencia semántica de un LLM. |
| NQ-ownership | [ownership](../../docs/agente.md) | LLM02:2025 | ownership | Prueba HTTP real del contrato; no mide resistencia semántica de un LLM. |
| NQ-logout | [logout](../../docs/agente.md) | LLM06:2025 | logout | Prueba HTTP real del contrato; no mide resistencia semántica de un LLM. |
| NQ-size | [size](../../docs/agente.md) | LLM10:2025 | size | Prueba HTTP real del contrato; no mide resistencia semántica de un LLM. |
| NQ-baseline | [baseline](../../docs/agente.md) | LLM09:2025 | baseline | Prueba HTTP real del contrato; no mide resistencia semántica de un LLM. |
| NQ-agent_authority | [agent_authority](../../docs/agente.md) | LLM06:2025 | agent_authority | Prueba HTTP real del contrato; no mide resistencia semántica de un LLM. |
| NQ-document-isolation | [document-isolation](../../docs/agente.md) | LLM02:2025 | blocked | Requiere consulta Jev válida, canDocument=true y PDF sintético. Faltan fixture y proveedor autorizado. Mismo titular en sesión vigente: 200; otro titular: 404; sin sesión: 401. No se atribuye resultado. |
| NQ-handoff-isolation | [handoff-isolation](../../docs/agente.md) | LLM02:2025 | blocked | El objetivo aislado usa rules, sin modelo ni envío externo autorizado. |
