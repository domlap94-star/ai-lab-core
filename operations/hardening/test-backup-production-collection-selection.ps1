[CmdletBinding(DefaultParameterSetName = "Path")]
param(
    [Parameter(ParameterSetName = "Path")]
    [string]$ScriptPath = "",

    [Parameter(Mandatory = $true, ParameterSetName = "Base64")]
    [string]$ScriptTextBase64,

    [Parameter(Mandatory = $true, ParameterSetName = "Stdin")]
    [switch]$ReadFromStdin,

    [switch]$ExpectFailBefore
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

if ($PSCmdlet.ParameterSetName -eq "Base64") {
    $source = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($ScriptTextBase64))
} elseif ($PSCmdlet.ParameterSetName -eq "Stdin") {
    $source = [Console]::In.ReadToEnd()
} else {
    if ([string]::IsNullOrWhiteSpace($ScriptPath)) {
        $ScriptPath = Join-Path $PSScriptRoot "backup-production.ps1"
    }
    $source = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $ScriptPath).Path)
}

$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$parseErrors)
if (@($parseErrors).Count -ne 0) {
    throw "production_script_parse_failed: $($parseErrors[0].Message)"
}

$safeNameFunction = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq "Get-SafeQdrantCollectionName"
}, $true))
$selectionAssignment = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.AssignmentStatementAst] -and
        $node.Left.Extent.Text -match '\$selectedCollections$'
}, $true))
$nextAssignment = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.AssignmentStatementAst] -and
        $node.Left.Extent.Text -eq '$legacyDocumentSources'
}, $true))

if ($safeNameFunction.Count -ne 1 -or $selectionAssignment.Count -ne 1 -or $nextAssignment.Count -ne 1) {
    throw "production_selection_ast_not_unique"
}

$selectionText = $source.Substring(
    $selectionAssignment[0].Extent.StartOffset,
    $nextAssignment[0].Extent.StartOffset - $selectionAssignment[0].Extent.StartOffset
)
$harness = @"
Set-StrictMode -Version 2.0
$($safeNameFunction[0].Extent.Text)
function Get-BoundedJsonObject { [pscustomobject]@{ schema = 'NEXT_STABIL_RUNTIME_INVENTORY_V1'; contains_secret_values = `$false } }
$selectionText
[pscustomobject]@{
    is_array = (`$selectedCollections -is [array])
    element_type = `$selectedCollections.GetType().GetElementType().FullName
    count = @(`$selectedCollections).Count
    items = @(`$selectedCollections)
}
"@
$selectionScript = [scriptblock]::Create($harness)

function Invoke-SelectionCase {
    param(
        [string]$Name,
        [string[]]$Collections,
        [string]$DefaultCollection,
        [string]$Manifest,
        [string]$ExpectedError = ""
    )

    $QdrantCollections = $Collections
    $QdrantCollection = $DefaultCollection
    $ManifestFormat = $Manifest
    $Scope = "full"
    $QdrantProofMode = "CaptureOnly"
    $RuntimeInventoryPath = $PSCommandPath
    try {
        $result = & $selectionScript
        if (-not [string]::IsNullOrWhiteSpace($ExpectedError)) {
            throw "${Name}: expected_error_not_raised:$ExpectedError"
        }
        return $result
    } catch {
        if (-not [string]::IsNullOrWhiteSpace($ExpectedError) -and $_.Exception.Message -eq $ExpectedError) {
            return $ExpectedError
        }
        throw
    }
}

if ($ExpectFailBefore) {
    try {
        $null = Invoke-SelectionCase -Name "default_legacy" -Collections @() -DefaultCollection "ai_lab_document_chunks" -Manifest "LegacyV1"
        throw "fail_before_not_reproduced"
    } catch {
        if ($_.FullyQualifiedErrorId -notmatch "PropertyNotFoundStrict" -and
            $_.Exception.Message -notmatch "property 'Count' cannot be found") {
            throw
        }
        Write-Output "FAIL_BEFORE_PROPERTY_NOT_FOUND_STRICT"
        exit 0
    }
}

$legacyDefault = Invoke-SelectionCase -Name "default_legacy" -Collections @() -DefaultCollection "ai_lab_document_chunks" -Manifest "LegacyV1"
if ($legacyDefault.is_array -ne $true -or $legacyDefault.element_type -ne "System.String" -or
    $legacyDefault.count -ne 1 -or $legacyDefault.items[0] -ne "ai_lab_document_chunks") {
    throw "default_legacy_contract_failed"
}

$explicitOne = Invoke-SelectionCase -Name "explicit_one" -Collections @("ai_lab_document_chunks") -DefaultCollection "unused" -Manifest "LegacyV1"
if ($explicitOne.is_array -ne $true -or $explicitOne.element_type -ne "System.String" -or $explicitOne.count -ne 1) {
    throw "explicit_one_contract_failed"
}

$recovery = Invoke-SelectionCase -Name "recovery_two" -Collections @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks") -DefaultCollection "unused" -Manifest "RecoveryPointV2"
if ($recovery.is_array -ne $true -or $recovery.element_type -ne "System.String" -or $recovery.count -ne 2 -or
    "ai_lab_document_chunks" -notin $recovery.items -or "ai_lab_knowledge_base_chunks" -notin $recovery.items) {
    throw "recovery_two_contract_failed"
}

$null = Invoke-SelectionCase -Name "duplicate" -Collections @("ai_lab_document_chunks", "ai_lab_document_chunks") -DefaultCollection "unused" -Manifest "RecoveryPointV2" -ExpectedError "qdrant_collection_duplicate"
$null = Invoke-SelectionCase -Name "invalid" -Collections @("not/valid") -DefaultCollection "unused" -Manifest "LegacyV1" -ExpectedError "qdrant_collection_name_invalid"
$null = Invoke-SelectionCase -Name "legacy_two" -Collections @("ai_lab_document_chunks", "ai_lab_knowledge_base_chunks") -DefaultCollection "unused" -Manifest "LegacyV1" -ExpectedError "legacy_manifest_requires_one_qdrant_collection"
$null = Invoke-SelectionCase -Name "recovery_missing" -Collections @("ai_lab_document_chunks") -DefaultCollection "unused" -Manifest "RecoveryPointV2" -ExpectedError "recovery_point_v2_required_collections_missing"

Write-Output "PASS_BACKUP_COLLECTION_SELECTION_PS51 cases=7 parser_errors=0"
