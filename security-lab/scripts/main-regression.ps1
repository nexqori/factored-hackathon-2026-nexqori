$ErrorActionPreference = 'Stop'
$labRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $labRoot
$overridePath = Join-Path $labRoot '.local/main-rules.override.yaml'
New-Item -ItemType Directory -Force (Join-Path $labRoot '.local') | Out-Null
@'
services:
  api:
    environment:
      CHAT_AGENT_MODE: rules
      CHAT_AGENT_ALLOW_EXTERNAL_DATA: "false"
'@ | Set-Content -LiteralPath $overridePath -Encoding utf8
Push-Location $repoRoot
try {
    docker compose -f compose.yaml -f $overridePath up -d --no-deps --wait api
    if ($LASTEXITCODE -ne 0) { throw 'Could not start isolated rules configuration for UI regression.' }
    $env:NEXQORI_TEST_OUTPUT = 'security-lab/.local/main-ui-verification'
    npm run test:ui
    if ($LASTEXITCODE -ne 0) { throw 'Main UI regression failed.' }
} finally {
    Remove-Item Env:NEXQORI_TEST_OUTPUT -ErrorAction SilentlyContinue
    docker compose -f compose.yaml up -d --no-deps --wait api
    Pop-Location
}
