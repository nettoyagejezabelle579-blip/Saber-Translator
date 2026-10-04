# Saber-Translator 更新程式
# 只更新程式檔案；data-v2（書籍、設定、API Key、術語表）完全不會被改動。
param(
    [switch]$Offline,                     # 不連 GitHub，只用下載資料夾裡的檔案
    [string]$DownloadsDir = ''            # 預設為使用者的「下載」資料夾
)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Owner = 'nettoyagejezabelle579-blip'
$Repo = 'Saber-Translator'
$Tag = 'galaxy-zh-hant-cpu'
$Prefix = 'Saber-Translator-zhHant-CPU'
$App = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataDir = Join-Path $App 'data-v2'
$TokenFile = Join-Path $DataDir 'github-token.txt'
$Work = Join-Path $env:TEMP 'saber-update'

function Say([string]$Message, [string]$Color = 'White') { Write-Host $Message -ForegroundColor $Color }
function Stop-Update([string]$Message) { Say $Message 'Red'; exit 1 }

if (-not (Test-Path (Join-Path $App 'Saber-Translator.exe'))) {
    Stop-Update '請把更新程式放在 Saber-Translator.exe 所在的資料夾再執行。'
}

# 1. 關閉執行中的 Saber-Translator
$running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -and $_.Path.StartsWith($App, [StringComparison]::OrdinalIgnoreCase)
})
if ($running.Count -gt 0) {
    Say 'Saber-Translator 正在執行，更新前需要先關閉。' 'Yellow'
    $answer = Read-Host '要自動關閉嗎？(Y/N)'
    if ($answer -notmatch '^[Yy]') { Stop-Update '已取消。請關閉 Saber-Translator 後再執行更新。' }
    $running | Stop-Process -Force
    Start-Sleep -Seconds 3
}

# 2. 目前版本
$LocalBuild = ''
$BuildFile = Join-Path $App 'BUILD.json'
if (Test-Path $BuildFile) { $LocalBuild = (Get-Content $BuildFile -Raw | ConvertFrom-Json).build }
if ($LocalBuild) { Say "目前版本：$LocalBuild" } else { Say '目前版本：舊版（沒有版本資訊，會下載完整程式）' }

# 3. 取得最新版資訊
function Get-Release([string]$Token) {
    $headers = @{ 'User-Agent' = 'Saber-Updater'; 'Accept' = 'application/vnd.github+json' }
    if ($Token) { $headers['Authorization'] = "Bearer $Token" }
    Invoke-RestMethod -Uri "https://api.github.com/repos/$Owner/$Repo/releases/tags/$Tag" -Headers $headers
}
$Token = ''
if (Test-Path $TokenFile) { $Token = (Get-Content $TokenFile -Raw).Trim() }
$Release = $null
try {
    if ($Offline) { throw 'offline' }
    $Release = Get-Release $Token
} catch {
    if ($Offline) {
        Say '離線模式：使用下載資料夾裡的更新檔。'
    } elseif (-not $Token) {
        Say '這個 GitHub 倉庫是私人倉庫，需要一組「唯讀存取權杖」才能自動下載更新（只需設定一次）。' 'Yellow'
        Say '建立方式：GitHub 右上角頭像 → Settings → Developer settings → Personal access tokens'
        Say '  → Fine-grained tokens → Generate new token；Repository access 選 Saber-Translator，'
        Say '  Permissions → Contents 選 Read-only，產生後複製權杖。'
        $Token = (Read-Host '請貼上權杖（直接按 Enter：改用「下載」資料夾裡已下載的更新檔）').Trim()
        if ($Token) {
            try {
                $Release = Get-Release $Token
                New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
                Set-Content -Path $TokenFile -Value $Token -Encoding ASCII
                Say '權杖已儲存在 data-v2\github-token.txt，下次不用再輸入。' 'Green'
            } catch {
                Say ('權杖無效或沒有權限：' + $_.Exception.Message) 'Red'
                $Token = ''
            }
        }
    } else {
        Say ('無法連線到 GitHub（' + $_.Exception.Message + '），改用「下載」資料夾裡的更新檔。') 'Yellow'
    }
}

function Get-Asset($Asset, [string]$Destination) {
    $curlArgs = @('-L', '--fail', '--retry', '3', '-o', $Destination, '-H', 'User-Agent: Saber-Updater')
    if ($Token) {
        $curlArgs += @('-H', "Authorization: Bearer $Token", '-H', 'Accept: application/octet-stream', $Asset.url)
    } else {
        $curlArgs += $Asset.browser_download_url
    }
    & curl.exe @curlArgs
    if ($LASTEXITCODE -ne 0) { throw "下載失敗：$($Asset.name)" }
}

if (Test-Path $Work) { Remove-Item $Work -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Work | Out-Null
$Staging = Join-Path $Work 'staging'
New-Item -ItemType Directory -Force -Path $Staging | Out-Null
$Zips = @()

if ($Release) {
    $assets = @{}
    foreach ($asset in $Release.assets) { $assets[$asset.name] = $asset }
    $info = $null
    if ($assets.ContainsKey('update-info.json')) {
        $infoPath = Join-Path $Work 'update-info.json'
        Get-Asset $assets['update-info.json'] $infoPath
        $info = Get-Content $infoPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    $RemoteBuild = if ($info) { $info.build } else { ($Release.name -split ' ')[-1] }
    if ($LocalBuild -and $LocalBuild -eq $RemoteBuild) {
        Say "已經是最新版本（$LocalBuild），不需要更新。" 'Green'
        exit 0
    }
    if ($info -and $LocalBuild -and $info.base -eq $LocalBuild -and $assets.ContainsKey("$Prefix-update.zip")) {
        $update = $assets["$Prefix-update.zip"]
        Say ("下載小型更新包（{0} → {1}，約 {2:N0} MB）..." -f $LocalBuild, $RemoteBuild, ($update.size / 1MB))
        $destination = Join-Path $Work $update.name
        Get-Asset $update $destination
        $Zips += $destination
    } else {
        $parts = @($Release.assets | Where-Object { $_.name -like "$Prefix-part*.zip" } | Sort-Object name)
        if ($parts.Count -eq 0) { Stop-Update 'GitHub 上找不到更新檔，請稍後再試。' }
        $total = ($parts | Measure-Object -Property size -Sum).Sum / 1GB
        Say ("需要下載完整程式：{0} 個分卷，約 {1:N1} GB（書籍與設定會保留）。" -f $parts.Count, $total) 'Yellow'
        foreach ($part in $parts) {
            $destination = Join-Path $Work $part.name
            Say "下載 $($part.name)..."
            Get-Asset $part $destination
            $Zips += $destination
        }
    }
} else {
    # 離線：使用「下載」資料夾中手動下載的檔案
    $downloads = if ($DownloadsDir) { $DownloadsDir } else { Join-Path $env:USERPROFILE 'Downloads' }
    $update = Get-ChildItem $downloads -Filter "$Prefix-update*.zip" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $parts = @(Get-ChildItem $downloads -Filter "$Prefix-part*.zip" -ErrorAction SilentlyContinue | Sort-Object Name)
    if ($update -and $LocalBuild) {
        $Zips = @($update.FullName)
    } elseif ($parts.Count -gt 0) {
        $Zips = @($parts | ForEach-Object { $_.FullName })
    } else {
        Stop-Update '找不到更新檔。請到 GitHub Release 頁面下載所有 part*.zip（或 update.zip）到「下載」資料夾後再執行。'
    }
    Say "使用「下載」資料夾中的 $($Zips.Count) 個檔案更新。"
}

# 4. 解壓縮（每解完一個就刪掉下載檔，節省磁碟空間）
foreach ($zip in $Zips) {
    Say "解壓縮 $(Split-Path $zip -Leaf)..."
    & tar.exe -xf $zip -C $Staging
    if ($LASTEXITCODE -ne 0) { Stop-Update "解壓縮失敗：$zip" }
    if ($zip.StartsWith($Work)) { Remove-Item $zip -Force }
}
$Source = Join-Path $Staging 'Saber-Translator'
if (-not (Test-Path $Source)) { Stop-Update '更新檔內容不正確。' }

$UpdateInfo = $null
$UpdateInfoFile = Join-Path $Source 'UPDATE-INFO.json'
if (Test-Path $UpdateInfoFile) {
    $UpdateInfo = Get-Content $UpdateInfoFile -Raw -Encoding UTF8 | ConvertFrom-Json
    Remove-Item $UpdateInfoFile -Force
    if ($UpdateInfo.base -ne $LocalBuild) {
        Stop-Update "這個更新包只適用於 $($UpdateInfo.base) 版，你目前是 $LocalBuild 版。請改用完整分卷（part1、part2…）更新。"
    }
}

# 5. 套用：複製新檔案，完全排除 data-v2
Say '套用更新中（data-v2 不會被改動）...'
& robocopy.exe $Source $App /E /XD data-v2 /R:2 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) {
    Stop-Update "複製檔案失敗（robocopy 代碼 $LASTEXITCODE）。請確認 Saber-Translator 已關閉後再執行一次。"
}
if ($UpdateInfo -and $UpdateInfo.deleted) {
    foreach ($relative in $UpdateInfo.deleted) {
        if ($relative -like 'data-v2*') { continue }
        $target = Join-Path $App ($relative -replace '/', '\')
        if (Test-Path $target) { Remove-Item $target -Force }
    }
}
Remove-Item $Work -Recurse -Force -ErrorAction SilentlyContinue

$NewBuild = ''
if (Test-Path $BuildFile) { $NewBuild = (Get-Content $BuildFile -Raw | ConvertFrom-Json).build }
Say "更新完成！目前版本：$NewBuild。你的書籍、設定、API Key、術語表都已保留。" 'Green'
Say '現在可以重新開啟 Saber-Translator.exe。'
