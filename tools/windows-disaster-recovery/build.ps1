[CmdletBinding()]
param(
    [ValidateSet("Release", "Debug")]
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$projectRoot = $PSScriptRoot
$repoRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot "..\.."))
$csc = "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\Roslyn\csc.exe"
$framework = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319"
if (-not (Test-Path -LiteralPath $csc -PathType Leaf)) { throw "csharp_compiler_not_found" }
if (-not (Test-Path -LiteralPath (Join-Path $framework "System.dll") -PathType Leaf)) { throw "net_framework_runtime_not_found" }
$bin = Join-Path $projectRoot "bin\$Configuration"
New-Item -ItemType Directory -Path $bin -Force | Out-Null
$dist = Join-Path $projectRoot "recovery-dist"
$helpers = Join-Path $dist "helpers"
New-Item -ItemType Directory -Path $helpers -Force | Out-Null
$exe = Join-Path $dist "NEXT-Stabil-Recovery.exe"
$sources = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot "src") -Filter "*.cs" | Sort-Object Name | ForEach-Object FullName)
$sources += Join-Path $projectRoot "Properties\AssemblyInfo.cs"
$references = @("System.dll", "System.Core.dll", "System.Drawing.dll", "System.Web.Extensions.dll", "System.Windows.Forms.dll") |
    ForEach-Object { "/reference:$([IO.Path]::Combine($framework, $_))" }
& $csc "/nologo" "/target:winexe" "/platform:anycpu" "/langversion:latest" "/deterministic+" `
    "/out:$exe" "/win32manifest:$([IO.Path]::Combine($projectRoot, 'app.manifest'))" @references @sources
if ($LASTEXITCODE -ne 0) { throw "recovery_build_failed:$LASTEXITCODE" }

$helperMap = [ordered]@{
    "restore-checkpoint.ps1" = "operations\hardening\restore-checkpoint.ps1"
    "backup-production.ps1" = "operations\hardening\backup-production.ps1"
    "verify-qdrant-snapshot-offline.ps1" = "operations\hardening\verify-qdrant-snapshot-offline.ps1"
    "qdrant_snapshot_validator.js" = "operations\supervisor\qdrant_snapshot_validator.js"
}
$records = @()
foreach ($name in $helperMap.Keys) {
    $source = Join-Path $repoRoot $helperMap[$name]
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "helper_missing:$name" }
    $target = Join-Path $helpers $name
    Copy-Item -LiteralPath $source -Destination $target -Force
    $records += [ordered]@{
        file = "helpers/$name"
        bytes = [int64](Get-Item -LiteralPath $target).Length
        sha256 = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
[ordered]@{
    schema = "NEXT_STABIL_RECOVERY_TOOL_V1"
    tool_version = "1.0.0"
    helpers = $records
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $dist "recovery-tool-manifest.json") -Encoding UTF8

$built = Get-Item -LiteralPath $exe
Write-Output "RECOVERY_EXE=$($built.FullName)"
Write-Output "RECOVERY_BYTES=$($built.Length)"
Write-Output "RECOVERY_SHA256=$((Get-FileHash -LiteralPath $built.FullName -Algorithm SHA256).Hash.ToLowerInvariant())"
