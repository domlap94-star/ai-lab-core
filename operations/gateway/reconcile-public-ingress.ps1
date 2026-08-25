param(
    [string]$ManifestPath = (Join-Path $PSScriptRoot "public-ingress-manifest.json"),
    [string]$TailscalePath = "C:\Program Files\Tailscale\tailscale.exe"
)

$ErrorActionPreference = "Stop"

function Get-DynamicProperty {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Object,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }
    return $property.Value
}

function Get-FunnelConfiguration {
    $raw = @(& $TailscalePath funnel status --json 2>&1)
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "TAILSCALE_FUNNEL_STATUS_FAILED"
    }
    try {
        return (($raw | ForEach-Object { $_.ToString() }) -join "`n") |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "TAILSCALE_FUNNEL_STATUS_INVALID_JSON"
    }
}

if (-not (Test-Path -LiteralPath $TailscalePath -PathType Leaf)) {
    throw "TAILSCALE_EXECUTABLE_NOT_FOUND"
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 |
    ConvertFrom-Json -ErrorAction Stop
$portName = $manifest.public_https_port.ToString()
$authority = "{0}:{1}" -f ([Uri]$manifest.public_origin).DnsSafeHost, $portName
$expectedProxy = $manifest.public_gateway.origin
$configuration = Get-FunnelConfiguration

$allowedFunnelAuthorities = @(
    $configuration.AllowFunnel.PSObject.Properties |
    Where-Object { $_.Value -eq $true } |
    ForEach-Object { $_.Name }
)
$web = Get-DynamicProperty -Object $configuration.Web -Name $authority
$handler = $null
if ($null -ne $web -and $null -ne $web.Handlers) {
    $handler = Get-DynamicProperty -Object $web.Handlers -Name "/"
}
$tcp = Get-DynamicProperty -Object $configuration.TCP -Name $portName

$exactMappingPresent = (
    $null -ne $tcp -and
    $tcp.HTTPS -eq $true -and
    $null -ne $handler -and
    $handler.Proxy -eq $expectedProxy -and
    $allowedFunnelAuthorities.Count -eq 1 -and
    $allowedFunnelAuthorities[0] -eq $authority
)

if ($exactMappingPresent) {
    Write-Output "PUBLIC_INGRESS_RECONCILE_NOOP exact mapping already present"
}
else {
    $hasConflictingPort = $null -ne $tcp
    $hasConflictingWeb = $null -ne $web
    $hasAnyPublicFunnel = $allowedFunnelAuthorities.Count -gt 0
    if ($hasConflictingPort -or $hasConflictingWeb -or $hasAnyPublicFunnel) {
        throw "PUBLIC_INGRESS_CONFLICT_REQUIRES_OPERATOR_REVIEW"
    }

    $localHealth = Invoke-RestMethod `
        -Uri ("{0}{1}" -f $expectedProxy, $manifest.public_gateway.health_path) `
        -TimeoutSec 10 `
        -ErrorAction Stop
    if ($localHealth.gateway_online -ne $true) {
        throw "PUBLIC_GATEWAY_NOT_READY"
    }

    $restoreOutput = @(
        & $TailscalePath funnel `
            --bg `
            --https=$portName `
            --yes `
            $expectedProxy `
            2>&1
    )
    $restoreCode = $LASTEXITCODE
    if ($restoreCode -ne 0) {
        throw "PUBLIC_INGRESS_EXACT_RESTORE_FAILED"
    }
    Write-Output "PUBLIC_INGRESS_RESTORED exact approved mapping"
}

& (Join-Path $PSScriptRoot "check-public-ingress.ps1") `
    -ManifestPath $ManifestPath `
    -TailscalePath $TailscalePath
