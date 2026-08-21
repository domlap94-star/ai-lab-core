[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$csc = "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\Roslyn\csc.exe"
$framework = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319"
$out = Join-Path $root "bin\tests\Recovery.Tests.dll"
New-Item -ItemType Directory -Path (Split-Path -Parent $out) -Force | Out-Null
$sources = @(
    (Join-Path $root "src\Models.cs"), (Join-Path $root "src\CheckpointValidator.cs"),
    (Join-Path $root "src\ConfirmationPolicy.cs"), (Join-Path $root "src\HelperIntegrity.cs"),
    (Join-Path $root "tests\TestRunner.cs")
)
$references = @("System.dll", "System.Core.dll", "System.Web.Extensions.dll") | ForEach-Object { "/reference:$([IO.Path]::Combine($framework, $_))" }
& $csc "/nologo" "/target:library" "/platform:anycpu" "/langversion:latest" "/out:$out" @references @sources
if ($LASTEXITCODE -ne 0) { throw "recovery_test_build_failed" }
$csi = "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\Roslyn\csi.exe"
if (-not (Test-Path -LiteralPath $csi -PathType Leaf)) { throw "csharp_interactive_not_found" }
Push-Location $root
try {
    & $csi "tests\run.csx"
    if ($LASTEXITCODE -ne 0) { throw "recovery_unit_tests_failed" }
}
finally { Pop-Location }
