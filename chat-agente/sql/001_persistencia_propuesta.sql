-- PROPUESTA: NO APLICADA. Revisar e integrar a Alembic antes de usar persistir_turno.
-- No modifica products, transactions, requests, sessions ni messages existentes.
BEGIN;
CREATE TABLE chat_agent_conversations (
    id uuid PRIMARY KEY,
    user_id varchar(64) NOT NULL REFERENCES users(id),
    version integer NOT NULL CHECK (version > 0),
    status text NOT NULL,
    state jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    UNIQUE (id, user_id)
);
CREATE TABLE chat_agent_turns (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL,
    user_id varchar(64) NOT NULL,
    client_message_id varchar(100) NOT NULL,
    payload_sha256 varchar(64) NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    FOREIGN KEY (conversation_id,user_id) REFERENCES chat_agent_conversations(id,user_id),
    UNIQUE (user_id,client_message_id)
);
CREATE INDEX chat_agent_turns_conversation ON chat_agent_turns(conversation_id,created_at);
-- GRANT debe limitarse al rol de persistencia autorizado; no conceder permisos a partir del modelo.
COMMIT;
