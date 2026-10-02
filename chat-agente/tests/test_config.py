"""Pruebas de configuración escritas, no ejecutadas. Sin conexiones ni APIs."""
import unittest
from nexqori_chat.config import resolve_database_url
from nexqori_chat.contratos import AgentError


class DatabaseConfigurationTests(unittest.TestCase):
    def test_explicit_url_has_priority(self):
        self.assertEqual(resolve_database_url({'DATABASE_URL': 'postgresql://environment/db'},
                                             'postgresql://explicit/db'), 'postgresql://explicit/db')

    def test_existing_url_has_priority_over_components(self):
        self.assertEqual(resolve_database_url({'DATABASE_URL': 'postgresql://existing/db',
                                              'PGHOST': 'another', 'APP_DATABASE_PASSWORD': 'fake'}),
                         'postgresql://existing/db')

    def test_compose_defaults_and_encoded_password(self):
        self.assertEqual(resolve_database_url({'APP_DATABASE_PASSWORD': 'fake@:#${x}'}),
                         'postgresql://nexqori_app:fake%40%3A%23%24%7Bx%7D@db:5432/nexqori')

    def test_independent_host_and_port(self):
        self.assertEqual(resolve_database_url({'APP_DATABASE_PASSWORD': 'fake',
                                              'PGHOST': '127.0.0.1', 'PGPORT': '55432'}),
                         'postgresql://nexqori_app:fake@127.0.0.1:55432/nexqori')

    def test_missing_connection_configuration(self):
        with self.assertRaises(AgentError):
            resolve_database_url({})

    def test_invalid_port(self):
        with self.assertRaises(AgentError):
            resolve_database_url({'APP_DATABASE_PASSWORD': 'fake', 'PGPORT': '70000'})
