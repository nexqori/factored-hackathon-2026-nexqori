"""Sólo lectura de esquema backend; todos los filtros de titular salen de la sesión."""
from datetime import datetime
from decimal import Decimal
import time
import psycopg
from psycopg.rows import dict_row
from .contratos import require, digest, now

QUERIES = {
 'products': 'SELECT id,type,last4,balance_minor,currency FROM products WHERE user_id=%(uid)s AND (%(pid)s::text IS NULL OR id=%(pid)s) AND (%(kinds)s::text[] IS NULL OR type=ANY(%(kinds)s::text[])) ORDER BY id LIMIT %(limit)s',
 'transactions': 'SELECT t.id,t.product_id,t.merchant,t.category,t.amount_minor,t.currency,t.occurred_at,t.status FROM transactions t JOIN products p ON p.id=t.product_id AND p.user_id=t.user_id WHERE t.user_id=%(uid)s AND (%(pid)s::text IS NULL OR t.product_id=%(pid)s) AND (%(tid)s::text IS NULL OR t.id=%(tid)s) AND (%(start)s::timestamptz IS NULL OR t.occurred_at>=%(start)s::timestamptz) AND (%(end)s::timestamptz IS NULL OR t.occurred_at<%(end)s::timestamptz) ORDER BY t.occurred_at DESC,t.id LIMIT %(limit)s',
 'requests': 'SELECT id,transaction_id,service,reason,details,status,created_at,updated_at FROM requests WHERE user_id=%(uid)s AND (%(rid)s::text IS NULL OR id=%(rid)s) ORDER BY created_at DESC,id LIMIT %(limit)s',
 'related_transactions': 'SELECT t.id,t.product_id,t.merchant,t.category,t.amount_minor,t.currency,t.occurred_at,t.status FROM transactions t JOIN products p ON p.id=t.product_id AND p.user_id=t.user_id WHERE t.user_id=%(uid)s AND t.id=ANY(%(ids)s::text[]) ORDER BY t.id LIMIT %(limit)s',
 'related_products': 'SELECT id,type,last4,balance_minor,currency FROM products WHERE user_id=%(uid)s AND id=ANY(%(ids)s::text[]) ORDER BY id LIMIT %(limit)s',
}


def normalize(row):
    value = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in row.items()}
    for key in ('balance_minor', 'amount_minor'):
        if key in value:
            value[key.replace('_minor', '_display')] = None if value[key] is None else format(Decimal(value[key]) / 100, '.2f') + ' ' + value['currency']
    return value


class PostgresRepository:
    def __init__(self, settings):
        self.settings = settings

    def _connect(self):
        require(bool(self.settings.database_url), 'MISSING_DATABASE_URL', 'Falta DATABASE_URL o database_url explícita.')
        # SQLAlchemy suele usar postgresql+psycopg://; psycopg espera postgresql://.
        url = self.settings.database_url.replace('postgresql+psycopg://', 'postgresql://', 1)
        return psycopg.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=5)

    @staticmethod
    def _session(conn, token, expected_user):
        require(isinstance(token, str) and len(token) == 64, 'SESSION_REQUIRED', 'Se requiere cookie nexqori_session vigente.')
        row = conn.execute('SELECT u.id,u.role,s.expires_at FROM public.sessions s JOIN public.users u ON u.id=s.user_id WHERE s.token_hash=%s AND s.expires_at>%s', (digest(token), int(time.time()))).fetchone()
        require(row is not None and row['role'] == 'customer' and row['id'] == expected_user,
                'UNAUTHORIZED', 'Sesión inválida, caducada, de otro titular o sin rol cliente.')
        return row['id']

    def authenticate(self, token, expected_user):
        with self._connect() as conn, conn.transaction():
            conn.execute('SET TRANSACTION READ ONLY')
            conn.execute("SET LOCAL statement_timeout='3000ms'")
            return self._session(conn, token, expected_user)

    def retrieve(self, token, expected_user, intent, action, fields, trace):
        require(action['kind'] == 'read', 'NOT_READ_ACTION', 'Sólo se recuperan consultas de lectura.')
        table = action['query']
        if table == 'catalog':
            self.authenticate(token, expected_user)
            return {'facts': [], 'status': 'ok', 'retrieved_at': now(), 'catalog': action['description']}
        allowed = {'products': {'product_id'}, 'transactions': {'product_id', 'transaction_id'}, 'requests': {'request_id'}}[table]
        require(not any(fields.get(k) for k in {'product_id', 'transaction_id', 'request_id'} - allowed),
                'INCOMPATIBLE_SELECTION', 'Selección incompatible con la consulta.')
        packet = {'facts': [], 'status': 'ok', 'retrieved_at': now(), 'query_trace': [], 'execution_authorized': False}
        with self._connect() as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            conn.execute("SET LOCAL search_path = public, pg_catalog")
            conn.execute("SET LOCAL statement_timeout='3000ms'")
            conn.execute("SET LOCAL lock_timeout='1000ms'")
            uid = self._session(conn, token, expected_user)
            params = {'uid': uid, 'pid': fields.get('product_id'), 'tid': fields.get('transaction_id'),
                'rid': fields.get('request_id'), 'start': fields.get('start'), 'end': fields.get('end'),
                'kinds': ['account', 'savings'] if intent == 'accounts' else ['card'] if intent == 'cards' else None,
                'limit': self.settings.max_rows + 1, 'ids': []}

            def query(name, **updates):
                values = {**params, **updates}
                rows = conn.execute(QUERIES[name], values).fetchall()
                require(len(rows) <= self.settings.max_rows, 'ROW_LIMIT', 'Demasiados registros: acotar filtros antes de continuar.')
                record = {'query': name, 'sql': QUERIES[name], 'params': {k: v for k, v in values.items() if k != 'uid'}, 'row_count': len(rows)}
                packet['query_trace'].append(record); trace.add('codigo5.sql', **record)
                return rows

            def add(table_name, rows):
                for row in rows:
                    ref = table_name + ':' + row['id']
                    if not any(f['source_ref'] == ref for f in packet['facts']):
                        packet['facts'].append({'fact_id': 'F' + str(len(packet['facts']) + 1), 'source_ref': ref, 'values': normalize(row)})
            rows = query(table); add(table, rows)
            if not rows and any(fields.get(k) for k in allowed):
                packet['status'] = 'not_found'
                return packet
            transactions = rows if table == 'transactions' else []
            if table == 'requests':
                ids = sorted({r['transaction_id'] for r in rows if r['transaction_id']})
                if ids:
                    transactions = query('related_transactions', ids=ids)
                    require({r['id'] for r in transactions} == set(ids), 'RELATION_INTEGRITY', 'Movimiento relacionado inexistente o sin titularidad.')
                    add('transactions', transactions)
            if transactions:
                ids = sorted({r['product_id'] for r in transactions})
                products = query('related_products', ids=ids)
                require({r['id'] for r in products} == set(ids), 'RELATION_INTEGRITY', 'Producto relacionado inexistente o sin titularidad.')
                add('products', products)
        return packet
