Set-Location (Join-Path $PSScriptRoot "..")
.\tools\cloudflared.exe tunnel --url http://127.0.0.1:8000 *> logs\cloudflared.log
