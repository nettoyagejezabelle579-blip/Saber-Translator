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
# 中文檔名（實際程式內的字型就是中文檔名）也要能正確解壓與複製
New-Item -ItemType Directory -Force -Path "$Root\v2\Saber-Translator\_internal\fonts" | Out-Null
Set-Content -LiteralPath "$Root\v2\Saber-Translator\_internal\fonts\思源黑體-測試.ttf" 'font'
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
}

$incremental = New-Install 'install-incremental' $true
powershell -NoProfile -ExecutionPolicy Bypass -File "$incremental\Update-Saber.ps1" -Offline -DownloadsDir "$Root\o2"
if ($LASTEXITCODE -ne 0) { throw "incremental update failed ($LASTEXITCODE)" }
Assert-Updated $incremental $true

$full = New-Install 'install-full' $false
powershell -NoProfile -ExecutionPolicy Bypass -File "$full\Update-Saber.ps1" -Offline -DownloadsDir "$Root\parts"
if ($LASTEXITCODE -ne 0) { throw "full update failed ($LASTEXITCODE)" }
Assert-Updated $full $false

Write-Host 'Updater tests passed'
