"""Entrada manual; nunca se ejecuta al importar el paquete."""
import argparse
import getpass
from dotenv import load_dotenv
from .config import ROOT, Settings
from .postgres import PostgresRepository
from .codigo1_orquestador import ChatAgent, solicitud_predeterminada


def main():
    parser = argparse.ArgumentParser(description='Solicitud predeterminada a Nexqori; conexiones sólo con activación explícita.')
    parser.add_argument('--user-id', required=True, help='ID real de users, titular de la sesión.')
    parser.add_argument('--text', default='¿Cuál es el saldo de todas mis cuentas?')
    parser.add_argument('--language', choices=['es', 'en', 'pt'], default='es')
    parser.add_argument('--enable-api', action='store_true')
    parser.add_argument('--allow-external-data', action='store_true')
    args = parser.parse_args()
    if not (args.enable_api and args.allow_external_data):
        parser.error('Se requieren --enable-api y --allow-external-data; no se inició ninguna consulta.')
    load_dotenv(ROOT.parent / '.env', override=False)
    settings = Settings.from_env(allow_api=args.enable_api, allow_external_data=args.allow_external_data)
    token = getpass.getpass('Cookie nexqori_session del cliente (oculta): ')
    service = ChatAgent(settings, PostgresRepository(settings))
    solicitud_predeterminada(service, user_id=args.user_id, session_token=token, text=args.text, language=args.language)


if __name__ == '__main__':
    main()
