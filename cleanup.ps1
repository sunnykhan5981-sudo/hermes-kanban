$ErrorActionPreference = 'SilentlyContinue'

# 1) Kill every server.py and watchdog.py process (full tree, parents first)
$pids = @()
$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'watchdog.py|server.py' -and $_.CommandLine -notlike '*powershell*' -and $_.CommandLine -notlike '*bash*' }
$pids += $p.ProcessId
$pids += $p.ParentProcessId

# also kill the bash launchers that spawned them
$bash = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'watchdog.py|server.py' -and ($_.CommandLine -like '*bash*') }
$pids += $bash.ProcessId

$pids = $pids | Where-Object { $_ -and $_ -ne 0 } | Sort-Object -Unique
Write-Host "Killing PIDs: $($pids -join ',')"
foreach ($id in $pids) {
    Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3

# 2) Confirm port free
$conn = Get-NetTCPConnection -LocalPort 9121 -ErrorAction SilentlyContinue
if ($conn) { Write-Host "STILL LISTENING: $($conn.OwningProcess -join ',')" } else { Write-Host "PORT 9121 FREE" }
