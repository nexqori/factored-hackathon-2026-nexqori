"""Adaptador futuro explícito. El coordinador NO lo llama ni aplica la propuesta SQL."""
from psycopg.types.json import Jsonb
from .contratos import require, digest, encode
from .postgres import PostgresRepository


def persistir_turno(conn, payload, *, session_token):
    """Usar desde servidor con payload devuelto por el agente, nunca JSON del cliente.

    Requiere tablas de sql/001_persistencia_propuesta.sql ya migradas y conexión dedicada.
    Conserva historial, preguntas, respuestas, decisiones, errores y trazas completos en JSONB.
    """
    require(payload['authenticated'] and payload['conversation'] is not None, 'UNAUTHENTICATED_RECORD', 'No persistir como turno autenticado un intento sin sesión.')
    state = payload['conversation'];uid = payload['user_id']
    require(state['user_id'] == uid, 'PERSISTENCE_OWNER', 'Titular incompatible.')
    fingerprint = digest(encode(payload))
    with conn.transaction():
        conn.execute("SET LOCAL statement_timeout='5000ms'")
        PostgresRepository._session(conn, session_token, uid)
        with conn.cursor() as cursor:
            cursor.execute('SELECT payload_sha256 FROM chat_agent_turns WHERE user_id=%s AND client_message_id=%s', (uid,payload['client_message']['message_id']))
            existing = cursor.fetchone()
            if existing:
                saved_hash = existing['payload_sha256'] if isinstance(existing,dict) else existing[0]
                require(saved_hash == fingerprint, 'PERSISTENCE_CONFLICT', 'Turno ya guardado con otro contenido.')
                return {'persisted': True, 'reused': True, 'turn_id': payload['turn_id']}
            cursor.execute('SELECT version FROM chat_agent_conversations WHERE id=%s AND user_id=%s FOR UPDATE', (state['id'],uid))
            current = cursor.fetchone()
            if current:
                version = current['version'] if isinstance(current,dict) else current[0]
                require(version == state['version']-1, 'PERSISTENCE_VERSION', 'Estado desactualizado o faltan turnos por guardar.')
                cursor.execute('UPDATE chat_agent_conversations SET version=%s,status=%s,state=%s,updated_at=%s WHERE id=%s AND user_id=%s',
                    (state['version'],state['status'],Jsonb(state),payload['generated_at'],state['id'],uid))
            else:
                require(state['version'] == 1, 'PERSISTENCE_VERSION', 'Guardar primero el primer turno de la conversación.')
                cursor.execute('INSERT INTO chat_agent_conversations (id,user_id,version,status,state,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                    (state['id'],uid,state['version'],state['status'],Jsonb(state),state['created_at'],payload['generated_at']))
            cursor.execute('INSERT INTO chat_agent_turns (id,conversation_id,user_id,client_message_id,payload_sha256,payload,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                (payload['turn_id'],state['id'],uid,payload['client_message']['message_id'],fingerprint,Jsonb(payload),payload['generated_at']))
    return {'persisted': True, 'reused': False, 'turn_id': payload['turn_id']}
