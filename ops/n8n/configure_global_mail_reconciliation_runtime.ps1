param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$GmailCredentialId,
    [string]$GmailCredentialName = "Gmail account"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$templatePath = Join-Path $PSScriptRoot "global_mail_reconciliation_adapter.workflow.json"
$envPath = Join-Path $repoRoot ".env"

if (-not (Test-Path -LiteralPath $templatePath)) {
    throw "Reconciliation workflow template is missing."
}

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Runtime .env file is missing."
}

$bytes = New-Object byte[] 48
$generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $generator.GetBytes($bytes)
}
finally {
    $generator.Dispose()
}
$secret = [Convert]::ToBase64String($bytes)

$credentialId = "Ch10MailReconSecret26"
$workflowId = "Ch10MailRecon2026"
$credentialName = "AI Lab Mail Reconciliation Webhook Secret"
$workflowName = "AI Lab Global Mail Reconciliation Adapter"

$temporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) (
    "ai-lab-mail-reconcile-" + [Guid]::NewGuid().ToString("N")
)
[System.IO.Directory]::CreateDirectory($temporaryDirectory) | Out-Null
$credentialPath = Join-Path $temporaryDirectory "credential.json"
$workflowPath = Join-Path $temporaryDirectory "workflow.json"

try {
    $credential = @(
        [ordered]@{
            id = $credentialId
            name = $credentialName
            type = "httpHeaderAuth"
            data = [ordered]@{
                name = "X-AI-Lab-Mail-Reconcile-Secret"
                value = $secret
            }
        }
    )
    ConvertTo-Json -InputObject $credential -Depth 8 | Set-Content -LiteralPath $credentialPath -Encoding UTF8

    $workflow = Get-Content -LiteralPath $templatePath -Raw | ConvertFrom-Json
    $workflow | Add-Member -NotePropertyName id -NotePropertyValue $workflowId -Force
    $workflow.active = $false
    $workflow.meta.templateOnly = $false
    foreach ($node in $workflow.nodes) {
        if ($node.credentials.httpHeaderAuth) {
            $node.credentials.httpHeaderAuth.id = $credentialId
            $node.credentials.httpHeaderAuth.name = $credentialName
        }
        if ($node.credentials.gmailOAuth2) {
            $node.credentials.gmailOAuth2.id = $GmailCredentialId
            $node.credentials.gmailOAuth2.name = $GmailCredentialName
        }
    }
    ConvertTo-Json -InputObject @($workflow) -Depth 100 | Set-Content -LiteralPath $workflowPath -Encoding UTF8

    & docker compose cp $credentialPath "n8n:/tmp/ai-lab-mail-reconcile-credential.json"
    if ($LASTEXITCODE -ne 0) { throw "Credential copy failed." }
    & docker compose exec -T n8n n8n import:credentials --input=/tmp/ai-lab-mail-reconcile-credential.json
    if ($LASTEXITCODE -ne 0) { throw "Credential import failed." }

    & docker compose cp $workflowPath "n8n:/tmp/ai-lab-mail-reconcile-workflow.json"
    if ($LASTEXITCODE -ne 0) { throw "Workflow copy failed." }
    & docker compose exec -T n8n n8n import:workflow --input=/tmp/ai-lab-mail-reconcile-workflow.json
    if ($LASTEXITCODE -ne 0) { throw "Workflow import failed." }
    & docker compose exec -T n8n n8n update:workflow --id=$workflowId --active=true
    if ($LASTEXITCODE -ne 0) { throw "Workflow activation failed." }

    $environment = [System.IO.File]::ReadAllText($envPath)
    $settings = [ordered]@{
        "MAIL_RECONCILE_WEBHOOK_URL" = "http://n8n:5678/webhook/ai-lab-global-mail-reconcile-v1"
        "MAIL_RECONCILE_WEBHOOK_SECRET" = $secret
        "MAIL_RECONCILE_TIMEOUT_SECONDS" = "120"
    }
    foreach ($entry in $settings.GetEnumerator()) {
        $escapedKey = [Regex]::Escape($entry.Key)
        $line = $entry.Key + "=" + $entry.Value
        if ($environment -match "(?m)^$escapedKey=") {
            $environment = [Regex]::Replace(
                $environment,
                "(?m)^$escapedKey=.*$",
                $line
            )
        }
        else {
            if (-not $environment.EndsWith("`n")) { $environment += "`r`n" }
            $environment += $line + "`r`n"
        }
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($envPath, $environment, $utf8)

    Write-Output ("workflow_id=" + $workflowId)
    Write-Output ("workflow_name=" + $workflowName)
    Write-Output "credential_configured=True"
    Write-Output "runtime_env_configured=True"
    Write-Output "secret_output=False"
}
finally {
    & docker compose exec -T n8n rm -f /tmp/ai-lab-mail-reconcile-credential.json /tmp/ai-lab-mail-reconcile-workflow.json 2>$null
    if ((Resolve-Path -LiteralPath $temporaryDirectory).Path.StartsWith([System.IO.Path]::GetTempPath())) {
        Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
    }
    $secret = $null
}
