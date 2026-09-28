#!/usr/bin/env python3
"""Descarga reproducible de S3. Requiere Python 3.9+ y AWS CLI v2 en PATH."""

import argparse
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import time


DEFAULT_BUCKET = "factored-datathon-2026-s3-157725502942-us-east-2-an"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRIORITY = [
    "complaints", "call_center_interactions", "call_transcripts",
    "satisfaction_surveys", "transactions", "campaign_sends", "digital_events",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def local_path(destination, key, prefix):
    relative = key[len(prefix):]
    parts = PurePosixPath(relative).parts
    if (not key.startswith(prefix) or not parts or relative.startswith("/")
            or any(part in (".", "..") or ":" in part or "\\" in part for part in parts)):
        raise ValueError("El inventario contiene una ruta no admitida.")
    target = destination.joinpath(*parts).resolve()
    if not target.is_relative_to(destination) or parts[0] == "_descarga":
        raise ValueError("Un archivo de S3 invade una ruta reservada o externa.")
    return target


def progress(inventory, destination, state, stage, started_at, error=None):
    groups = defaultdict(lambda: {"files_total": 0, "bytes_total": 0,
                                  "files_available": 0, "bytes_available": 0})
    for item in inventory["objects"]:
        relative = item["Key"][len(inventory["prefix"]):]
        group = relative.split("/", 1)[0] if "/" in relative else "tablas_base"
        summary = groups[group]
        summary["files_total"] += 1
        summary["bytes_total"] += item["Size"]
        path = local_path(destination, item["Key"], inventory["prefix"])
        if path.is_file() and path.stat().st_size == item["Size"]:
            summary["files_available"] += 1
            summary["bytes_available"] += item["Size"]
    result = {"state": state, "stage": stage, "pid": os.getpid(),
              "started_at": started_at, "updated_at": now(), "destination": str(destination),
              "verification": "Existencia y tamano; no valida filas ni integridad criptografica.",
              "groups": dict(groups)}
    for field in ("files_total", "bytes_total", "files_available", "bytes_available"):
        result[field] = sum(group[field] for group in groups.values())
    if error:
        result["error"] = error
    write_json(destination / "_descarga" / "progreso.json", result)
    return result


@contextmanager
def download_lock(path):
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Ya hay una descarga activa en esta carpeta.") from exc
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--prefix", default="data/")
    parser.add_argument("--region", default="us-east-2")
    parser.add_argument("--profile", help="Perfil AWS local; opcional si usas variables de entorno.")
    parser.add_argument("--destination", type=Path, default=PROJECT_ROOT / "dataset")
    parser.add_argument("--inventory-only", action="store_true", help="Lista archivos sin descargarlos.")
    parser.add_argument("--status", action="store_true", help="Muestra el ultimo avance local sin conectarse a AWS.")
    args = parser.parse_args()
    destination = args.destination.resolve()
    metadata = destination / "_descarga"
    if args.status:
        status_path = metadata / "progreso.json"
        if not status_path.exists():
            parser.error("Aun no hay un registro de avance en esta carpeta.")
        print(status_path.read_text(encoding="utf-8"))
        return 0
    aws = shutil.which("aws")
    if not aws:
        parser.error("Instala AWS CLI v2 y agrega aws al PATH.")
    prefix = args.prefix.strip("/") + "/" if args.prefix.strip("/") else ""
    metadata.mkdir(parents=True, exist_ok=True)
    base = [aws, "--region", args.region, "--no-cli-pager"]
    if args.profile:
        base += ["--profile", args.profile]
    environment = os.environ.copy()
    environment["AWS_PAGER"] = ""
    # Un perfil explicito no debe quedar oculto por credenciales heredadas.
    if args.profile:
        for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
            environment.pop(name, None)
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    started_at = now()
    inventory = None
    stage = "inventario"
    with download_lock(metadata / "descarga.lock"):
        try:
            print("Consultando inventario S3...", flush=True)
            listing = subprocess.run(
                base + ["s3api", "list-objects-v2", "--bucket", args.bucket,
                        "--prefix", prefix, "--output", "json"],
                env=environment, capture_output=True, text=True, encoding="utf-8",
                creationflags=creationflags, timeout=180,
            )
            if listing.returncode:
                raise RuntimeError("No se pudo listar S3. Comprueba el perfil, permisos y conexion.")
            objects = [item for item in json.loads(listing.stdout).get("Contents", [])
                       if not item["Key"].endswith("/")]
            if not objects:
                raise RuntimeError("El prefijo de S3 no contiene archivos.")
            for item in objects:
                local_path(destination, item["Key"], prefix)
            inventory = {"bucket": args.bucket, "prefix": prefix, "region": args.region,
                         "observed_at": now(), "objects": objects}
            write_json(metadata / "inventario-s3.json", inventory)
            current = progress(inventory, destination, "inventariado", stage, started_at)
            print(f"{current['files_total']:,} archivos; {current['bytes_total'] / 1e9:.2f} GB.", flush=True)
            if args.inventory_only:
                return 0
            remaining = current["bytes_total"] - current["bytes_available"]
            if shutil.disk_usage(destination).free < remaining + 256 * 1024**2:
                raise RuntimeError("Espacio libre insuficiente para completar la descarga.")
            source = f"s3://{args.bucket}/{prefix}"
            root_files = sorted(
                [item for item in objects if "/" not in item["Key"][len(prefix):]],
                key=lambda item: item["Size"],
            )
            directories = {item["Key"][len(prefix):].split("/", 1)[0]
                           for item in objects if "/" in item["Key"][len(prefix):]}
            ordered = sorted(directories, key=lambda name: (PRIORITY.index(name)
                             if name in PRIORITY else len(PRIORITY), name))
            jobs = []
            for item in root_files:
                target = local_path(destination, item["Key"], prefix)
                if target.is_file() and target.stat().st_size == item["Size"]:
                    continue
                jobs.append((target.name, ["s3", "cp", f"s3://{args.bucket}/{item['Key']}", str(target)]))
            for name in ordered:
                jobs.append((name, ["s3", "sync", source + name + "/", str(destination / name)]))
            with (metadata / "transferencias.log").open("a", encoding="utf-8") as log:
                for stage, command in jobs:
                    print(f"Descargando {stage}...", flush=True)
                    log.write(f"\n{now()} {stage}\n")
                    log.flush()
                    child = subprocess.Popen(
                        base + command + ["--no-progress"], env=environment,
                        stdout=log, stderr=log, creationflags=creationflags,
                    )
                    try:
                        while child.poll() is None:
                            progress(inventory, destination, "descargando", stage, started_at)
                            try:
                                child.wait(timeout=10)
                            except subprocess.TimeoutExpired:
                                pass
                        if child.returncode:
                            raise RuntimeError(f"Fallo descargando {stage}; revisa transferencias.log.")
                    finally:
                        if child.poll() is None:
                            child.terminate()
                            try:
                                child.wait(timeout=10)
                            except subprocess.TimeoutExpired:
                                child.kill()
                                child.wait()
            current = progress(inventory, destination, "verificando", "final", started_at)
            if current["files_available"] != current["files_total"]:
                raise RuntimeError("Faltan archivos o sus tamanos no coinciden; vuelve a ejecutar el script.")
            progress(inventory, destination, "completado", "final", started_at)
            print("Descarga completa. Todos los archivos coinciden con los tamanos del inventario.", flush=True)
            return 0
        except (Exception, KeyboardInterrupt) as exc:
            message = "Descarga interrumpida; puedes volver a ejecutar el script." if isinstance(exc, KeyboardInterrupt) else str(exc)
            if inventory is not None:
                progress(inventory, destination, "interrumpido" if isinstance(exc, KeyboardInterrupt) else "error",
                         stage, started_at, message)
            else:
                write_json(metadata / "progreso.json", {"state": "error", "pid": os.getpid(),
                           "updated_at": now(), "error": message})
            print(message, file=sys.stderr, flush=True)
            return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
