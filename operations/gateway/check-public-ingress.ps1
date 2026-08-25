param(
    [string]$ManifestPath = (Join-Path $PSScriptRoot "public-ingress-manifest.json"),
    [string]$TailscalePath = "C:\Program Files\Tailscale\tailscale.exe"
)

$ErrorActionPreference = "Stop"

function Invoke-NoProxyHttp {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri
    )

    Add-Type -AssemblyName System.Net.Http
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.UseProxy = $false
    $handler.AllowAutoRedirect = $false
    $client = New-Object System.Net.Http.HttpClient($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(20)

    try {
        $response = $client.GetAsync($Uri).GetAwaiter().GetResult()
        return [int]$response.StatusCode
    }
    finally {
        $client.Dispose()
        $handler.Dispose()
    }
}

function Get-FunnelConfiguration {
    if (-not (Test-Path -LiteralPath $TailscalePath -PathType Leaf)) {
        throw "TAILSCALE_EXECUTABLE_NOT_FOUND"
    }

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

$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 |
    ConvertFrom-Json -ErrorAction Stop

if ($manifest.schema_version -ne 1) {
    throw "PUBLIC_INGRESS_MANIFEST_VERSION_UNSUPPORTED"
}
if ($manifest.public_control -ne "FORBIDDEN") {
    throw "PUBLIC_CONTROL_POLICY_INVALID"
}

$portName = $manifest.public_https_port.ToString()
$authority = "{0}:{1}" -f ([Uri]$manifest.public_origin).DnsSafeHost, $portName
$expectedProxy = $manifest.public_gateway.origin
$configuration = Get-FunnelConfiguration

$tcp = Get-DynamicProperty -Object $configuration.TCP -Name $portName
if ($null -eq $tcp -or $tcp.HTTPS -ne $true) {
    throw "PUBLIC_INGRESS_HTTPS_PORT_MISSING"
}

$web = Get-DynamicProperty -Object $configuration.Web -Name $authority
$handler = $null
if ($null -ne $web -and $null -ne $web.Handlers) {
    $handler = Get-DynamicProperty -Object $web.Handlers -Name "/"
}
if ($null -eq $handler -or $handler.Proxy -ne $expectedProxy) {
    throw "PUBLIC_INGRESS_PROXY_MISMATCH"
}

$allowedFunnelAuthorities = @(
    $configuration.AllowFunnel.PSObject.Properties |
    Where-Object { $_.Value -eq $true } |
    ForEach-Object { $_.Name }
)
if (
    $allowedFunnelAuthorities.Count -ne 1 -or
    $allowedFunnelAuthorities[0] -ne $authority
) {
    throw "UNEXPECTED_PUBLIC_FUNNEL_MAPPING"
}

$localGatewayHealth = Invoke-NoProxyHttp (
    "{0}{1}" -f
    $manifest.public_gateway.origin,
    $manifest.public_gateway.health_path
)
if ($localGatewayHealth -ne 200) {
    throw "PUBLIC_GATEWAY_LOCAL_HEALTH_FAILED"
}

$publicHealth = Invoke-NoProxyHttp (
    "{0}/health" -f $manifest.public_origin
)
if ($publicHealth -ne 200) {
    throw "PUBLIC_INGRESS_HEALTH_FAILED"
}

foreach ($path in $manifest.forbidden_public_paths) {
    $status = Invoke-NoProxyHttp ("{0}{1}" -f $manifest.public_origin, $path)
    if ($status -ne 404) {
        throw "PUBLIC_CONTROL_BOUNDARY_FAILED"
    }
}

Write-Output (
    "PUBLIC_INGRESS_CHECK_PASS origin={0} target={1} control=404" -f
    $manifest.public_origin,
    $expectedProxy
)
