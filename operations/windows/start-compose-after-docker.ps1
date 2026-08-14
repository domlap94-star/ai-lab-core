$ErrorActionPreference = "Stop"

$repo = "C:\ai-lab-core"
$composeFile = "C:\ai-lab-core\compose.yaml"

Set-Location $repo

$dockerCommand = Get-Command docker.exe -ErrorAction Stop
$docker = $dockerCommand.Source

Write-Output "NEXT Stabil Docker bootstrap starting."

$dockerReady = $false

for ($i = 1; $i -le 120; $i++) {

    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    $versionRaw = @(
        & $docker info `
            --format "{{.ServerVersion}}" `
            2>$null
    )

    $code = $LASTEXITCODE

    $ErrorActionPreference = $oldEap

    if (
        $code -eq 0 -and
        $versionRaw.Count -gt 0
    ) {
        $version = (
            $versionRaw |
            ForEach-Object {
                $_.ToString()
            }
        ) -join ""

        Write-Output (
            "Docker Engine ready: {0}" -f
            $version
        )

        $dockerReady = $true
        break
    }

    Start-Sleep -Seconds 5
}

if (-not $dockerReady) {
    throw "Docker Engine did not become ready within 10 minutes."
}

Write-Output "Starting NEXT Stabil Compose services."

$oldEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"

$composeRaw = @(
    & $docker compose `
        -f $composeFile `
        up `
        -d `
        2>&1
)

$composeCode = $LASTEXITCODE

$ErrorActionPreference = $oldEap

foreach ($item in $composeRaw) {

    if ($item -is [System.Management.Automation.ErrorRecord]) {

        $message = $item.Exception.Message

        if (-not [string]::IsNullOrWhiteSpace($message)) {
            Write-Output $message
        }
    }
    else {
        $message = $item.ToString()

        if (-not [string]::IsNullOrWhiteSpace($message)) {
            Write-Output $message
        }
    }
}

if ($composeCode -ne 0) {
    throw (
        "docker compose up -d failed with exit code {0}" -f
        $composeCode
    )
}

Write-Output "Waiting for backend."

$backendReady = $false

for ($i = 1; $i -le 120; $i++) {

    try {
        $health = Invoke-RestMethod `
            -Uri "http://127.0.0.1:8000/health" `
            -TimeoutSec 5 `
            -ErrorAction Stop

        if ($health.status -eq "ok") {
            $backendReady = $true
            break
        }
    }
    catch {
    }

    Start-Sleep -Seconds 5
}

if (-not $backendReady) {
    throw "Backend did not become healthy within 10 minutes."
}

Write-Output "NEXT Stabil Docker bootstrap completed successfully."