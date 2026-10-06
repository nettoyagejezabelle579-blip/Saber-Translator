# 在 Windows 上實測 Update-Saber.ps1：語法檢查＋離線套用「小型更新包」與「完整分卷」，
# 確認程式檔案被更新、被刪除的檔案移除、data-v2 完全不變。
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$Updater = Join-Path $Repo 'packaging\Update-Saber.ps1'
$Prefix = 'Saber-Translator-zhHant-CPU'

$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($Updater, [ref]$null, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Host $_ }; throw 'Update-Saber.ps1 has syntax errors' }

$Root = Join-Path $env:RUNNER_TEMP 'updater-test'
if (Test-Path $Root) { Remove-Item $Root -Recurse -Force }
function New-Tree([string]$Dist, [string]$Exe, [string[]]$Extra) {
    $app = Join-Path $Dist 'Saber-Translator'
    New-Item -ItemType Directory -Force -Path "$app\_internal" | Out-Null
    Set-Content "$app\Saber-Translator.exe" $Exe
    Set-Content "$app\_internal\keep.bin" 'unchanged library'
    foreach ($name in $Extra) { Set-Content "$app\$name" $name }
}
New-Tree "$Root\v1" 'old program' @('old.txt')
New-Tree "$Root\v2" 'new program' @('added.txt')
# 舊版留下、缺少 METADATA 的套件資訊資料夾（曾讓 openai 匯入時崩潰）；新版只有正確的那一個
New-Item -ItemType Directory -Force -Path "$Root\v1\Saber-Translator\_internal\aiohttp-3.0.0.dist-info\licenses" | Out-Null
Set-Content "$Root\v1\Saber-Translator\_internal\aiohttp-3.0.0.dist-info\licenses\LICENSE.txt" 'stale'
New-Item -ItemType Directory -Force -Path "$Root\v2\Saber-Translator\_internal\aiohttp-3.14.4.dist-info" | Out-Null
Set-Content "$Root\v2\Saber-Translator\_internal\aiohttp-3.14.4.dist-info\METADATA" 'Version: 3.14.4'
# 中文檔名（實際程式內的字型就是中文檔名）也要能正確解壓與複製
New-Item -ItemType Directory -Force -Path "$Root\v2\Saber-Translator\_internal\fonts" | Out-Null
Set-Content -LiteralPath "$Root\v2\Saber-Translator\_internal\fonts\思源黑體-測試.ttf" 'font'
# 兩個 50 KB 的「模型」，讓續傳測試能切成多個分卷
$random = New-Object Random
foreach ($name in 'model-a.bin', 'model-b.bin') {
    $blob = New-Object byte[] 50000
    $random.NextBytes($blob)
    [IO.File]::WriteAllBytes("$Root\v2\Saber-Translator\_internal\$name", $blob)
}
New-Item -ItemType Directory -Force -Path "$Root\o1", "$Root\o2", "$Root\parts" | Out-Null
Push-Location "$Root\o1"; python "$Repo\.github\scripts\make_update.py" "$Root\v1" aaa1111 $Prefix; Pop-Location
Push-Location "$Root\o2"; python "$Repo\.github\scripts\make_update.py" "$Root\v2" bbb2222 $Prefix "$Root\o1\build-manifest.json"; Pop-Location
Push-Location "$Root\parts"; python "$Repo\.github\scripts\pack_parts.py" "$Root\v2" $Prefix; Pop-Location
if (-not (Test-Path "$Root\o2\$Prefix-update.zip")) { throw 'update zip was not created' }

function New-Install([string]$Name, [bool]$WithBuild) {
    $install = Join-Path $Root $Name
    Copy-Item "$Root\v1\Saber-Translator" $install -Recurse
    if (-not $WithBuild) { Remove-Item "$install\BUILD.json", "$install\build-manifest.json" -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Force -Path "$install\data-v2" | Out-Null
    Set-Content "$install\data-v2\library.db" 'my books and settings'
    Copy-Item $Updater $install
    return $install
}
function Assert-Updated([string]$Install, [bool]$Incremental) {
    if ((Get-Content "$Install\Saber-Translator.exe") -ne 'new program') { throw "$Install exe not updated" }
    if (-not (Test-Path "$Install\added.txt")) { throw "$Install added file missing" }
    if (-not (Test-Path -LiteralPath "$Install\_internal\fonts\思源黑體-測試.ttf")) { throw "$Install unicode file missing" }
    if ((Get-Content "$Install\data-v2\library.db") -ne 'my books and settings') { throw "$Install data-v2 changed" }
    if ((Get-Content "$Install\BUILD.json" -Raw | ConvertFrom-Json).build -ne 'bbb2222') { throw "$Install build id not updated" }
    if ($Incremental -and (Test-Path "$Install\old.txt")) { throw "$Install deleted file still present" }
    if (Test-Path "$Install\UPDATE-INFO.json") { throw "$Install UPDATE-INFO.json left behind" }
    if (Test-Path "$Install\_internal\aiohttp-3.0.0.dist-info") { throw "$Install stale dist-info left behind" }
    if (-not (Test-Path "$Install\_internal\aiohttp-3.14.4.dist-info\METADATA")) { throw "$Install current dist-info removed" }
}

$incremental = New-Install 'install-incremental' $true
powershell -NoProfile -ExecutionPolicy Bypass -File "$incremental\Update-Saber.ps1" -Offline -DownloadsDir "$Root\o2"
if ($LASTEXITCODE -ne 0) { throw "incremental update failed ($LASTEXITCODE)" }
Assert-Updated $incremental $true

$full = New-Install 'install-full' $false
powershell -NoProfile -ExecutionPolicy Bypass -File "$full\Update-Saber.ps1" -Offline -DownloadsDir "$Root\parts"
if ($LASTEXITCODE -ne 0) { throw "full update failed ($LASTEXITCODE)" }
Assert-Updated $full $false

# 線上下載＋續傳：舊版更新程式留下完整的 part1（放在舊位置，伺服器上沒有 part1，若重新下載就會失敗），
# part2 只下載了一半（必須用 Range 從中斷處繼續）；舊版的 staging 與其他版本的暫存資料夾要被清掉。
New-Item -ItemType Directory -Force -Path "$Root\multi", "$Root\served" | Out-Null
Push-Location "$Root\multi"; python "$Repo\.github\scripts\pack_parts.py" "$Root\v2" $Prefix 60000; Pop-Location
$partFiles = @(Get-ChildItem "$Root\multi\$Prefix-part*.zip" | Sort-Object Name)
if ($partFiles.Count -lt 2) { throw 'resume test needs at least two parts' }
$port = 8765
$releaseAssets = @($partFiles | ForEach-Object {
    [ordered]@{
        name = $_.Name
        size = $_.Length
        url = 'unused'
        browser_download_url = "http://127.0.0.1:$port/$($_.Name)"
        digest = 'sha256:' + (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
})
ConvertTo-Json -Depth 5 @{ name = '繁中免安裝版 (CPU) bbb2222'; assets = $releaseAssets } |
    Set-Content "$Root\release.json" -Encoding UTF8
$partFiles | Select-Object -Skip 1 | Copy-Item -Destination "$Root\served"

# 自動更新（開啟 Saber-Translator.exe 時）用的發布資訊：小型更新包＋update-info.json
Copy-Item "$Root\o2\$Prefix-update.zip", "$Root\o2\update-info.json" -Destination "$Root\served"
$autoAssets = @(Get-Item "$Root\served\$Prefix-update.zip", "$Root\served\update-info.json" | ForEach-Object {
    [ordered]@{
        name = $_.Name
        size = $_.Length
        url = 'unused'
        browser_download_url = "http://127.0.0.1:$port/$($_.Name)"
        digest = 'sha256:' + (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
})
ConvertTo-Json -Depth 5 @{ name = '繁中免安裝版 (CPU) bbb2222'; assets = ($autoAssets + $releaseAssets) } |
    Set-Content "$Root\release-auto.json" -Encoding UTF8

$tmp = Join-Path $Root 'tmp'
$work = Join-Path $tmp 'saber-update\build-bbb2222'
New-Item -ItemType Directory -Force -Path $work, "$tmp\saber-update\build-old", "$tmp\saber-update\staging\Saber-Translator" | Out-Null
Set-Content "$tmp\saber-update\build-old\stale.zip" 'stale'
Set-Content "$tmp\saber-update\staging\Saber-Translator\half-extracted.txt" 'old updater leftovers'
Copy-Item $partFiles[0].FullName "$tmp\saber-update\$($partFiles[0].Name)"
$bytes = [IO.File]::ReadAllBytes($partFiles[1].FullName)
$half = [int]($bytes.Length / 2)
[IO.File]::WriteAllBytes("$work\$($partFiles[1].Name)", [byte[]]$bytes[0..($half - 1)])

$server = Start-Process python -ArgumentList @("$Repo\.github\scripts\range_server.py", "$Root\served", $port, "$Root\ranges.log") -PassThru -WindowStyle Hidden
try {
    for ($i = 0; $i -lt 50; $i++) {
        try { Invoke-WebRequest "http://127.0.0.1:$port/$($partFiles[1].Name)" -Method Head -UseBasicParsing -TimeoutSec 2 | Out-Null; break }
        catch { Start-Sleep -Milliseconds 200 }
    }
    $online = New-Install 'install-online' $false
    $savedTemp = $env:TEMP
    $env:TEMP = $tmp
    try {
        powershell -NoProfile -ExecutionPolicy Bypass -File "$online\Update-Saber.ps1" -ReleaseFile "$Root\release.json"
        if ($LASTEXITCODE -ne 0) { throw "online resumed update failed ($LASTEXITCODE)" }
        Assert-Updated $online $false
        if (Test-Path "$tmp\saber-update") { throw 'download folder was not cleaned up' }
        if (Test-Path "$online\half-extracted.txt") { throw 'old updater leftovers were installed' }
        $ranges = Get-Content "$Root\ranges.log" -ErrorAction SilentlyContinue
        if ($ranges -notcontains "$($partFiles[1].Name) $half") { throw "part2 was not resumed: $ranges" }
        powershell -NoProfile -ExecutionPolicy Bypass -File "$online\Update-Saber.ps1" -ReleaseFile "$Root\release.json"
        if ($LASTEXITCODE -ne 0) { throw "second run should report up to date ($LASTEXITCODE)" }

        # 自動模式：先等開啟更新的程式結束、不詢問任何問題（-NonInteractive 下有提問就會失敗）、
        # 套用小型更新後嘗試重新開啟程式（測試裡的 exe 不是真的程式，開啟失敗也不影響結果）
        $auto = New-Install 'install-auto' $true
        $dummy = Start-Process powershell -ArgumentList '-NoProfile', '-Command', 'Start-Sleep -Seconds 3' -PassThru -WindowStyle Hidden
        powershell -NonInteractive -NoProfile -ExecutionPolicy Bypass -File "$auto\Update-Saber.ps1" -ReleaseFile "$Root\release-auto.json" -Auto -WaitPid $dummy.Id
        if ($LASTEXITCODE -ne 0) { throw "automatic update failed ($LASTEXITCODE)" }
        if (-not $dummy.HasExited) { throw 'automatic update did not wait for the running program' }
        Assert-Updated $auto $true
    } finally {
        $env:TEMP = $savedTemp
    }
} finally {
    Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
}

Write-Host 'Updater tests passed'
