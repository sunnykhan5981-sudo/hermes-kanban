$ErrorActionPreference = 'SilentlyContinue'
for ($i = 0; $i -lt 8; $i++) {
    $conn = Get-NetTCPConnection -LocalPort 9121 -ErrorAction SilentlyContinue
    if (-not $conn) { Write-Host "PORT 9121 FREE after $i attempts"; exit 0 }
    $pids = $conn.OwningProcess | Sort-Object -Unique
    Write-Host "Attempt $i : 9121 held by PID(s): $($pids -join ',')"
    foreach ($p in $pids) {
        # also kill the parent bash/console that may have launched it
        try {
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $p"
            if ($proc -and $proc.ParentProcessId) {
                Stop-Process -Id $proc.ParentProcessId -Force -ErrorAction SilentlyContinue
            }
        } catch {}
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}
$final = Get-NetTCPConnection -LocalPort 9121 -ErrorAction SilentlyContinue
if ($final) { Write-Host "FINAL STILL LISTENING: $($final.OwningProcess -join ',')" }
else { Write-Host "CONFIRMED FREE" }
