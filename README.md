# Clavo (monorepo)

- **`restaurante/`** — web Next.js (pública, Prisma, recepción).
- **`restaurante/gastro-app/`** — panel Gastro (Flask), tablet, API de reservas.
- **`gerente/`** — PWA + API personal (pedidos a proveedores, tareas, resumen Telegram); puerto por defecto **37893** en `deploy/docker-compose.yml`.
- **`deploy/`** — Docker Compose para VPS: [deploy/README.md](deploy/README.md).

## Git y GitHub privado

El código vive en Git en esta carpeta. Para **crear un repo privado** en tu cuenta y subir `main` con un PAT:

```powershell
cd <ruta>\Clavo
$env:GITHUB_TOKEN = "…"; $env:GITHUB_OWNER = "…"; $env:GITHUB_REPO = "Clavo"
.\scripts\github-create-private-and-push.ps1
```

(Linux / Git Bash: `scripts/github-create-private-and-push.sh` con las mismas variables `GITHUB_*`.)

## Despliegue VPS

Ver [deploy/SUBIR-VPS.md](deploy/SUBIR-VPS.md) y [deploy/README.md](deploy/README.md) (incluye GitHub Actions y scripts `vps-remote-deploy`).
