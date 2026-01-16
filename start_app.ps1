# Script de lancement de l'application TourGuide Paris
# S'assure que la clé API OpenRouter est configurée

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "🗼 TourGuide Paris - Démarrage" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Vérifier la clé API
if (-not $env:OPENROUTER_API_KEY) {
    Write-Host "⚠️  OPENROUTER_API_KEY non définie!" -ForegroundColor Yellow
    Write-Host "`nPour la définir, exécute dans ton terminal :" -ForegroundColor Yellow
    Write-Host '  $env:OPENROUTER_API_KEY="sk-or-v1-..."' -ForegroundColor Green
    Write-Host "`nPuis relance ce script.`n" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Clé API détectée : $($env:OPENROUTER_API_KEY.Substring(0,20))..." -ForegroundColor Green

# Activer l'environnement virtuel si nécessaire
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "✓ Activation de l'environnement virtuel..." -ForegroundColor Green
    & .\.venv\Scripts\Activate.ps1
}

Write-Host "`n🚀 Lancement du serveur..`n" -ForegroundColor Cyan

# Lancer l'application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
