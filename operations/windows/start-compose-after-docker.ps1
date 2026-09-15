[CmdletBinding()]
param([switch]$ImportDefinitionsOnly)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$runtimeHelper = Join-Path (Split-Path -Parent $PSScriptRoot) "runtime\startup-runtime.ps1"
. $runtimeHelper

function Invoke-ApprovedExistingContainerPhase {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object[]]$ExpectedContainers,
        [Parameter(Mandatory = $true)]$Adapters,
        [Parameter(Mandatory = $true)][int]$CommandTimeoutMilliseconds
    )
    return Invoke-StartupExistingContainerPhase `
        -ExpectedContainers $ExpectedContainers `
        -Adapters $Adapters `
        -CommandTimeoutMilliseconds $CommandTimeoutMilliseconds
}

if (-not $ImportDefinitionsOnly) {
    throw "START_REFUSED: this internal existing-resource-only stage cannot be executed directly. Use the approved single-start entrypoint."
}
