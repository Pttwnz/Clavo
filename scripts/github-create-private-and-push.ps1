# Crea un repo PRIVADO en tu cuenta GitHub y hace push de la rama main (desde la raíz del monorepo Clavo).
#
# 1) Token: https://github.com/settings/personal-access-tokens — «repo» (classic) o permiso «Contents» read/write (fine-grained).
# 2) En PowerShell:
#    $env:GITHUB_TOKEN = "github_pat_...."
#    $env:GITHUB_OWNER = "tu_usuario"     # mismo usuario que posee el token
#    $env:GITHUB_REPO   = "Clavo"        # nombre del repo nuevo (minúsculas recomendadas)
#    .\scripts\github-create-private-and-push.ps1
#
# Si el repo ya existe, omite la creación y solo configura origin + push.

param(
    [string] $Owner = $env:GITHUB_OWNER,
    [string] $Repo = $env:GITHUB_REPO
)

$ErrorActionPreference = "Stop"
if (-not $env:GITHUB_TOKEN) { Write-Error "Define `$env:GITHUB_TOKEN (PAT con acceso a repos)." }
if (-not $Owner) { Write-Error "Define `$env:GITHUB_OWNER (tu usuario de GitHub)." }
if (-not $Repo) { Write-Error "Define `$env:GITHUB_REPO (nombre del repositorio)." }

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$headers = @{
    Authorization        = "Bearer $($env:GITHUB_TOKEN)"
    Accept               = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}
$createUri = "https://api.github.com/user/repos"
$body = @{ name = $Repo; private = $true; description = "Clavo — Taberna (Next + Gastro)" } | ConvertTo-Json

try {
    Invoke-RestMethod -Uri $createUri -Method Post -Headers $headers -Body $body -ContentType "application/json" | Out-Null
    Write-Host "Repositorio privado creado: https://github.com/$Owner/$Repo"
} catch {
    $code = $null
    if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
    if ($code -eq 422) {
        Write-Warning "El repo '$Repo' quizá ya existe (422). Se continúa con remote + push."
    } else {
        throw
    }
}

git remote remove origin 2>$null
git remote add origin "https://github.com/$Owner/$Repo.git"

$pushUrl = "https://x-access-token:$($env:GITHUB_TOKEN)@github.com/$Owner/$Repo.git"
Write-Host "git push (una vez con token; no se guarda el PAT en .git/config)..."
git push "$pushUrl" "main:main"
git branch --set-upstream-to=origin/main main

Write-Host ""
Write-Host "Listo. Repo privado: https://github.com/$Owner/$Repo"
Write-Host "Siguientes push: git push origin main (Git Credential Manager o SSH)."
