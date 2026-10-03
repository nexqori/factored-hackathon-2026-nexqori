"""Local account administration. Passwords use getpass, never command arguments."""
import argparse
import getpass
from sqlalchemy import select, delete
from .db import User, Session, Target, audit, engine_for, sessions
from .security import HASHER


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create-admin", "reset-password", "seed-targets"])
    parser.add_argument("username", nargs="?")
    args = parser.parse_args()
    with sessions(engine_for())() as db:
        if args.command == "seed-targets":
            for adapter, name in [("nexqori-local", "Nexqori · isolated rules"), ("demo", "DEMO · deterministic simulation")]:
                if not db.scalar(select(Target).where(Target.adapter == adapter)):
                    db.add(Target(name=name, adapter=adapter))
        else:
            if not args.username or not 3 <= len(args.username) <= 80:
                parser.error("username: 3–80 characters")
            user = db.scalar(select(User).where(User.username == args.username.lower()))
            if args.command == "create-admin" and user:
                parser.error("Account already exists; use reset-password")
            if args.command == "reset-password" and not user:
                parser.error("Account not found")
            password = getpass.getpass("New password (minimum 14 characters): ")
            if len(password) < 14 or len(password) > 256 or password != getpass.getpass("Repeat password: "):
                parser.error("Password length or confirmation invalid")
            if user:
                user.password_hash = HASHER.hash(password)
                db.execute(delete(Session).where(Session.user_id == user.id))
            else:
                db.add(User(username=args.username.lower(), password_hash=HASHER.hash(password), role="admin"))
            audit(db, "local-cli", args.command, args.username.lower())
        db.commit()
    print("Completed. No credentials printed.")


if __name__ == "__main__":
    main()
