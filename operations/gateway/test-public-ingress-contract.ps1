$ErrorActionPreference = "Stop"

function Require {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

$manifestPath = Join-Path $PSScriptRoot "public-ingress-manifest.json"
$checkPath = Join-Path $PSScriptRoot "check-public-ingress.ps1"
$reconcilePath = Join-Path $PSScriptRoot "reconcile-public-ingress.ps1"
$registerPath = Join-Path $PSScriptRoot "register-public-ingress-reconciliation.ps1"
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$check = Get-Content -LiteralPath $checkPath -Raw -Encoding UTF8
$reconcile = Get-Content -LiteralPath $reconcilePath -Raw -Encoding UTF8
$register = Get-Content -LiteralPath $registerPath -Raw -Encoding UTF8

Require ($manifest.public_origin -eq "https://domai.tail1927bd.ts.net") "origin"
Require ($manifest.public_https_port -eq 443) "port"
Require ($manifest.public_gateway.origin -eq "http://127.0.0.1:8789") "gateway"
Require ($manifest.public_control -eq "FORBIDDEN") "control"
Require ($manifest.private_services.supervisor -eq "http://127.0.0.1:8787") "supervisor"
Require ($manifest.tailnet_private_serve.reconciled_by_this_manifest -eq $false) "private_serve"
Require ($check -match 'UNEXPECTED_PUBLIC_FUNNEL_MAPPING') "unexpected_mapping_gate"
Require ($check -match 'PUBLIC_CONTROL_BOUNDARY_FAILED') "control_gate"
Require ($reconcile -match 'PUBLIC_INGRESS_CONFLICT_REQUIRES_OPERATOR_REVIEW') "conflict_gate"
Require ($reconcile -match 'funnel\s+`\s*--bg') "funnel_restore"
Require ($reconcile -notmatch 'serve\s+reset') "no_serve_reset"
Require ($reconcile -notmatch 'funnel\s+reset') "no_funnel_reset"
Require ($reconcile -notmatch '8787') "no_supervisor_exposure"
Require ($register -match 'RunLevel Highest') "elevated_task"
Require ($register -match 'PUBLIC_INGRESS_TASK_CONFLICT_REQUIRES_OPERATOR_REVIEW') "task_conflict"

Write-Output "PUBLIC_INGRESS_CONTRACT_TEST_PASS"
