# Saber-Translator 更新程式
# 只更新程式檔案；data-v2（書籍、設定、API Key、術語表）完全不會被改動。
param(
    [switch]$Offline,                     # 不連 GitHub，只用下載資料夾裡的檔案
    [string]$DownloadsDir = '',           # 預設為使用者的「下載」資料夾
    [string]$ReleaseFile = '',            # 測試用：從檔案讀取 Release 資訊
    [switch]$Auto,                        # 由 Saber-Translator.exe 開啟時自動執行：不詢問，更新後重新開啟程式
    [int]$WaitPid = 0                     # 先等這個程序（剛才開啟的 Saber-Translator）結束
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
# 下載中斷後再執行會從中斷處繼續：已下載／已解壓的分卷都保留在這裡，更新完成才刪除
$WorkRoot = Join-Path $env:TEMP 'saber-update'

function Say([string]$Message, [string]$Color = 'White') { Write-Host $Message -ForegroundColor $Color }
function Start-Saber {
    # 重新開啟時略過更新檢查，避免更新失敗時反覆開啟更新程式
    $env:SABER_SKIP_UPDATE_CHECK = '1'
    try { Start-Process -FilePath (Join-Path $App 'Saber-Translator.exe') -WorkingDirectory $App | Out-Null }
    catch { Say "無法自動開啟 Saber-Translator，請手動雙擊 Saber-Translator.exe。（$($_.Exception.Message)）" 'Yellow' }
}
function Ask([string]$Question) {
    try { return (Read-Host $Question) } catch { return '' }
}
function Stop-Update([string]$Message) {
    Say $Message 'Red'
    if ($Auto -and (Test-Path (Join-Path $App 'Saber-Translator.exe'))) {
        Ask '按 Enter 開啟 Saber-Translator（這次先不更新）' | Out-Null
        Start-Saber
    }
    exit 1
}
if ($Auto) {
    try { $Host.UI.RawUI.WindowTitle = 'Saber-Translator 自動更新' } catch { }
    Say 'Saber-Translator 有新版本，正在自動更新（書籍、設定、API Key 都不會被改動）...' 'Cyan'
}

if (-not (Test-Path (Join-Path $App 'Saber-Translator.exe'))) {
    Stop-Update '請把更新程式放在 Saber-Translator.exe 所在的資料夾再執行。'
}

# 1. 關閉執行中的 Saber-Translator（自動更新時先等剛才開啟的程式自己結束）
if ($WaitPid -gt 0) {
    Wait-Process -Id $WaitPid -Timeout 60 -ErrorAction SilentlyContinue
}
$running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -and $_.Path.StartsWith($App, [StringComparison]::OrdinalIgnoreCase)
})
if ($running.Count -gt 0) {
    Say 'Saber-Translator 正在執行，更新前需要先關閉。' 'Yellow'
    $answer = Ask '要自動關閉嗎？(Y/N)'
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
    if ($ReleaseFile) {
        $Release = Get-Content $ReleaseFile -Raw -Encoding UTF8 | ConvertFrom-Json
    } else {
        $Release = Get-Release $Token
    }
} catch {
    if ($Offline) {
        Say '離線模式：使用下載資料夾裡的更新檔。'
    } elseif ($Auto) {
        Stop-Update ('無法連線到 GitHub（' + $_.Exception.Message + '），這次先不更新。')
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

function Invoke-Curl($Asset, [string]$Destination) {
    # -C - ：檔案已有一部分時，從中斷處繼續下載
    $curlArgs = @('-L', '--fail', '-C', '-', '-o', $Destination, '-H', 'User-Agent: Saber-Updater')
    if ($Token) {
        $curlArgs += @('-H', "Authorization: Bearer $Token", '-H', 'Accept: application/octet-stream', $Asset.url)
    } else {
        $curlArgs += $Asset.browser_download_url
    }
    & curl.exe @curlArgs
}

function Test-Asset($Asset, [string]$Path) {
    $expected = [int64]$Asset.size
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    if ($expected -gt 0 -and (Get-Item -LiteralPath $Path).Length -ne $expected) { return $false }
    if ($Asset.digest -and "$($Asset.digest)".StartsWith('sha256:')) {
        $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        return $hash -eq "$($Asset.digest)".Substring(7).ToLowerInvariant()
    }
    return $true
}

function Get-Asset($Asset, [string]$Destination) {
    $expected = [int64]$Asset.size
    if (Test-Path -LiteralPath $Destination) {
        $have = (Get-Item -LiteralPath $Destination).Length
        if ($expected -gt 0 -and $have -eq $expected -and (Test-Asset $Asset $Destination)) {
            Say "$($Asset.name) 上次已下載完成，略過。" 'Green'
            return
        }
        if ($expected -gt 0 -and $have -lt $expected -and $have -gt 0) {
            Say ("繼續上次中斷的下載（已完成 {0:N0} / {1:N0} MB）..." -f ($have / 1MB), ($expected / 1MB))
        } else {
            Remove-Item -LiteralPath $Destination -Force
        }
    }
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        Invoke-Curl $Asset $Destination
        $code = $LASTEXITCODE
        if ($code -eq 33 -or $code -eq 36) {
            # 伺服器不支援續傳：刪掉重新下載
            Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
            Invoke-Curl $Asset $Destination
            $code = $LASTEXITCODE
        }
        if ($code -eq 0) {
            if (Test-Asset $Asset $Destination) { return }
            Say "$($Asset.name) 檔案不完整或已損壞，重新下載..." 'Yellow'
            Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
        } elseif ($attempt -lt 5) {
            Say "下載中斷（curl 代碼 $code），$($attempt * 5) 秒後從中斷處繼續..." 'Yellow'
        }
        if ($attempt -lt 5) { Start-Sleep -Seconds ($attempt * 5) }
    }
    Stop-Update "下載失敗：$($Asset.name)。請確認網路後再執行一次 Update-Saber.bat，已下載的部分會保留。"
}

function Assert-FreeSpace($Assets) {
    # 暫存空間：尚未完成的分卷解壓後的大小，加上解壓時暫留的一個 zip
    $pending = @($Assets | Where-Object { -not (Test-Path -LiteralPath ((Join-Path $Work $_.name) + '.done')) })
    if ($pending.Count -eq 0) { return }
    $sizes = @($pending | ForEach-Object { [int64]$_.size })
    $needed = ($sizes | Measure-Object -Sum).Sum + ($sizes | Measure-Object -Maximum).Maximum + 512MB
    $drive = $WorkRoot.Substring(0, 1)
    $free = $null
    try { $free = (Get-PSDrive -Name $drive -ErrorAction Stop).Free } catch { return }
    if ($free -and $free -lt $needed) {
        Stop-Update ("{0} 槽空間不足：更新需要約 {1:N1} GB 暫存空間，目前只剩 {2:N1} GB。請清出空間後再執行（已下載的部分會保留）。" -f $drive, ($needed / 1GB), ($free / 1GB))
    }
}

function Use-WorkDir([string]$Name) {
    # 只保留這一版的下載資料夾；其他版本（或舊版更新程式）留下的暫存檔都清掉
    New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
    Get-ChildItem -LiteralPath $WorkRoot -Force | Where-Object { $_.Name -ne $Name } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    $dir = Join-Path $WorkRoot $Name
    New-Item -ItemType Directory -Force -Path (Join-Path $dir 'staging') | Out-Null
    return $dir
}

# 下載（可續傳）→ 檢查 → 解壓 → 標記完成 → 刪掉 zip；中斷後再執行會跳過已完成的分卷
function Get-AndExtract($Asset) {
    $destination = Join-Path $Work $Asset.name
    $doneMark = "$destination.done"
    if (Test-Path -LiteralPath $doneMark) {
        Say "$($Asset.name) 上次已下載並解壓縮，略過。" 'Green'
        return
    }
    Say "下載 $($Asset.name)..."
    Get-Asset $Asset $destination
    Expand-Part $destination
    Set-Content -LiteralPath $doneMark -Value 'ok'
    Remove-Item -LiteralPath $destination -Force
}

function Expand-Part([string]$Zip) {
    Say "解壓縮 $(Split-Path $Zip -Leaf)..."
    & tar.exe -xf $Zip -C $Staging
    if ($LASTEXITCODE -ne 0) { Stop-Update "解壓縮失敗：$Zip。請再執行一次 Update-Saber.bat。" }
}

if ($Release) {
    $assets = @{}
    foreach ($asset in $Release.assets) { $assets[$asset.name] = $asset }
    New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
    $info = $null
    if ($assets.ContainsKey('update-info.json')) {
        $infoPath = Join-Path $WorkRoot 'update-info.json'
        Remove-Item -LiteralPath $infoPath -Force -ErrorAction SilentlyContinue
        Get-Asset $assets['update-info.json'] $infoPath
        $info = Get-Content $infoPath -Raw -Encoding UTF8 | ConvertFrom-Json
        Remove-Item -LiteralPath $infoPath -Force
    }
    $RemoteBuild = if ($info) { $info.build } else { ($Release.name -split ' ')[-1] }
    if ($LocalBuild -and $LocalBuild -eq $RemoteBuild) {
        Say "已經是最新版本（$LocalBuild），不需要更新。" 'Green'
        Remove-Item $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
        if ($Auto) { Start-Saber }
        exit 0
    }
    $Work = Use-WorkDir ('build-' + ($RemoteBuild -replace '[^A-Za-z0-9._-]', '_'))
    $Staging = Join-Path $Work 'staging'
    if ($info -and $LocalBuild -and $info.base -eq $LocalBuild -and $assets.ContainsKey("$Prefix-update.zip")) {
        $update = $assets["$Prefix-update.zip"]
        Say ("小型更新包（{0} → {1}，約 {2:N0} MB）" -f $LocalBuild, $RemoteBuild, ($update.size / 1MB))
        Assert-FreeSpace @($update)
        Get-AndExtract $update
    } else {
        $parts = @($Release.assets | Where-Object { $_.name -like "$Prefix-part*.zip" } | Sort-Object name)
        if ($parts.Count -eq 0) { Stop-Update 'GitHub 上找不到更新檔，請稍後再試。' }
        $total = ($parts | Measure-Object -Property size -Sum).Sum / 1GB
        Say ("需要下載完整程式：{0} 個分卷，約 {1:N1} GB（書籍與設定會保留）。" -f $parts.Count, $total) 'Yellow'
        if ($Auto) {
            # 版本差太多才需要完整下載，時間較長，先問一聲
            $answer = Ask '這次需要下載完整程式，時間較長。現在下載嗎？(Y/N)'
            if ($answer -notmatch '^[Yy]') {
                New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
                Set-Content -LiteralPath (Join-Path $DataDir 'update-skipped.txt') -Value $RemoteBuild -Encoding ASCII
                Say '已略過這個版本，開啟程式時不會再詢問；之後要更新請雙擊 Update-Saber.bat。' 'Yellow'
                Start-Saber
                exit 0
            }
        }
        Say '中途關掉視窗或斷線也沒關係：再執行一次會從中斷處繼續，已下載的分卷不會重新下載。'
        Assert-FreeSpace $parts
        foreach ($part in $parts) { Get-AndExtract $part }
    }
} else {
    # 離線：使用「下載」資料夾中手動下載的檔案（不會刪除這些檔案）
    $Work = Use-WorkDir 'offline'
    $Staging = Join-Path $Work 'staging'
    Remove-Item (Join-Path $Staging '*') -Recurse -Force -ErrorAction SilentlyContinue
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
    foreach ($zip in $Zips) { Expand-Part $zip }
}

$Source = Join-Path $Staging 'Saber-Translator'
if (-not (Test-Path $Source)) { Stop-Update '更新檔內容不正確。' }

$UpdateInfo = $null
$UpdateInfoFile = Join-Path $Source 'UPDATE-INFO.json'
if (Test-Path $UpdateInfoFile) {
    $UpdateInfo = Get-Content $UpdateInfoFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($UpdateInfo.base -ne $LocalBuild) {
        Remove-Item $Work -Recurse -Force -ErrorAction SilentlyContinue
        Stop-Update "這個更新包只適用於 $($UpdateInfo.base) 版，你目前是 $LocalBuild 版。請改用完整分卷（part1、part2…）更新。"
    }
}

# 5. 套用：複製新檔案，完全排除 data-v2。
# BUILD.json 最後才複製：中途關掉視窗時版本號仍是舊的，再執行一次會用暫存的檔案重新套用。
Say '套用更新中（data-v2 不會被改動，請不要關閉視窗）...'
& robocopy.exe $Source $App /E /XD data-v2 /XF BUILD.json UPDATE-INFO.json /R:2 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
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
if (Test-Path (Join-Path $Source 'BUILD.json')) { Copy-Item (Join-Path $Source 'BUILD.json') $BuildFile -Force }
Remove-Item $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue

$NewBuild = ''
if (Test-Path $BuildFile) { $NewBuild = (Get-Content $BuildFile -Raw | ConvertFrom-Json).build }
Remove-Item -LiteralPath (Join-Path $DataDir 'update-skipped.txt') -Force -ErrorAction SilentlyContinue
Say "更新完成！目前版本：$NewBuild。你的書籍、設定、API Key、術語表都已保留。" 'Green'
if ($Auto) {
    Say '正在重新開啟 Saber-Translator...'
    Start-Saber
    Start-Sleep -Seconds 2
} else {
    Say '現在可以重新開啟 Saber-Translator.exe。'
}
