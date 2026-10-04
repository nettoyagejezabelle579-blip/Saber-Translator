# 發布前實測小型更新包：把目前 Release 的完整分卷裝成「使用者現在的版本」（含書籍資料），
# 再用新的 Update-Saber.ps1 套用新的 update.zip，逐一核對每個檔案的 SHA-256。
# 任何一步失敗都會讓建置失敗，不會發布。
param(
    [Parameter(Mandatory)] [string]$OldPartsDir,   # 目前 Release 的 part*.zip
    [Parameter(Mandatory)] [string]$UpdateZip,     # 這次建置的 update.zip
    [Parameter(Mandatory)] [string]$Manifest,      # 這次建置的 build-manifest.json
    [Parameter(Mandatory)] [string]$Updater,       # 這次建置的 Update-Saber.ps1
    [string]$Root = 'C:\verify-update'
)
$ErrorActionPreference = 'Stop'
$app = Join-Path $Root 'Saber-Translator'
if (Test-Path $Root) { Remove-Item $Root -Recurse -Force }
New-Item -ItemType Directory -Force -Path "$app\data-v2\books", "$Root\upd", "$Root\tmp" | Out-Null
Set-Content "$app\Saber-Translator.exe" 'placeholder'
Set-Content "$app\data-v2\library.db" 'my books and settings'
Set-Content "$app\data-v2\books\chapter1.png" 'page'
Copy-Item $Updater $app
$dataBefore = Get-ChildItem "$app\data-v2" -Recurse -File | Get-FileHash | ForEach-Object { $_.Hash }
$env:TEMP = "$Root\tmp"

function Invoke-Updater([string]$Downloads, [string]$Log) {
    cmd /c "powershell -NonInteractive -NoProfile -ExecutionPolicy Bypass -File `"$app\Update-Saber.ps1`" -Offline -DownloadsDir `"$Downloads`" > `"$Log`" 2>&1"
    $code = $LASTEXITCODE
    Get-Content $Log -Encoding UTF8 | Write-Host
    if ($code -ne 0) { throw "updater failed ($code)" }
}

# 1) 裝成使用者現在的版本
Invoke-Updater $OldPartsDir "$Root\install-old.log"
$oldBuild = (Get-Content "$app\BUILD.json" -Raw | ConvertFrom-Json).build
Write-Host "installed current release: $oldBuild"
Remove-Item "$OldPartsDir\*.zip" -Force   # 省空間

# 2) 套用新的小型更新包
Copy-Item $UpdateZip "$Root\upd\"
Invoke-Updater "$Root\upd" "$Root\update.log"

# 3) 核對
$expected = Get-Content $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
$bad = 0; $checked = 0
foreach ($entry in $expected.files.PSObject.Properties) {
    $path = Join-Path $app ($entry.Name -replace '/', '\')
    $checked++
    if (-not (Test-Path -LiteralPath $path)) { Write-Host "MISSING $($entry.Name)"; $bad++; continue }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) { Write-Host "DIFFERENT $($entry.Name)"; $bad++ }
}
Write-Host "checked $checked files, $bad problems"
if ($bad -gt 0) { throw "$bad files differ after applying the update" }
if ((Get-Content "$app\BUILD.json" -Raw | ConvertFrom-Json).build -ne $expected.build) { throw 'BUILD.json was not updated' }
$dataAfter = Get-ChildItem "$app\data-v2" -Recurse -File | Get-FileHash | ForEach-Object { $_.Hash }
if (Compare-Object $dataBefore $dataAfter) { throw 'data-v2 changed' }
Write-Host "update.zip verified: $oldBuild -> $($expected.build), data-v2 untouched"
