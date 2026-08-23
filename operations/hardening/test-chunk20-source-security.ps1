$ErrorActionPreference = "Stop"

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$compose = Get-Content -LiteralPath (Join-Path $repo "compose\postgres\docker-compose.yml") -Raw
$manifest = Get-Content -LiteralPath (Join-Path $repo "frontend\android\app\src\main\AndroidManifest.xml") -Raw
$debugManifest = Get-Content -LiteralPath (Join-Path $repo "frontend\android\app\src\debug\AndroidManifest.xml") -Raw
$publicGateway = Get-Content -LiteralPath (Join-Path $repo "operations\gateway\public_web_server.cjs") -Raw
$authApi = Get-Content -LiteralPath (Join-Path $repo "backend\app\api\auth.py") -Raw
$rateLimiter = Get-Content -LiteralPath (Join-Path $repo "backend\app\services\login_rate_limiter.py") -Raw

if ($compose -match 'POSTGRES_PASSWORD:\s*ai_lab_password') {
    throw "tracked_postgres_password_literal_present"
}
if ($compose -notmatch 'POSTGRES_PASSWORD:\s*\$\{POSTGRES_PASSWORD:\?') {
    throw "postgres_password_not_fail_closed"
}
if ($manifest -notmatch 'android:allowBackup="false"') {
    throw "android_backup_not_disabled"
}
if ($manifest -notmatch 'android:fullBackupContent="false"') {
    throw "android_full_backup_not_disabled"
}
if ($manifest -notmatch 'android:usesCleartextTraffic="false"') {
    throw "android_cleartext_not_disabled"
}
if ($debugManifest -notmatch 'tools:replace="android:usesCleartextTraffic"') {
    throw "android_debug_cleartext_override_not_explicit"
}
if ($publicGateway -notmatch "pathname === '/control'") {
    throw "public_control_boundary_missing"
}
if ($publicGateway -match 'SUPERVISOR\s*=') {
    throw "public_gateway_references_supervisor"
}
if ($publicGateway -notmatch "X-Content-Type-Options': 'nosniff'") {
    throw "public_nosniff_missing"
}
if ($publicGateway -notmatch 'Content-Security-Policy-Report-Only') {
    throw "public_csp_report_only_missing"
}
if ($publicGateway -match 'Strict-Transport-Security') {
    throw "hsts_enabled_without_https_only_proof"
}
if ($authApi -match 'request\.headers.*(X-Forwarded-For|X-Real-IP|Forwarded)') {
    throw "auth_trusts_forwarded_header"
}
if ($rateLimiter -notmatch 'max_buckets') {
    throw "login_rate_limiter_unbounded"
}

$trackedSensitive = @(git -C $repo ls-files | Where-Object {
    $_ -match '(^|/)(\.env($|\.)|key\.properties$|.*\.jks$|.*\.keystore$|id_rsa$|.*\.pfx$|.*\.pem$)'
})
if ($trackedSensitive.Count -ne 0) {
    throw "tracked_sensitive_files_present"
}

Write-Output "CHUNK20_TRACKED_SECRET_GUARD=PASS"
Write-Output "CHUNK20_ANDROID_RELEASE_POLICY=PASS"
Write-Output "CHUNK20_PUBLIC_SUPERVISOR_BOUNDARY=PASS"
Write-Output "CHUNK20_PUBLIC_SECURITY_HEADERS=PASS"
Write-Output "CHUNK20_LOGIN_PROXY_TRUST=FAIL_CLOSED"
