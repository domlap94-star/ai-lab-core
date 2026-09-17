Set-StrictMode -Version 2.0

$script:NextStabilStartupSchema = "NEXT_STABIL_STARTUP_SET_V1"
$script:NextStabilComponentIdentitySchema = "NEXT_STABIL_COMPONENT_COMPATIBILITY_V1"
$script:NextStabilDataTopologySchema = "NEXT_STABIL_DATA_TOPOLOGY_V1"
$script:NextStabilStartupPackageSchema = "NEXT_STABIL_STARTUP_PACKAGE_V1"
$script:NextStabilCanonicalRoot = "C:\ai-lab-core"
$script:NextStabilCanonicalDataPath = "C:\ai-lab-core\data"
$script:NextStabilCanonicalDataTarget = "D:\ai-lab-data"

function Get-StartupProperty {
    param(
        [Parameter(Mandatory = $true)]$InputObject,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if ($null -eq $InputObject) {
        return $null
    }
    $matches = @($InputObject.PSObject.Properties | Where-Object { $_.Name -ceq $Name })
    if ($matches.Count -eq 0) {
        return $null
    }
    return $matches[0].Value
}

function Test-StartupProperty {
    param(
        [AllowNull()]$InputObject,
        [Parameter(Mandatory = $true)][string]$Name
    )
    if ($null -eq $InputObject) { return $false }
    return @($InputObject.PSObject.Properties | Where-Object { $_.Name -ceq $Name }).Count -eq 1
}

function ConvertTo-StartupUtcTimestamp {
    param([AllowNull()]$Value)

    if ($null -eq $Value) {
        return [pscustomobject]@{ valid = $false; value = ''; source_type = 'MISSING' }
    }
    try {
        if ($Value -is [datetime]) {
            return [pscustomobject]@{ valid = $true; value = ([datetime]$Value).ToUniversalTime().ToString('o'); source_type = 'DATETIME' }
        }
        if ($Value -is [datetimeoffset]) {
            return [pscustomobject]@{ valid = $true; value = ([datetimeoffset]$Value).UtcDateTime.ToString('o'); source_type = 'DATETIMEOFFSET' }
        }
        $text = ([string]$Value).Trim()
        if ($text -match '^\d{14}\.\d{6}[+-]\d{3}$') {
            $converted = [System.Management.ManagementDateTimeConverter]::ToDateTime($text)
            return [pscustomobject]@{ valid = $true; value = $converted.ToUniversalTime().ToString('o'); source_type = 'DMTF' }
        }
        $parsed = [datetime]::MinValue
        if ([datetime]::TryParse(
            $text,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::AssumeUniversal -bor [System.Globalization.DateTimeStyles]::AdjustToUniversal,
            [ref]$parsed
        )) {
            return [pscustomobject]@{ valid = $true; value = $parsed.ToUniversalTime().ToString('o'); source_type = 'ISO_TEXT' }
        }
    }
    catch {
    }
    return [pscustomobject]@{ valid = $false; value = ''; source_type = 'INVALID' }
}

function Get-StartupRemainingMilliseconds {
    param(
        [Parameter(Mandatory = $true)][int64]$Deadline,
        [Parameter(Mandatory = $true)][int]$MaximumMilliseconds
    )
    $remaining = $Deadline - (Get-MonotonicMilliseconds)
    if ($remaining -le 0) { return 0 }
    return [int][Math]::Min([int64]$MaximumMilliseconds, $remaining)
}

function ConvertTo-SafeStartupDiagnostic {
    param(
        [AllowNull()][object]$Value,
        [int]$MaximumCharacters = 2048
    )

    $text = if ($null -eq $Value) { "" } else { [string]$Value }
    $text = $text -replace '(?i)\b(authorization|password|passwd|token|secret|api[_-]?key|client[_-]?secret)\s*[:=]\s*([^\s,;]+)', '$1=[REDACTED]'
    $text = $text -replace '(?i)(https?://)[^/@\s]+@', '$1[REDACTED]@'
    if ($MaximumCharacters -lt 0) {
        $MaximumCharacters = 0
    }
    if ($text.Length -gt $MaximumCharacters) {
        return $text.Substring(0, $MaximumCharacters) + "...[TRUNCATED]"
    }
    return $text
}

function ConvertTo-WindowsNativeArgument {
    param([AllowEmptyString()][string]$Value)

    if ($Value.Length -eq 0) {
        return '""'
    }
    if ($Value -notmatch '[\s"]') {
        return $Value
    }

    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $backslashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') {
            $backslashes++
            continue
        }
        if ($character -eq '"') {
            if ($backslashes -gt 0) {
                [void]$builder.Append(('\' * ($backslashes * 2)))
            }
            [void]$builder.Append('\"')
            $backslashes = 0
            continue
        }
        if ($backslashes -gt 0) {
            [void]$builder.Append(('\' * $backslashes))
            $backslashes = 0
        }
        [void]$builder.Append($character)
    }
    if ($backslashes -gt 0) {
        [void]$builder.Append(('\' * ($backslashes * 2)))
    }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Join-WindowsNativeArguments {
    param([string[]]$ArgumentList = @())

    return (($ArgumentList | ForEach-Object {
        ConvertTo-WindowsNativeArgument -Value ([string]$_)
    }) -join ' ')
}

function Add-BoundedText {
    param(
        [Parameter(Mandatory = $true)][System.Text.StringBuilder]$Builder,
        [AllowNull()][string]$Text,
        [int]$MaximumCharacters
    )

    if ([string]::IsNullOrEmpty($Text) -or $Builder.Length -ge $MaximumCharacters) {
        return
    }
    $remaining = $MaximumCharacters - $Builder.Length
    if ($Text.Length -le $remaining) {
        [void]$Builder.Append($Text)
    }
    else {
        [void]$Builder.Append($Text.Substring(0, $remaining))
    }
}

function Invoke-BoundedNativeCommand {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$WorkingDirectory = "",
        [ValidateRange(1, 3600000)][int]$TimeoutMilliseconds = 20000,
        [ValidateRange(256, 1048576)][int]$MaximumOutputCharacters = 32768
    )

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $process = New-Object System.Diagnostics.Process
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $FilePath
    $startInfo.Arguments = Join-WindowsNativeArguments -ArgumentList $ArgumentList
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
        $startInfo.WorkingDirectory = $WorkingDirectory
    }
    $process.StartInfo = $startInfo

    $started = $false
    $timedOut = $false
    $processLeftRunning = $false
    $pidValue = $null
    $startTicks = $null
    $stdout = New-Object System.Text.StringBuilder
    $stderr = New-Object System.Text.StringBuilder
    $stdoutTruncated = $false
    $stderrTruncated = $false

    try {
        try {
            $started = $process.Start()
            if (-not $started) {
                throw "Process.Start returned false."
            }
            $pidValue = $process.Id
            $startTicks = $process.StartTime.ToUniversalTime().Ticks
        }
        catch {
            return [pscustomobject][ordered]@{
                status = "START_FAILED"
                started = $false
                timed_out = $false
                exit_code = $null
                pid = $null
                process_left_running = $false
                duration_ms = [int]$stopwatch.ElapsedMilliseconds
                stdout = ""
                stderr = ConvertTo-SafeStartupDiagnostic -Value $_.Exception.Message -MaximumCharacters $MaximumOutputCharacters
                stdout_truncated = $false
                stderr_truncated = $false
            }
        }

        $stdoutBuffer = New-Object char[] 4096
        $stderrBuffer = New-Object char[] 4096
        $stdoutTask = $process.StandardOutput.ReadAsync($stdoutBuffer, 0, $stdoutBuffer.Length)
        $stderrTask = $process.StandardError.ReadAsync($stderrBuffer, 0, $stderrBuffer.Length)
        $stdoutEnded = $false
        $stderrEnded = $false

        while (-not ($process.HasExited -and $stdoutEnded -and $stderrEnded)) {
            if ($null -ne $stdoutTask -and $stdoutTask.IsCompleted) {
                $count = $stdoutTask.Result
                if ($count -eq 0) {
                    $stdoutEnded = $true
                    $stdoutTask = $null
                }
                else {
                    $chunk = -join $stdoutBuffer[0..($count - 1)]
                    if ($stdout.Length + $chunk.Length -gt $MaximumOutputCharacters) {
                        $stdoutTruncated = $true
                    }
                    Add-BoundedText -Builder $stdout -Text $chunk -MaximumCharacters $MaximumOutputCharacters
                    $stdoutBuffer = New-Object char[] 4096
                    $stdoutTask = $process.StandardOutput.ReadAsync($stdoutBuffer, 0, $stdoutBuffer.Length)
                }
            }
            if ($null -ne $stderrTask -and $stderrTask.IsCompleted) {
                $count = $stderrTask.Result
                if ($count -eq 0) {
                    $stderrEnded = $true
                    $stderrTask = $null
                }
                else {
                    $chunk = -join $stderrBuffer[0..($count - 1)]
                    if ($stderr.Length + $chunk.Length -gt $MaximumOutputCharacters) {
                        $stderrTruncated = $true
                    }
                    Add-BoundedText -Builder $stderr -Text $chunk -MaximumCharacters $MaximumOutputCharacters
                    $stderrBuffer = New-Object char[] 4096
                    $stderrTask = $process.StandardError.ReadAsync($stderrBuffer, 0, $stderrBuffer.Length)
                }
            }

            if ($stopwatch.ElapsedMilliseconds -ge $TimeoutMilliseconds) {
                if (-not $process.HasExited) {
                    $timedOut = $true
                    try {
                        if (
                            $process.Id -eq $pidValue -and
                            $process.StartTime.ToUniversalTime().Ticks -eq $startTicks -and
                            -not $process.HasExited
                        ) {
                            $process.Kill()
                        }
                    }
                    catch {
                        $processLeftRunning = -not $process.HasExited
                        Add-BoundedText -Builder $stderr -Text ("process_cleanup_failed: " + $_.Exception.Message) -MaximumCharacters $MaximumOutputCharacters
                    }
                }
                break
            }
            Start-Sleep -Milliseconds 5
        }

        if ($timedOut -and -not $processLeftRunning) {
            try {
                [void]$process.WaitForExit(1000)
            }
            catch {
            }
            $processLeftRunning = -not $process.HasExited
        }

        $drainDeadline = [System.Diagnostics.Stopwatch]::StartNew()
        while (
            -not ($stdoutEnded -and $stderrEnded) -and
            $drainDeadline.ElapsedMilliseconds -lt 1000
        ) {
            if ($null -ne $stdoutTask -and $stdoutTask.IsCompleted) {
                $count = $stdoutTask.Result
                if ($count -eq 0) {
                    $stdoutEnded = $true
                    $stdoutTask = $null
                }
                else {
                    $chunk = -join $stdoutBuffer[0..($count - 1)]
                    if ($stdout.Length + $chunk.Length -gt $MaximumOutputCharacters) {
                        $stdoutTruncated = $true
                    }
                    Add-BoundedText -Builder $stdout -Text $chunk -MaximumCharacters $MaximumOutputCharacters
                    $stdoutBuffer = New-Object char[] 4096
                    $stdoutTask = $process.StandardOutput.ReadAsync($stdoutBuffer, 0, $stdoutBuffer.Length)
                }
            }
            if ($null -ne $stderrTask -and $stderrTask.IsCompleted) {
                $count = $stderrTask.Result
                if ($count -eq 0) {
                    $stderrEnded = $true
                    $stderrTask = $null
                }
                else {
                    $chunk = -join $stderrBuffer[0..($count - 1)]
                    if ($stderr.Length + $chunk.Length -gt $MaximumOutputCharacters) {
                        $stderrTruncated = $true
                    }
                    Add-BoundedText -Builder $stderr -Text $chunk -MaximumCharacters $MaximumOutputCharacters
                    $stderrBuffer = New-Object char[] 4096
                    $stderrTask = $process.StandardError.ReadAsync($stderrBuffer, 0, $stderrBuffer.Length)
                }
            }
            Start-Sleep -Milliseconds 5
        }

        $exitCode = if ($process.HasExited) { $process.ExitCode } else { $null }
        $safeOut = ConvertTo-SafeStartupDiagnostic -Value $stdout.ToString() -MaximumCharacters $MaximumOutputCharacters
        $safeErr = ConvertTo-SafeStartupDiagnostic -Value $stderr.ToString() -MaximumCharacters $MaximumOutputCharacters
        $status = if ($timedOut) {
            "TIMEOUT"
        }
        elseif ($null -eq $exitCode) {
            "UNKNOWN"
        }
        elseif ($exitCode -ne 0) {
            "NONZERO_EXIT"
        }
        elseif ([string]::IsNullOrWhiteSpace($safeOut) -and [string]::IsNullOrWhiteSpace($safeErr)) {
            "EMPTY_OUTPUT"
        }
        else {
            "SUCCESS"
        }

        return [pscustomobject][ordered]@{
            status = $status
            started = $started
            timed_out = $timedOut
            exit_code = $exitCode
            pid = $pidValue
            process_left_running = $processLeftRunning
            duration_ms = [int]$stopwatch.ElapsedMilliseconds
            stdout = $safeOut
            stderr = $safeErr
            stdout_truncated = $stdoutTruncated
            stderr_truncated = $stderrTruncated
        }
    }
    finally {
        $process.Dispose()
    }
}

function Get-MonotonicMilliseconds {
    return [int64](([System.Diagnostics.Stopwatch]::GetTimestamp() * 1000.0) / [System.Diagnostics.Stopwatch]::Frequency)
}

function Get-CanonicalStartupPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $pathRoot = [System.IO.Path]::GetPathRoot($fullPath)
    if ($fullPath.Equals($pathRoot, [System.StringComparison]::OrdinalIgnoreCase)) { return $pathRoot }
    return $fullPath.TrimEnd('\', '/')
}

function Test-StartupPathWithinRoot {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Candidate
    )

    try {
        $canonicalRoot = Get-CanonicalStartupPath -Path $Root
        $canonicalCandidate = Get-CanonicalStartupPath -Path $Candidate
    }
    catch {
        return $false
    }
    if ($canonicalCandidate.Equals($canonicalRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    $prefix = if ($canonicalRoot.EndsWith([string][System.IO.Path]::DirectorySeparatorChar)) {
        $canonicalRoot
    }
    else {
        $canonicalRoot + [System.IO.Path]::DirectorySeparatorChar
    }
    return $canonicalCandidate.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-StartupPathHasReparsePoint {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Candidate
    )

    $canonicalRoot = Get-CanonicalStartupPath -Path $Root
    $canonicalCandidate = Get-CanonicalStartupPath -Path $Candidate
    if (-not (Test-StartupPathWithinRoot -Root $canonicalRoot -Candidate $canonicalCandidate)) {
        return $true
    }
    $current = $canonicalCandidate
    while (Test-StartupPathWithinRoot -Root $canonicalRoot -Candidate $current) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                return $true
            }
        }
        if ($current.Equals($canonicalRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            break
        }
        $parent = Split-Path -Parent $current
        if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $current) {
            break
        }
        $current = $parent
    }
    return $false
}

function ConvertTo-StartupLocalLinkTarget {
    param([AllowNull()]$Value)

    $targets = @($Value | Where-Object { $null -ne $_ -and -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($targets.Count -ne 1) { return $null }
    $text = ([string]$targets[0]).Trim().Replace('/', '\')
    if ($text.StartsWith('\??\UNC\', [System.StringComparison]::OrdinalIgnoreCase) -or
        $text.StartsWith('\\?\UNC\', [System.StringComparison]::OrdinalIgnoreCase) -or
        $text.StartsWith('\\')) { return $null }
    if ($text.StartsWith('\??\', [System.StringComparison]::OrdinalIgnoreCase) -or
        $text.StartsWith('\\?\', [System.StringComparison]::OrdinalIgnoreCase)) { $text = $text.Substring(4) }
    if (-not [System.IO.Path]::IsPathRooted($text)) { return $null }
    try { return Get-CanonicalStartupPath -Path $text } catch { return $null }
}

function Get-StartupDirectoryLinkMetadata {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        if (-not (Test-Path -LiteralPath $Path -PathType Container)) { return [pscustomobject]@{ status = 'MISSING'; link_type = ''; target = '' } }
        $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0) { return [pscustomobject]@{ status = 'PRESENT'; link_type = 'DIRECTORY'; target = '' } }
        $linkTypeProperty = @($item.PSObject.Properties | Where-Object { $_.Name -ceq 'LinkType' })
        $targetProperty = @($item.PSObject.Properties | Where-Object { $_.Name -ceq 'Target' })
        if ($linkTypeProperty.Count -ne 1 -or $targetProperty.Count -ne 1) { return [pscustomobject]@{ status = 'UNKNOWN'; link_type = ''; target = '' } }
        $normalizedTarget = ConvertTo-StartupLocalLinkTarget -Value $targetProperty[0].Value
        if ($null -eq $normalizedTarget) { return [pscustomobject]@{ status = 'UNKNOWN'; link_type = [string]$linkTypeProperty[0].Value; target = '' } }
        return [pscustomobject]@{ status = 'PRESENT'; link_type = ([string]$linkTypeProperty[0].Value).ToUpperInvariant(); target = $normalizedTarget }
    }
    catch { return [pscustomobject]@{ status = 'UNKNOWN'; link_type = ''; target = '' } }
}

function Test-StartupPathReparseChain {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Candidate,
        [AllowEmptyString()][string]$AllowedReparsePath = ''
    )

    try {
        $canonicalRoot = Get-CanonicalStartupPath -Path $Root
        $canonicalCandidate = Get-CanonicalStartupPath -Path $Candidate
        $canonicalAllowed = if ([string]::IsNullOrWhiteSpace($AllowedReparsePath)) { '' } else { Get-CanonicalStartupPath -Path $AllowedReparsePath }
    }
    catch { return [pscustomobject]@{ valid = $false; code = 'PATH_INVALID'; path = $Candidate } }
    if (-not (Test-StartupPathWithinRoot -Root $canonicalRoot -Candidate $canonicalCandidate)) { return [pscustomobject]@{ valid = $false; code = 'PATH_OUTSIDE_ROOT'; path = $canonicalCandidate } }
    $current = $canonicalCandidate
    while (Test-StartupPathWithinRoot -Root $canonicalRoot -Candidate $current) {
        try {
            if (-not (Test-Path -LiteralPath $current)) { return [pscustomobject]@{ valid = $false; code = 'PATH_MISSING'; path = $current } }
            $item = Get-Item -LiteralPath $current -Force -ErrorAction Stop
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -and
                ([string]::IsNullOrWhiteSpace($canonicalAllowed) -or -not $current.Equals($canonicalAllowed, [System.StringComparison]::OrdinalIgnoreCase))) {
                return [pscustomobject]@{ valid = $false; code = 'UNEXPECTED_REPARSE_POINT'; path = $current }
            }
        }
        catch { return [pscustomobject]@{ valid = $false; code = 'PATH_METADATA_UNKNOWN'; path = $current } }
        if ($current.Equals($canonicalRoot, [System.StringComparison]::OrdinalIgnoreCase)) { break }
        $parent = Split-Path -Parent $current
        if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $current) { return [pscustomobject]@{ valid = $false; code = 'PATH_PARENT_INVALID'; path = $current } }
        $current = $parent
    }
    return [pscustomobject]@{ valid = $true; code = 'OK'; path = $canonicalCandidate }
}

function Test-StartupDataTopology {
    param(
        [AllowNull()]$Topology,
        [Parameter(Mandatory = $true)][string]$CanonicalRoot,
        [switch]$AllowSyntheticRoot
    )

    $errors = New-Object System.Collections.Generic.List[string]
    $approvedBindings = [System.Collections.Generic.Dictionary[string,object]]::new([System.StringComparer]::Ordinal)
    if ($null -eq $Topology) { return [pscustomobject]@{ valid = $true; errors = @(); logical_path = ''; target = ''; approved_bindings = $approvedBindings } }
    if ((Get-StartupProperty -InputObject $Topology -Name 'schema') -ne $script:NextStabilDataTopologySchema) { $errors.Add('DATA_TOPOLOGY_SCHEMA_UNSUPPORTED') }
    if ((Get-StartupProperty -InputObject $Topology -Name 'purpose') -ne 'ACTIVE_DATA_ONLY') { $errors.Add('DATA_TOPOLOGY_PURPOSE_INVALID') }
    if ((Get-StartupProperty -InputObject $Topology -Name 'link_type') -ne 'DIRECTORY_JUNCTION') { $errors.Add('DATA_TOPOLOGY_LINK_TYPE_INVALID') }

    $logicalText = [string](Get-StartupProperty -InputObject $Topology -Name 'logical_path')
    $targetText = [string](Get-StartupProperty -InputObject $Topology -Name 'target')
    if ([string]::IsNullOrWhiteSpace($logicalText)) { $logicalPath = ''; $errors.Add('DATA_TOPOLOGY_LOGICAL_PATH_INVALID') }
    else { try { $logicalPath = Get-CanonicalStartupPath -Path $logicalText } catch { $logicalPath = ''; $errors.Add('DATA_TOPOLOGY_LOGICAL_PATH_INVALID') } }
    if ([string]::IsNullOrWhiteSpace($targetText)) { $targetPath = ''; $errors.Add('DATA_TOPOLOGY_TARGET_INVALID') }
    else { try { $targetPath = Get-CanonicalStartupPath -Path $targetText } catch { $targetPath = ''; $errors.Add('DATA_TOPOLOGY_TARGET_INVALID') } }
    $expectedLogicalPath = Get-CanonicalStartupPath -Path (Join-Path $CanonicalRoot 'data')
    if (-not [string]::IsNullOrWhiteSpace($logicalPath) -and -not $logicalPath.Equals($expectedLogicalPath, [System.StringComparison]::OrdinalIgnoreCase)) { $errors.Add('DATA_TOPOLOGY_LOGICAL_PATH_MISMATCH') }
    if (-not $AllowSyntheticRoot) {
        if (-not $logicalPath.Equals($script:NextStabilCanonicalDataPath, [System.StringComparison]::OrdinalIgnoreCase)) { $errors.Add('DATA_TOPOLOGY_CANONICAL_PATH_MISMATCH') }
        if (-not $targetPath.Equals($script:NextStabilCanonicalDataTarget, [System.StringComparison]::OrdinalIgnoreCase)) { $errors.Add('DATA_TOPOLOGY_CANONICAL_TARGET_MISMATCH') }
    }
    if (-not [string]::IsNullOrWhiteSpace($targetPath) -and ($targetPath.StartsWith('\\') -or -not [System.IO.Path]::IsPathRooted($targetPath))) { $errors.Add('DATA_TOPOLOGY_TARGET_NOT_LOCAL') }

    if (-not [string]::IsNullOrWhiteSpace($logicalPath) -and -not [string]::IsNullOrWhiteSpace($targetPath)) {
        $logicalChain = Test-StartupPathReparseChain -Root $CanonicalRoot -Candidate $logicalPath -AllowedReparsePath $logicalPath
        if (-not $logicalChain.valid) { $errors.Add(('DATA_TOPOLOGY_LOGICAL_CHAIN_{0}' -f $logicalChain.code)) }
        $link = Get-StartupDirectoryLinkMetadata -Path $logicalPath
        if ($link.status -ne 'PRESENT') { $errors.Add(('DATA_TOPOLOGY_LINK_{0}' -f $link.status)) }
        elseif ($link.link_type -ne 'JUNCTION') { $errors.Add('DATA_TOPOLOGY_NOT_DIRECTORY_JUNCTION') }
        elseif (-not ([string]$link.target).Equals($targetPath, [System.StringComparison]::OrdinalIgnoreCase)) { $errors.Add('DATA_TOPOLOGY_JUNCTION_TARGET_MISMATCH') }
        $targetRoot = [System.IO.Path]::GetPathRoot($targetPath)
        if ([string]::IsNullOrWhiteSpace($targetRoot)) { $errors.Add('DATA_TOPOLOGY_TARGET_ROOT_INVALID') }
        else {
            $targetChain = Test-StartupPathReparseChain -Root $targetRoot -Candidate $targetPath
            if (-not $targetChain.valid) { $errors.Add(('DATA_TOPOLOGY_TARGET_CHAIN_{0}' -f $targetChain.code)) }
        }
    }

    $bindingContracts = @(
        [pscustomobject]@{ service = 'backend'; role = 'APPLICATION_DATA'; destination = '/data' },
        [pscustomobject]@{ service = 'postgres'; role = 'POSTGRESQL_DATA'; destination = '/var/lib/postgresql/data' },
        [pscustomobject]@{ service = 'n8n'; role = 'N8N_DATA'; destination = '/home/node/.n8n' },
        [pscustomobject]@{ service = 'open-webui'; role = 'OPENWEBUI_DATA'; destination = '/app/backend/data' },
        [pscustomobject]@{ service = 'ollama'; role = 'OLLAMA_DATA'; destination = '/root/.ollama' }
    )
    $allowedRoles = @($bindingContracts | ForEach-Object { $_.role })
    $bindings = @(Get-StartupProperty -InputObject $Topology -Name 'bindings')
    if ($bindings.Count -eq 0) { $errors.Add('DATA_TOPOLOGY_BINDINGS_MISSING') }
    foreach ($binding in $bindings) {
        $service = [string](Get-StartupProperty -InputObject $binding -Name 'service')
        $role = [string](Get-StartupProperty -InputObject $binding -Name 'role')
        $sourceText = [string](Get-StartupProperty -InputObject $binding -Name 'source')
        $destination = [string](Get-StartupProperty -InputObject $binding -Name 'destination')
        try { $source = Get-CanonicalStartupPath -Path $sourceText } catch { $source = ''; $errors.Add("DATA_BINDING_SOURCE_INVALID:$service") }
        if ([string]::IsNullOrWhiteSpace($service)) { $errors.Add('DATA_BINDING_SERVICE_INVALID') }
        if ($role -notin $allowedRoles) { $errors.Add("DATA_BINDING_ROLE_INVALID:$service") }
        if ([string]::IsNullOrWhiteSpace($destination) -or -not $destination.StartsWith('/')) { $errors.Add("DATA_BINDING_DESTINATION_INVALID:$service") }
        $matchingContracts = @($bindingContracts | Where-Object {
            $_.service.Equals($service, [System.StringComparison]::Ordinal) -and
            $_.role.Equals($role, [System.StringComparison]::Ordinal) -and
            $_.destination.Equals($destination, [System.StringComparison]::Ordinal)
        })
        if ($matchingContracts.Count -ne 1) { $errors.Add("DATA_BINDING_CONTRACT_MISMATCH:$service") }
        if (-not [string]::IsNullOrWhiteSpace($source) -and -not [string]::IsNullOrWhiteSpace($logicalPath)) {
            if (-not (Test-StartupPathWithinRoot -Root $logicalPath -Candidate $source)) { $errors.Add("DATA_BINDING_SOURCE_OUTSIDE_DATA:$service") }
            else {
                $sourceChain = Test-StartupPathReparseChain -Root $CanonicalRoot -Candidate $source -AllowedReparsePath $logicalPath
                if (-not $sourceChain.valid) { $errors.Add(('DATA_BINDING_LOGICAL_CHAIN_{0}:{1}' -f $sourceChain.code, $service)) }
                $relative = if ($source.Equals($logicalPath, [System.StringComparison]::OrdinalIgnoreCase)) { '' } else { $source.Substring($logicalPath.Length).TrimStart('\') }
                $mappedTarget = if ([string]::IsNullOrWhiteSpace($relative)) { $targetPath } else { Join-Path $targetPath $relative }
                if (-not [string]::IsNullOrWhiteSpace($targetPath)) {
                    $targetRoot = [System.IO.Path]::GetPathRoot($targetPath)
                    $mappedChain = Test-StartupPathReparseChain -Root $targetRoot -Candidate $mappedTarget
                    if (-not $mappedChain.valid) { $errors.Add(('DATA_BINDING_TARGET_CHAIN_{0}:{1}' -f $mappedChain.code, $service)) }
                }
            }
        }
        $key = ('{0}|{1}|{2}' -f $service.ToLowerInvariant(), $source.ToLowerInvariant(), $destination)
        if ($approvedBindings.ContainsKey($key)) { $errors.Add("DATA_BINDING_DUPLICATE:$service") } else { $approvedBindings[$key] = $binding }
    }
    return [pscustomobject]@{ valid = ($errors.Count -eq 0); errors = $errors.ToArray(); logical_path = $logicalPath; target = $targetPath; approved_bindings = $approvedBindings }
}

function Get-StartupSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $stream = [System.IO.File]::OpenRead($Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToUpperInvariant()
    }
    finally {
        $sha.Dispose()
        $stream.Dispose()
    }
}

function Test-StartupSha256Value {
    param([AllowNull()][object]$Value)
    return ($Value -is [string] -and ([string]$Value) -match '^[0-9A-Fa-f]{64}$')
}

function Test-StartupImageIdentity {
    param([AllowNull()][object]$Value)
    return ($Value -is [string] -and ([string]$Value) -match '^sha256:[0-9A-Fa-f]{64}$')
}

function Test-StartupContainerId {
    param([AllowNull()][object]$Value)
    return ($Value -is [string] -and ([string]$Value) -match '^[0-9A-Fa-f]{64}$')
}

function ConvertFrom-StartupDockerVersionResponse {
    param([AllowNull()][object]$Value)
    $text = if ($null -eq $Value) { '' } else { ([string]$Value).Trim() }
    if ([string]::IsNullOrWhiteSpace($text)) { return [pscustomobject]@{ valid = $false; code = 'EMPTY_OUTPUT'; version = $null } }
    if ($text -notmatch '^[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[-+][0-9A-Za-z.-]+)?$') {
        return [pscustomobject]@{ valid = $false; code = 'INVALID_FORMAT'; version = $null }
    }
    return [pscustomobject]@{ valid = $true; code = 'OK'; version = $text }
}

function Test-StartupSetManifest {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)][string]$ManifestPath,
        [Parameter(Mandatory = $true)][string]$ExpectedRoot,
        [switch]$AllowSyntheticRoot
    )

    $errors = New-Object System.Collections.Generic.List[string]
    $schema = Get-StartupProperty -InputObject $Manifest -Name 'schema'
    $identitySchema = Get-StartupProperty -InputObject $Manifest -Name 'component_identity_schema'
    $packageSchema = Get-StartupProperty -InputObject $Manifest -Name 'startup_package_schema'
    $isPinnedStartupPackage = ($packageSchema -eq $script:NextStabilStartupPackageSchema)
    $setId = Get-StartupProperty -InputObject $Manifest -Name 'set_id'
    $rootValue = Get-StartupProperty -InputObject $Manifest -Name 'root'
    $approval = Get-StartupProperty -InputObject $Manifest -Name 'approval'

    if ($schema -ne $script:NextStabilStartupSchema) { $errors.Add('MANIFEST_SCHEMA_UNSUPPORTED') }
    if ($identitySchema -ne $script:NextStabilComponentIdentitySchema) { $errors.Add('COMPONENT_IDENTITY_SCHEMA_UNSUPPORTED') }
    if ($null -ne $packageSchema -and -not [string]::IsNullOrWhiteSpace([string]$packageSchema) -and -not $isPinnedStartupPackage) { $errors.Add('STARTUP_PACKAGE_SCHEMA_UNSUPPORTED') }
    if (-not ($setId -is [string]) -or $setId -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$') { $errors.Add('SET_ID_INVALID') }
    if (-not ($rootValue -is [string]) -or [string]::IsNullOrWhiteSpace([string]$rootValue)) {
        $errors.Add('ROOT_INVALID')
        $canonicalRoot = $null
    }
    else {
        try { $canonicalRoot = Get-CanonicalStartupPath -Path ([string]$rootValue) } catch { $canonicalRoot = $null; $errors.Add('ROOT_INVALID') }
    }
    try { $canonicalExpectedRoot = Get-CanonicalStartupPath -Path $ExpectedRoot } catch { $canonicalExpectedRoot = $ExpectedRoot }
    if ($null -ne $canonicalRoot -and -not $canonicalRoot.Equals($canonicalExpectedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        $errors.Add('ROOT_MISMATCH')
    }
    if (-not $AllowSyntheticRoot -and $null -ne $canonicalRoot) {
        if (-not $canonicalRoot.Equals($script:NextStabilCanonicalRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            $errors.Add('RUNTIME_ROOT_NOT_CANONICAL')
        }
        if ($canonicalRoot -match '(?i)(^|[\\-])(recovery|staging|test)([\\-]|$)') {
            $errors.Add('RUNTIME_ROOT_FORBIDDEN')
        }
    }
    if ($null -ne $canonicalRoot) {
        if (-not (Test-StartupPathWithinRoot -Root $canonicalRoot -Candidate $ManifestPath)) {
            $errors.Add('MANIFEST_OUTSIDE_ROOT')
        }
        elseif (Test-StartupPathHasReparsePoint -Root $canonicalRoot -Candidate $ManifestPath) {
            $errors.Add('MANIFEST_REPARSE_POINT')
        }
    }

    $dataTopology = if ($null -eq $canonicalRoot) {
        [pscustomobject]@{ valid = $false; errors = @('DATA_TOPOLOGY_ROOT_UNAVAILABLE'); logical_path = ''; target = ''; approved_bindings = @{} }
    }
    else {
        Test-StartupDataTopology -Topology (Get-StartupProperty -InputObject $Manifest -Name 'data_topology') -CanonicalRoot $canonicalRoot -AllowSyntheticRoot:$AllowSyntheticRoot
    }
    foreach ($dataError in @($dataTopology.errors)) { $errors.Add([string]$dataError) }

    $approvalStatus = Get-StartupProperty -InputObject $approval -Name 'status'
    $approvalSetId = Get-StartupProperty -InputObject $approval -Name 'set_id'
    $decisionId = Get-StartupProperty -InputObject $approval -Name 'decision_id'
    if ($approvalStatus -ne 'APPROVED_FOR_START') { $errors.Add('START_NOT_APPROVED') }
    if ($approvalSetId -ne $setId) { $errors.Add('APPROVAL_SET_MISMATCH') }
    if (-not ($decisionId -is [string]) -or [string]::IsNullOrWhiteSpace([string]$decisionId)) { $errors.Add('APPROVAL_DECISION_MISSING') }

    $timeouts = Get-StartupProperty -InputObject $Manifest -Name 'timeouts'
    foreach ($timeoutName in @('native_command_ms', 'engine_stage_ms', 'service_stage_ms', 'poll_ms', 'max_output_chars')) {
        $value = Get-StartupProperty -InputObject $timeouts -Name $timeoutName
        if (-not ($value -is [int]) -and -not ($value -is [long])) {
            $errors.Add("TIMEOUT_INVALID:$timeoutName")
        }
        elseif ([int64]$value -le 0) {
            $errors.Add("TIMEOUT_INVALID:$timeoutName")
        }
    }

    $files = @(Get-StartupProperty -InputObject $Manifest -Name 'files')
    $requiredFileRoles = @('compose_config', 'compose_helper', 'public_gateway_script', 'private_gateway_script', 'supervisor_script')
    if ($isPinnedStartupPackage) {
        $requiredFileRoles += @('startup_launcher', 'startup_runtime', 'backend_override')
    }
    $seenFileRoles = @{}
    foreach ($file in $files) {
        if ($null -eq $file) { continue }
        $role = [string](Get-StartupProperty -InputObject $file -Name 'role')
        $relativePath = [string](Get-StartupProperty -InputObject $file -Name 'path')
        $expectedHash = Get-StartupProperty -InputObject $file -Name 'sha256'
        if ([string]::IsNullOrWhiteSpace($role) -or $seenFileRoles.ContainsKey($role)) {
            $errors.Add("FILE_ROLE_INVALID:$role")
            continue
        }
        $seenFileRoles[$role] = $file
        if ([System.IO.Path]::IsPathRooted($relativePath) -or [string]::IsNullOrWhiteSpace($relativePath)) {
            $errors.Add("FILE_PATH_INVALID:$role")
            continue
        }
        if ($null -eq $canonicalRoot) { continue }
        $fullPath = [System.IO.Path]::GetFullPath((Join-Path $canonicalRoot $relativePath))
        if (-not (Test-StartupPathWithinRoot -Root $canonicalRoot -Candidate $fullPath)) {
            $errors.Add("FILE_OUTSIDE_ROOT:$role")
            continue
        }
        if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
            $errors.Add("FILE_MISSING:$role")
            continue
        }
        if (Test-StartupPathHasReparsePoint -Root $canonicalRoot -Candidate $fullPath) {
            $errors.Add("FILE_REPARSE_POINT:$role")
            continue
        }
        if (-not (Test-StartupSha256Value -Value $expectedHash)) {
            $errors.Add("FILE_HASH_INVALID:$role")
            continue
        }
        if ((Get-StartupSha256 -Path $fullPath) -ne ([string]$expectedHash).ToUpperInvariant()) {
            $errors.Add("FILE_HASH_MISMATCH:$role")
        }
    }
    foreach ($role in $requiredFileRoles) {
        if (-not $seenFileRoles.ContainsKey($role)) { $errors.Add("FILE_ROLE_MISSING:$role") }
    }

    $tools = @(Get-StartupProperty -InputObject $Manifest -Name 'external_tools')
    $seenTools = @{}
    foreach ($tool in $tools) {
        if ($null -eq $tool) { continue }
        $name = [string](Get-StartupProperty -InputObject $tool -Name 'name')
        $path = [string](Get-StartupProperty -InputObject $tool -Name 'path')
        $hash = Get-StartupProperty -InputObject $tool -Name 'sha256'
        if ([string]::IsNullOrWhiteSpace($name) -or $seenTools.ContainsKey($name)) {
            $errors.Add("TOOL_NAME_INVALID:$name")
            continue
        }
        $seenTools[$name] = $tool
        if (-not [System.IO.Path]::IsPathRooted($path) -or -not (Test-Path -LiteralPath $path -PathType Leaf)) {
            $errors.Add("TOOL_PATH_INVALID:$name")
            continue
        }
        if (-not (Test-StartupSha256Value -Value $hash)) {
            $errors.Add("TOOL_HASH_INVALID:$name")
            continue
        }
        if ((Get-StartupSha256 -Path $path) -ne ([string]$hash).ToUpperInvariant()) {
            $errors.Add("TOOL_HASH_MISMATCH:$name")
        }
        if (-not [string]::IsNullOrWhiteSpace([string]$dataTopology.logical_path) -and
            -not [string]::IsNullOrWhiteSpace([string]$dataTopology.target) -and
            ((Test-StartupPathWithinRoot -Root ([string]$dataTopology.logical_path) -Candidate $path) -or
             (Test-StartupPathWithinRoot -Root ([string]$dataTopology.target) -Candidate $path))) {
            $errors.Add("TOOL_PATH_USES_ACTIVE_DATA:$name")
        }
    }
    foreach ($requiredTool in @('docker_cli', 'docker_desktop', 'node')) {
        if (-not $seenTools.ContainsKey($requiredTool)) { $errors.Add("TOOL_MISSING:$requiredTool") }
    }

    $docker = Get-StartupProperty -InputObject $Manifest -Name 'docker'
    foreach ($name in @('context', 'endpoint', 'process_name', 'cli_tool', 'desktop_tool')) {
        $value = Get-StartupProperty -InputObject $docker -Name $name
        if (-not ($value -is [string]) -or [string]::IsNullOrWhiteSpace([string]$value)) { $errors.Add("DOCKER_FIELD_INVALID:$name") }
    }
    if ((Get-StartupProperty -InputObject $docker -Name 'cli_tool') -ne 'docker_cli') { $errors.Add('DOCKER_CLI_TOOL_INVALID') }
    if ((Get-StartupProperty -InputObject $docker -Name 'desktop_tool') -ne 'docker_desktop') { $errors.Add('DOCKER_DESKTOP_TOOL_INVALID') }

    $containers = @(Get-StartupProperty -InputObject $Manifest -Name 'containers')
    $containerNames = @{}
    $containerOrders = @{}
    $matchedDataBindings = @{}
    if ($containers.Count -eq 0) { $errors.Add('CONTAINERS_MISSING') }
    foreach ($container in $containers) {
        if ($null -eq $container) { continue }
        $service = [string](Get-StartupProperty -InputObject $container -Name 'service')
        if ([string]::IsNullOrWhiteSpace($service) -or $containerNames.ContainsKey($service)) {
            $errors.Add("CONTAINER_SERVICE_INVALID:$service")
            continue
        }
        $containerNames[$service] = $true
        foreach ($name in @('container_name', 'compose_project')) {
            $value = Get-StartupProperty -InputObject $container -Name $name
            if (-not ($value -is [string]) -or [string]::IsNullOrWhiteSpace([string]$value)) {
                $errors.Add(('CONTAINER_FIELD_INVALID:{0}:{1}' -f $service, $name))
            }
        }
        $containerId = Get-StartupProperty -InputObject $container -Name 'container_id'
        if ($isPinnedStartupPackage -or $null -ne $containerId) {
            if (-not (Test-StartupContainerId -Value $containerId)) { $errors.Add("CONTAINER_ID_INVALID:$service") }
        }
        if (-not (Test-StartupImageIdentity -Value (Get-StartupProperty -InputObject $container -Name 'image_id'))) { $errors.Add("CONTAINER_IMAGE_INVALID:$service") }
        $identityMode = [string](Get-StartupProperty -InputObject $container -Name 'image_identity_mode')
        if ([string]::IsNullOrWhiteSpace($identityMode)) { $identityMode = 'REPO_DIGEST' }
        if ($identityMode -eq 'REPO_DIGEST') {
            if (-not (Test-StartupImageIdentity -Value (Get-StartupProperty -InputObject $container -Name 'repo_digest'))) { $errors.Add("CONTAINER_DIGEST_INVALID:$service") }
        }
        elseif ($identityMode -eq 'LOCAL_IMAGE_ID_CONFIRMED_NO_REPO_DIGEST') {
            if ($service -ne 'backend') { $errors.Add("CONTAINER_LOCAL_IMAGE_MODE_FORBIDDEN:$service") }
            if ([string](Get-StartupProperty -InputObject $container -Name 'repo_digest') -ne 'CONFIRMED_ABSENT') { $errors.Add("CONTAINER_LOCAL_IMAGE_ABSENCE_MARKER_INVALID:$service") }
        }
        else {
            $errors.Add("CONTAINER_IMAGE_IDENTITY_MODE_INVALID:$service")
        }
        if ($isPinnedStartupPackage) {
            $startupOrder = Get-StartupProperty -InputObject $container -Name 'startup_order'
            if ((-not ($startupOrder -is [int]) -and -not ($startupOrder -is [long])) -or [int64]$startupOrder -le 0 -or $containerOrders.ContainsKey([string]$startupOrder)) {
                $errors.Add("CONTAINER_STARTUP_ORDER_INVALID:$service")
            }
            else {
                $containerOrders[[string]$startupOrder] = $service
            }
            $healthRequirement = [string](Get-StartupProperty -InputObject $container -Name 'health_requirement')
            if ($healthRequirement -notin @('RUNNING', 'HEALTHY')) { $errors.Add("CONTAINER_HEALTH_REQUIREMENT_INVALID:$service") }
        }
        $containerMounts = @(Get-StartupProperty -InputObject $container -Name 'mounts')
        if ($containerMounts.Count -eq 0) { $errors.Add("CONTAINER_MOUNTS_MISSING:$service") }
        foreach ($mount in $containerMounts) {
            $mountType = [string](Get-StartupProperty -InputObject $mount -Name 'type')
            $mountSource = [string](Get-StartupProperty -InputObject $mount -Name 'source')
            $mountDestination = [string](Get-StartupProperty -InputObject $mount -Name 'destination')
            if ($mountType -notin @('bind', 'volume') -or [string]::IsNullOrWhiteSpace($mountSource) -or [string]::IsNullOrWhiteSpace($mountDestination)) { $errors.Add("CONTAINER_MOUNT_INVALID:$service"); continue }
            if ($mountType -eq 'bind') {
                if ($null -eq $canonicalRoot -or -not (Test-StartupPathWithinRoot -Root $canonicalRoot -Candidate $mountSource)) { $errors.Add("CONTAINER_BIND_OUTSIDE_ROOT:$service") }
                elseif (Test-StartupPathHasReparsePoint -Root $canonicalRoot -Candidate $mountSource) {
                    try { $canonicalMountSource = Get-CanonicalStartupPath -Path $mountSource } catch { $canonicalMountSource = '' }
                    $bindingKey = ('{0}|{1}|{2}' -f $service.ToLowerInvariant(), $canonicalMountSource.ToLowerInvariant(), $mountDestination)
                    if (-not $dataTopology.valid -or -not $dataTopology.approved_bindings.ContainsKey($bindingKey)) {
                        $errors.Add("CONTAINER_BIND_REPARSE_POINT:$service")
                    }
                    else {
                        $matchedDataBindings[$bindingKey] = $true
                    }
                }
            }
        }
        foreach ($port in @(Get-StartupProperty -InputObject $container -Name 'ports')) {
            if ((Get-StartupProperty -InputObject $port -Name 'host_ip') -ne '127.0.0.1') { $errors.Add("CONTAINER_PORT_NOT_LOOPBACK:$service") }
        }
    }
    if ($isPinnedStartupPackage) {
        foreach ($container in $containers) {
            if ($null -eq $container) { continue }
            $service = [string](Get-StartupProperty -InputObject $container -Name 'service')
            foreach ($dependency in @(Get-StartupProperty -InputObject $container -Name 'depends_on_healthy')) {
                $dependencyName = [string]$dependency
                if ([string]::IsNullOrWhiteSpace($dependencyName) -or -not $containerNames.ContainsKey($dependencyName) -or $dependencyName -eq $service) {
                    $errors.Add("CONTAINER_HEALTH_DEPENDENCY_INVALID:$service")
                    continue
                }
                $dependencyContainer = @($containers | Where-Object { [string](Get-StartupProperty -InputObject $_ -Name 'service') -eq $dependencyName })[0]
                if ([string](Get-StartupProperty -InputObject $dependencyContainer -Name 'health_requirement') -ne 'HEALTHY') {
                    $errors.Add(('CONTAINER_HEALTH_DEPENDENCY_NOT_HEALTHY:{0}:{1}' -f $service, $dependencyName))
                }
                $dependencyOrder = [int64](Get-StartupProperty -InputObject $dependencyContainer -Name 'startup_order')
                $serviceOrder = [int64](Get-StartupProperty -InputObject $container -Name 'startup_order')
                if ($dependencyOrder -ge $serviceOrder) { $errors.Add(('CONTAINER_HEALTH_DEPENDENCY_ORDER_INVALID:{0}:{1}' -f $service, $dependencyName)) }
            }
        }
    }
    foreach ($bindingKey in @($dataTopology.approved_bindings.Keys)) {
        if (-not $matchedDataBindings.ContainsKey($bindingKey)) { $errors.Add(('DATA_BINDING_CONTAINER_MOUNT_MISSING:{0}' -f $bindingKey)) }
    }

    $services = @(Get-StartupProperty -InputObject $Manifest -Name 'host_services')
    $serviceByName = @{}
    foreach ($service in $services) {
        if ($null -eq $service) { continue }
        $name = [string](Get-StartupProperty -InputObject $service -Name 'name')
        if ([string]::IsNullOrWhiteSpace($name) -or $serviceByName.ContainsKey($name)) {
            $errors.Add("HOST_SERVICE_NAME_INVALID:$name")
            continue
        }
        $serviceByName[$name] = $service
        $policy = Get-StartupProperty -InputObject $service -Name 'policy'
        if ($policy -notin @('REQUIRED', 'INTENTIONALLY_STOPPED')) { $errors.Add("HOST_SERVICE_POLICY_INVALID:$name") }
        $fileRef = [string](Get-StartupProperty -InputObject $service -Name 'script_ref')
        $toolRef = [string](Get-StartupProperty -InputObject $service -Name 'tool_ref')
        if (-not $seenFileRoles.ContainsKey($fileRef)) { $errors.Add("HOST_SERVICE_SCRIPT_REF_INVALID:$name") }
        if (-not $seenTools.ContainsKey($toolRef)) { $errors.Add("HOST_SERVICE_TOOL_REF_INVALID:$name") }
    }
    foreach ($requiredService in @('public_gateway', 'private_gateway', 'supervisor')) {
        if (-not $serviceByName.ContainsKey($requiredService)) { $errors.Add("HOST_SERVICE_MISSING:$requiredService") }
    }
    foreach ($serviceName in @($serviceByName.Keys)) {
        $service = $serviceByName[$serviceName]
        $fileRef = [string](Get-StartupProperty -InputObject $service -Name 'script_ref')
        foreach ($field in @('launch_kind', 'executable', 'working_directory', 'listener_host', 'listener_port')) {
            $value = Get-StartupProperty -InputObject $service -Name $field
            if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
                $errors.Add(('HOST_SERVICE_FIELD_INVALID:{0}:{1}' -f $serviceName, $field))
            }
        }
        if ((Get-StartupProperty -InputObject $service -Name 'listener_host') -ne '127.0.0.1') {
            $errors.Add(('HOST_SERVICE_LISTENER_NOT_LOOPBACK:{0}' -f $serviceName))
        }
        $launchKind = [string](Get-StartupProperty -InputObject $service -Name 'launch_kind')
        if ($launchKind -ne 'TASK') { $errors.Add(('HOST_SERVICE_LAUNCH_KIND_INVALID:{0}' -f $serviceName)) }
        if ($launchKind -eq 'TASK') {
            if ([string]::IsNullOrWhiteSpace([string](Get-StartupProperty -InputObject $service -Name 'task_name'))) { $errors.Add(('HOST_SERVICE_TASK_NAME_MISSING:{0}' -f $serviceName)) }
            if ([string]::IsNullOrWhiteSpace([string](Get-StartupProperty -InputObject $service -Name 'task_path'))) { $errors.Add(('HOST_SERVICE_TASK_PATH_MISSING:{0}' -f $serviceName)) }
        }
        $toolRef = [string](Get-StartupProperty -InputObject $service -Name 'tool_ref')
        if ($seenTools.ContainsKey($toolRef)) {
            $toolPath = [string](Get-StartupProperty -InputObject $seenTools[$toolRef] -Name 'path')
            if (-not $toolPath.Equals([string](Get-StartupProperty -InputObject $service -Name 'executable'), [System.StringComparison]::OrdinalIgnoreCase)) {
                $errors.Add(('HOST_SERVICE_EXECUTABLE_MISMATCH:{0}' -f $serviceName))
            }
        }
        if ($null -ne $canonicalRoot) {
            try {
                $serviceWorkingDirectory = Get-CanonicalStartupPath ([string](Get-StartupProperty -InputObject $service -Name 'working_directory'))
                if (-not $serviceWorkingDirectory.Equals($canonicalRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                    $errors.Add(('HOST_SERVICE_WORKING_DIRECTORY_MISMATCH:{0}' -f $serviceName))
                }
            }
            catch { $errors.Add(('HOST_SERVICE_WORKING_DIRECTORY_INVALID:{0}' -f $serviceName)) }
        }
        $arguments = @(Get-StartupProperty -InputObject $service -Name 'arguments')
        if ($arguments.Count -eq 0) { $errors.Add(('HOST_SERVICE_ARGUMENTS_MISSING:{0}' -f $serviceName)) }
        if ($null -ne $canonicalRoot -and $seenFileRoles.ContainsKey($fileRef)) {
            $scriptFile = $seenFileRoles[$fileRef]
            $scriptRelativePath = [string](Get-StartupProperty -InputObject $scriptFile -Name 'path')
            try {
                $expectedScriptPath = Get-CanonicalStartupPath (Join-Path $canonicalRoot $scriptRelativePath)
                $codeArguments = New-Object System.Collections.Generic.List[string]
                foreach ($argument in $arguments) {
                    $argumentText = [string]$argument
                    if ($argumentText -match '(?i)\.(c?js|mjs|ps1|py)$') {
                        $candidate = if ([System.IO.Path]::IsPathRooted($argumentText)) {
                            Get-CanonicalStartupPath $argumentText
                        }
                        else {
                            Get-CanonicalStartupPath (Join-Path ([string](Get-StartupProperty -InputObject $service -Name 'working_directory')) $argumentText)
                        }
                        $codeArguments.Add($candidate)
                    }
                }
                if ($codeArguments.Count -ne 1 -or -not $codeArguments[0].Equals($expectedScriptPath, [System.StringComparison]::OrdinalIgnoreCase)) {
                    $errors.Add(('HOST_SERVICE_SCRIPT_BINDING_MISMATCH:{0}' -f $serviceName))
                }
            }
            catch {
                $errors.Add(('HOST_SERVICE_SCRIPT_BINDING_INVALID:{0}' -f $serviceName))
            }
        }
    }
    if ($serviceByName.ContainsKey('supervisor')) {
        if ((Get-StartupProperty -InputObject $serviceByName['supervisor'] -Name 'policy') -ne 'INTENTIONALLY_STOPPED') {
            $errors.Add('SUPERVISOR_POLICY_MUST_BE_INTENTIONALLY_STOPPED')
        }
    }

    $client = Get-StartupProperty -InputObject $Manifest -Name 'client'
    $clientPolicy = Get-StartupProperty -InputObject $client -Name 'policy'
    if ($clientPolicy -notin @('DISABLED', 'OPEN_AFTER_BASE_READY')) { $errors.Add('CLIENT_POLICY_INVALID') }
    if ($clientPolicy -eq 'OPEN_AFTER_BASE_READY') {
        $errors.Add('CLIENT_OPEN_NOT_IMPLEMENTED_P1')
    }

    $readiness = @(Get-StartupProperty -InputObject $Manifest -Name 'readiness')
    $readinessNames = @{}
    foreach ($check in $readiness) {
        if ($null -eq $check) { continue }
        $name = [string](Get-StartupProperty -InputObject $check -Name 'name')
        $uri = [string](Get-StartupProperty -InputObject $check -Name 'uri')
        $expectedStatus = Get-StartupProperty -InputObject $check -Name 'expected_status'
        if ([string]::IsNullOrWhiteSpace($name) -or $readinessNames.ContainsKey($name)) { $errors.Add(('READINESS_NAME_INVALID:{0}' -f $name)); continue }
        $readinessNames[$name] = $true
        if ($uri -notmatch '^http://127\.0\.0\.1:[0-9]+/') { $errors.Add(('READINESS_URI_INVALID:{0}' -f $name)) }
        if (-not ($expectedStatus -is [int]) -and -not ($expectedStatus -is [long])) { $errors.Add(('READINESS_STATUS_INVALID:{0}' -f $name)) }
    }
    foreach ($requiredCheck in @('backend', 'web', 'public_control_boundary')) {
        if (-not $readinessNames.ContainsKey($requiredCheck)) { $errors.Add(('READINESS_MISSING:{0}' -f $requiredCheck)) }
    }
    if ($readinessNames.ContainsKey('public_control_boundary')) {
        $boundary = @($readiness | Where-Object { (Get-StartupProperty -InputObject $_ -Name 'name') -eq 'public_control_boundary' })[0]
        if ([int](Get-StartupProperty -InputObject $boundary -Name 'expected_status') -ne 404) { $errors.Add('PUBLIC_CONTROL_EXPECTED_STATUS_INVALID') }
    }

    return [pscustomobject][ordered]@{
        valid = ($errors.Count -eq 0)
        errors = $errors.ToArray()
        normalized_root = $canonicalRoot
        files_by_role = $seenFileRoles
        tools_by_name = $seenTools
        services_by_name = $serviceByName
    }
}

function ConvertTo-StartupComparableMount {
    param([Parameter(Mandatory = $true)]$Mount)
    return ('{0}|{1}|{2}|{3}' -f
        ([string](Get-StartupProperty -InputObject $Mount -Name 'source')).ToLowerInvariant(),
        ([string](Get-StartupProperty -InputObject $Mount -Name 'destination')).ToLowerInvariant(),
        ([string](Get-StartupProperty -InputObject $Mount -Name 'type')).ToLowerInvariant(),
        [bool](Get-StartupProperty -InputObject $Mount -Name 'read_only'))
}

function ConvertTo-StartupComparablePort {
    param([Parameter(Mandatory = $true)]$Port)
    return ('{0}|{1}|{2}|{3}' -f
        ([string](Get-StartupProperty -InputObject $Port -Name 'host_ip')).ToLowerInvariant(),
        [string](Get-StartupProperty -InputObject $Port -Name 'host_port'),
        [string](Get-StartupProperty -InputObject $Port -Name 'container_port'),
        ([string](Get-StartupProperty -InputObject $Port -Name 'protocol')).ToLowerInvariant())
}

function Test-StartupStringSetEqual {
    param([object[]]$Expected = @(), [object[]]$Observed = @())
    $left = @($Expected | ForEach-Object { [string]$_ } | Sort-Object)
    $right = @($Observed | ForEach-Object { [string]$_ } | Sort-Object)
    if ($left.Count -ne $right.Count) { return $false }
    for ($index = 0; $index -lt $left.Count; $index++) {
        if (-not $left[$index].Equals($right[$index], [System.StringComparison]::OrdinalIgnoreCase)) { return $false }
    }
    return $true
}

function Test-ApprovedContainerIdentity {
    param([Parameter(Mandatory = $true)]$Expected, [Parameter(Mandatory = $true)]$Observed)
    $errors = New-Object System.Collections.Generic.List[string]
    foreach ($field in @('container_name', 'compose_project', 'service', 'image_id')) {
        $expectedValue = [string](Get-StartupProperty -InputObject $Expected -Name $field)
        $observedValue = [string](Get-StartupProperty -InputObject $Observed -Name $field)
        if (-not $expectedValue.Equals($observedValue, [System.StringComparison]::OrdinalIgnoreCase)) {
            $errors.Add(('CONTAINER_IDENTITY_MISMATCH:{0}' -f $field))
        }
    }
    $expectedContainerId = [string](Get-StartupProperty -InputObject $Expected -Name 'container_id')
    if (-not [string]::IsNullOrWhiteSpace($expectedContainerId)) {
        $observedContainerId = [string](Get-StartupProperty -InputObject $Observed -Name 'full_id')
        if (-not $expectedContainerId.Equals($observedContainerId, [System.StringComparison]::OrdinalIgnoreCase)) {
            $errors.Add('CONTAINER_IDENTITY_MISMATCH:container_id')
        }
    }
    $identityMode = [string](Get-StartupProperty -InputObject $Expected -Name 'image_identity_mode')
    if ([string]::IsNullOrWhiteSpace($identityMode)) { $identityMode = 'REPO_DIGEST' }
    if ($identityMode -eq 'REPO_DIGEST') {
        $expectedDigest = [string](Get-StartupProperty -InputObject $Expected -Name 'repo_digest')
        $observedDigest = [string](Get-StartupProperty -InputObject $Observed -Name 'repo_digest')
        if (-not $expectedDigest.Equals($observedDigest, [System.StringComparison]::OrdinalIgnoreCase)) {
            $errors.Add('CONTAINER_IDENTITY_MISMATCH:repo_digest')
        }
    }
    elseif ($identityMode -eq 'LOCAL_IMAGE_ID_CONFIRMED_NO_REPO_DIGEST') {
        $observedDigestState = [string](Get-StartupProperty -InputObject $Observed -Name 'repo_digest_state')
        if ($observedDigestState -ne 'CONFIRMED_ABSENT') {
            $errors.Add('CONTAINER_IDENTITY_MISMATCH:repo_digest_state')
        }
    }
    else {
        $errors.Add('CONTAINER_IDENTITY_MISMATCH:image_identity_mode')
    }
    $expectedMounts = @((Get-StartupProperty -InputObject $Expected -Name 'mounts') | ForEach-Object { ConvertTo-StartupComparableMount -Mount $_ })
    $observedMounts = @((Get-StartupProperty -InputObject $Observed -Name 'mounts') | ForEach-Object { ConvertTo-StartupComparableMount -Mount $_ })
    if (-not (Test-StartupStringSetEqual -Expected $expectedMounts -Observed $observedMounts)) { $errors.Add('CONTAINER_IDENTITY_MISMATCH:mounts') }
    $expectedPorts = @((Get-StartupProperty -InputObject $Expected -Name 'ports') | ForEach-Object { ConvertTo-StartupComparablePort -Port $_ })
    $configuredPortSource = if (Test-StartupProperty -InputObject $Observed -Name 'configured_ports') {
        Get-StartupProperty -InputObject $Observed -Name 'configured_ports'
    }
    else {
        Get-StartupProperty -InputObject $Observed -Name 'ports'
    }
    $configuredPorts = @($configuredPortSource | ForEach-Object { ConvertTo-StartupComparablePort -Port $_ })
    if (-not (Test-StartupStringSetEqual -Expected $expectedPorts -Observed $configuredPorts)) { $errors.Add('CONTAINER_IDENTITY_MISMATCH:configured_ports') }
    if ([bool](Get-StartupProperty -InputObject $Observed -Name 'running')) {
        $activePortSource = if (Test-StartupProperty -InputObject $Observed -Name 'active_ports') {
            Get-StartupProperty -InputObject $Observed -Name 'active_ports'
        }
        else {
            Get-StartupProperty -InputObject $Observed -Name 'ports'
        }
        $activePorts = @($activePortSource | ForEach-Object { ConvertTo-StartupComparablePort -Port $_ })
        if (-not (Test-StartupStringSetEqual -Expected $expectedPorts -Observed $activePorts)) { $errors.Add('CONTAINER_IDENTITY_MISMATCH:active_ports') }
    }
    return [pscustomobject]@{ valid = ($errors.Count -eq 0); errors = $errors.ToArray() }
}

function ConvertTo-StartupHostObservation {
    param([AllowNull()]$RawObservation)

    $items = @($RawObservation | Where-Object { $null -ne $_ })
    if ($items.Count -eq 1 -and (Test-StartupProperty -InputObject $items[0] -Name 'observation_status')) {
        return [pscustomobject]@{
            status = [string](Get-StartupProperty -InputObject $items[0] -Name 'observation_status')
            matches = @((Get-StartupProperty -InputObject $items[0] -Name 'matches'))
            detail = [string](Get-StartupProperty -InputObject $items[0] -Name 'detail')
        }
    }
    if ($items.Count -eq 0) { return [pscustomobject]@{ status = 'ABSENT'; matches = @(); detail = '' } }
    if ($items.Count -gt 1) { return [pscustomobject]@{ status = 'AMBIGUOUS'; matches = $items; detail = '' } }
    return [pscustomobject]@{ status = 'PRESENT'; matches = $items; detail = '' }
}

function Wait-StartupExistingContainerReady {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]$Expected,
        [Parameter(Mandatory = $true)]$Adapters,
        [Parameter(Mandatory = $true)][int]$StageTimeoutMilliseconds,
        [Parameter(Mandatory = $true)][int]$PollMilliseconds
    )
    $service = [string](Get-StartupProperty -InputObject $Expected -Name 'service')
    $healthRequirement = [string](Get-StartupProperty -InputObject $Expected -Name 'health_requirement')
    if ([string]::IsNullOrWhiteSpace($healthRequirement)) { $healthRequirement = 'RUNNING' }
    $deadline = (Get-MonotonicMilliseconds) + $StageTimeoutMilliseconds
    do {
        $matches = @(& $Adapters.ObserveContainer $Expected)
        if ($matches.Count -eq 0) { return [pscustomobject]@{ success = $false; code = 'CONTROLLED_DEPLOY_REQUIRED'; component = $service; observed = $null } }
        if ($matches.Count -ne 1) { return [pscustomobject]@{ success = $false; code = 'CONTAINER_IDENTITY_AMBIGUOUS'; component = $service; observed = $null } }
        $identity = Test-ApprovedContainerIdentity -Expected $Expected -Observed $matches[0]
        if (-not $identity.valid) { return [pscustomobject]@{ success = $false; code = 'IDENTITY_MISMATCH'; component = $service; detail = @($identity.errors); observed = $matches[0] } }
        if ([bool](Get-StartupProperty -InputObject $matches[0] -Name 'running')) {
            if ($healthRequirement -eq 'RUNNING') {
                return [pscustomobject]@{ success = $true; code = 'CONTAINER_READY'; component = $service; observed = $matches[0] }
            }
            if ([string](Get-StartupProperty -InputObject $matches[0] -Name 'health_status') -eq 'healthy') {
                return [pscustomobject]@{ success = $true; code = 'CONTAINER_HEALTHY'; component = $service; observed = $matches[0] }
            }
        }
        $remaining = Get-StartupRemainingMilliseconds -Deadline $deadline -MaximumMilliseconds $PollMilliseconds
        if ($remaining -le 0) { break }
        & $Adapters.Sleep $remaining
    } while ((Get-MonotonicMilliseconds) -lt $deadline)
    $code = if ($healthRequirement -eq 'HEALTHY') { 'CONTAINER_HEALTH_UNKNOWN' } else { 'CONTAINER_NOT_RUNNING_AFTER_START' }
    return [pscustomobject]@{ success = $false; code = $code; component = $service; observed = $null }
}

function Invoke-StartupExistingContainerPhase {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object[]]$ExpectedContainers,
        [Parameter(Mandatory = $true)]$Adapters,
        [Parameter(Mandatory = $true)][int]$CommandTimeoutMilliseconds,
        [int]$StageTimeoutMilliseconds = 60000,
        [int]$PollMilliseconds = 1000
    )
    $events = New-Object System.Collections.Generic.List[object]
    $orderedContainers = @($ExpectedContainers | Sort-Object @{ Expression = {
        $order = Get-StartupProperty -InputObject $_ -Name 'startup_order'
        if ($null -eq $order) { return [int64]::MaxValue }
        return [int64]$order
    } })
    $containersByService = @{}
    foreach ($definition in $orderedContainers) { $containersByService[[string](Get-StartupProperty -InputObject $definition -Name 'service')] = $definition }
    foreach ($expected in $orderedContainers) {
        $service = [string](Get-StartupProperty -InputObject $expected -Name 'service')
        foreach ($dependencyNameValue in @(Get-StartupProperty -InputObject $expected -Name 'depends_on_healthy')) {
            $dependencyName = [string]$dependencyNameValue
            if ([string]::IsNullOrWhiteSpace($dependencyName)) { continue }
            if (-not $containersByService.ContainsKey($dependencyName)) {
                return [pscustomobject]@{ success = $false; code = 'CONTAINER_DEPENDENCY_INVALID'; component = $service; events = $events.ToArray() }
            }
            $dependencyReady = Wait-StartupExistingContainerReady -Expected $containersByService[$dependencyName] -Adapters $Adapters -StageTimeoutMilliseconds $StageTimeoutMilliseconds -PollMilliseconds $PollMilliseconds
            if (-not $dependencyReady.success) {
                return [pscustomobject]@{ success = $false; code = $dependencyReady.code; component = $dependencyName; detail = @(Get-StartupProperty -InputObject $dependencyReady -Name 'detail'); events = $events.ToArray() }
            }
            $events.Add([pscustomobject]@{ component = $dependencyName; action = 'DEPENDENCY_HEALTH_CONFIRMED' })
        }
        $matches = @(& $Adapters.ObserveContainer $expected)
        if ($matches.Count -eq 0) { return [pscustomobject]@{ success = $false; code = 'CONTROLLED_DEPLOY_REQUIRED'; component = $service; events = $events.ToArray() } }
        if ($matches.Count -ne 1) { return [pscustomobject]@{ success = $false; code = 'CONTAINER_IDENTITY_AMBIGUOUS'; component = $service; events = $events.ToArray() } }
        $identity = Test-ApprovedContainerIdentity -Expected $expected -Observed $matches[0]
        if (-not $identity.valid) { return [pscustomobject]@{ success = $false; code = 'IDENTITY_MISMATCH'; component = $service; detail = @($identity.errors); events = $events.ToArray() } }
        if ([bool](Get-StartupProperty -InputObject $matches[0] -Name 'running')) {
            $ready = Wait-StartupExistingContainerReady -Expected $expected -Adapters $Adapters -StageTimeoutMilliseconds $StageTimeoutMilliseconds -PollMilliseconds $PollMilliseconds
            if (-not $ready.success) { return [pscustomobject]@{ success = $false; code = $ready.code; component = $service; detail = @(Get-StartupProperty -InputObject $ready -Name 'detail'); events = $events.ToArray() } }
            $events.Add([pscustomobject]@{ component = $service; action = 'PRESERVE_RUNNING' })
            continue
        }
        $observedFullId = [string](Get-StartupProperty -InputObject $matches[0] -Name 'full_id')
        if ($observedFullId -notmatch '^[a-fA-F0-9]{64}$') {
            return [pscustomobject]@{ success = $false; code = 'CONTAINER_RUNTIME_ID_INVALID'; component = $service; events = $events.ToArray() }
        }
        $startResult = & $Adapters.StartExistingContainer $observedFullId $CommandTimeoutMilliseconds
        $events.Add([pscustomobject]@{ component = $service; action = 'START_EXISTING'; result = [string](Get-StartupProperty -InputObject $startResult -Name 'status') })
        if ((Get-StartupProperty -InputObject $startResult -Name 'status') -ne 'SUCCESS') {
            $code = if ((Get-StartupProperty -InputObject $startResult -Name 'status') -eq 'TIMEOUT') { 'CONTAINER_START_UNKNOWN' } else { 'CONTAINER_START_FAILED' }
            return [pscustomobject]@{ success = $false; code = $code; component = $service; events = $events.ToArray() }
        }
        $ready = Wait-StartupExistingContainerReady -Expected $expected -Adapters $Adapters -StageTimeoutMilliseconds $StageTimeoutMilliseconds -PollMilliseconds $PollMilliseconds
        if (-not $ready.success) { return [pscustomobject]@{ success = $false; code = $ready.code; component = $service; detail = @(Get-StartupProperty -InputObject $ready -Name 'detail'); events = $events.ToArray() } }
        if (-not $observedFullId.Equals([string](Get-StartupProperty -InputObject $ready.observed -Name 'full_id'), [System.StringComparison]::OrdinalIgnoreCase)) {
            return [pscustomobject]@{ success = $false; code = 'CONTAINER_RUNTIME_ID_CHANGED'; component = $service; events = $events.ToArray() }
        }
    }
    return [pscustomobject]@{ success = $true; code = 'CONTAINERS_READY'; events = $events.ToArray() }
}

function Enter-StartupMutex {
    param([Parameter(Mandatory = $true)][string]$Root)

    $canonical = (Get-CanonicalStartupPath -Path $Root).ToLowerInvariant()
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($canonical)
        $hash = ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '')
    }
    finally {
        $sha.Dispose()
    }
    $name = "Local\NEXT_STABIL_HOST_START_" + $hash.Substring(0, 24)
    $mutex = New-Object System.Threading.Mutex($false, $name)
    $acquired = $false
    try {
        $acquired = $mutex.WaitOne(0, $false)
    }
    catch [System.Threading.AbandonedMutexException] {
        $acquired = $true
    }
    return [pscustomobject]@{ acquired = $acquired; name = $name; handle = $mutex }
}

function Exit-StartupMutex {
    param([Parameter(Mandatory = $true)]$Lock)
    if ($null -eq $Lock) { return }
    try {
        if ($Lock.acquired) { $Lock.handle.ReleaseMutex() }
    }
    finally {
        $Lock.handle.Dispose()
    }
}

function Read-StartupSetManifest {
    param([Parameter(Mandatory = $true)][string]$ManifestPath)

    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        return [pscustomobject]@{ success = $false; code = 'MANIFEST_MISSING'; manifest = $null; detail = '' }
    }
    try {
        $manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
        return [pscustomobject]@{ success = $true; code = 'OK'; manifest = $manifest; detail = '' }
    }
    catch {
        return [pscustomobject]@{
            success = $false
            code = 'MANIFEST_PARSE_FAILED'
            manifest = $null
            detail = ConvertTo-SafeStartupDiagnostic -Value $_.Exception.Message
        }
    }
}
