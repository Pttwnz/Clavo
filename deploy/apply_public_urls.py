#!/usr/bin/env python3
"""
Aplica URLs públicas (DNS) en deploy/.env y opcionalmente rebuild de Docker.

Ejecutar EN EL VPS, desde la raíz del repo (donde está la carpeta deploy/):

  # Dos dominios (app + clavo):
  python3 deploy/apply_public_urls.py https://app.gastromanager.es \\
    --auth-url https://clavo.gastromanager.es --rebuild

  # Un solo dominio (Next / + Gastro /panel… vía Nginx, ver nginx-elclavo-gastromanager.conf.example):
  python3 deploy/apply_public_urls.py https://elclavo.gastromanager.es \\
    --merged-host-root --legacy-host 178.104.143.67:37892 --rebuild

Si antes usabas IP en NEXT_PUBLIC_GASTRO_BASE_URL, se rellena solo GASTRO_LEGACY_HOSTS
salvo que pases --legacy-host 178.104.143.67:37892
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def _detect_legacy_from_gastro_url(current: str) -> str | None:
    s = (current or "").strip().strip('"').strip("'")
    m = re.match(r"^https?://(?P<h>\d{1,3}(?:\.\d{1,3}){3}):(?P<p>\d+)/?$", s)
    if m:
        return f"{m.group('h')}:{m.group('p')}"
    return None


def _merge_env_file(path: Path, patch: dict[str, str]) -> None:
    keys = set(patch)
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k = line.split("=", 1)[0].strip()
                if k in keys:
                    continue
            lines.append(line)
    for k, v in patch.items():
        lines.append(f"{k}={v}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="DNS público para Next + Gastro (deploy/.env)")
    p.add_argument("gastro_url", help="URL pública de Gastro, ej. https://app.gastromanager.es")
    p.add_argument(
        "--auth-url",
        dest="auth_url",
        default="",
        help="URL pública de la web Next (Auth), ej. https://clavo.gastromanager.es",
    )
    p.add_argument(
        "--legacy-host",
        dest="legacy_host",
        default="",
        help="Host:puerto desde el que redirigir al DNS (ej. 178.104.143.67:37892). Si se omite y el .env tenía IP, se infiere.",
    )
    p.add_argument(
        "--merged-host-root",
        action="store_true",
        dest="merged_host_root",
        help="FLASK_MERGED_HOST_ROOT=1 (mismo FQDN: Nginx enruta / a Next y /panel, /login, /tablet/* a Gastro).",
    )
    p.add_argument(
        "--rebuild",
        action="store_true",
        help="Tras escribir .env: docker compose build web gastro && up -d",
    )
    args = p.parse_args()

    gastro = args.gastro_url.strip().rstrip("/")
    if not gastro.lower().startswith(("http://", "https://")):
        print("gastro_url debe empezar por http:// o https://", file=sys.stderr)
        return 2

    deploy_dir = Path(__file__).resolve().parent
    env_path = deploy_dir / ".env"
    example = deploy_dir / "env.example"

    if not env_path.is_file():
        if example.is_file():
            env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"Creado {env_path} desde env.example — revisa AUTH_SECRET y demás claves.")
        else:
            print(f"No existe {env_path} ni env.example.", file=sys.stderr)
            return 1

    prev: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", k):
                prev[k] = v

    legacy = (args.legacy_host or "").strip()
    if not legacy:
        legacy = _detect_legacy_from_gastro_url(prev.get("NEXT_PUBLIC_GASTRO_BASE_URL", "")) or ""

    patch: dict[str, str] = {
        "NEXT_PUBLIC_GASTRO_BASE_URL": gastro,
        "TRUST_PROXY": "1",
    }
    if gastro.lower().startswith("https://"):
        patch["FLASK_SECURE_COOKIES"] = "1"

    if args.auth_url.strip():
        patch["AUTH_URL"] = args.auth_url.strip().rstrip("/")
    elif args.merged_host_root:
        patch["AUTH_URL"] = gastro

    if args.merged_host_root:
        patch["FLASK_MERGED_HOST_ROOT"] = "1"

    if legacy:
        patch["GASTRO_LEGACY_HOSTS"] = legacy

    _merge_env_file(env_path, patch)
    print(f"Actualizado {env_path}")
    print(f"  NEXT_PUBLIC_GASTRO_BASE_URL={gastro}")
    if "AUTH_URL" in patch:
        print(f"  AUTH_URL={patch['AUTH_URL']}")
    if legacy:
        print(f"  GASTRO_LEGACY_HOSTS={legacy}")
    print("  TRUST_PROXY=1")
    if "FLASK_SECURE_COOKIES" in patch:
        print("  FLASK_SECURE_COOKIES=1")
    if args.merged_host_root:
        print("  FLASK_MERGED_HOST_ROOT=1")

    if args.rebuild:
        print("Ejecutando docker compose build web gastro && up -d …")
        subprocess.run(
            ["docker", "compose", "build", "web", "gastro"],
            cwd=str(deploy_dir),
            check=True,
        )
        subprocess.run(
            ["docker", "compose", "up", "-d", "web", "gastro"],
            cwd=str(deploy_dir),
            check=True,
        )
        print("Listo. Prueba el panel por la URL con DNS (Ctrl+F5).")
    else:
        print("Sin --rebuild: ejecuta en deploy/: docker compose build web gastro && docker compose up -d web gastro")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
