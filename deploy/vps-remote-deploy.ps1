# Desde Windows: delega en Git Bash / WSL el script deploy/vps-remote-deploy.sh
#
#   $env:VPS_SSH = "root@203.0.113.10"
#   $env:VPS_REPO_PATH = "/root/Clavo"   # opcional
#   .\deploy\vps-remote-deploy.ps1
#   .\deploy\vps-remote-deploy.ps1 master
#
param(
    [Parameter(Position = 0)]
    [string] $Branch = "main"
)
$ErrorActionPreference = "Stop"
if (-not $env:VPS_SSH) {
    Write-Error "Define `$env:VPS_SSH (ej. root@TU_IP)"
}
$sh = Join-Path $PSScriptRoot "vps-remote-deploy.sh"
if (-not (Test-Path $sh)) {
    Write-Error "No se encuentra $sh"
}
$bash = Get-Command bash -ErrorAction SilentlyContinue
if (-not $bash) {
    Write-Error "No hay 'bash' en PATH. Instala Git for Windows (Git Bash) o ejecuta a mano: bash deploy/vps-remote-deploy.sh $Branch"
}
& bash $sh $Branch
