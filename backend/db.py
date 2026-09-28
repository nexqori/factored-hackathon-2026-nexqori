import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .models import Base

def make_engine(url=None):
    url = url or os.environ["DATABASE_URL"]
    options = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, pool_pre_ping=True, connect_args=options)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine

def make_sessions(engine):
    return sessionmaker(engine, expire_on_commit=False)

def session_dependency(request):
    with request.app.state.sessions() as session:
        yield session
