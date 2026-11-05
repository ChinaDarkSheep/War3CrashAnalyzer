# 魔兽 RPG 地图崩溃定位分析工具 (PowerShell 零依赖版)
# 支持环境：KK对战平台 / 本地单机测试

$ErrorActionPreference = "SilentlyContinue"
$Host.UI.RawUI.WindowTitle = "War3 Crash Analyzer - Zero Dependency"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   魔兽 RPG 崩溃分析工具 (PowerShell 版)                  " -ForegroundColor Cyan
Write-Host "   无需 Python，直接右键运行                              " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# --- 路径自动识别逻辑 ---
function Get-War3ErrorPath {
    $docsPath = [System.IO.Path]::Combine([Environment]::GetFolderPath("MyDocuments"), "Warcraft III", "Errors")
    $kkPathC = "C:\Program Files (x86)\NetEase\KK\Warcraft III\Errors"
    $kkPathD = "D:\Program Files (x86)\NetEase\KK\Warcraft III\Errors"
    $localPath = Join-Path (Get-Location) "Errors"

    $paths = @($docsPath, $kkPathC, $kkPathD, $localPath)
    
    foreach ($p in $paths) {
        if (Test-Path $p) {
            return $p
        }
    }
    return $null
}

$errorDir = Get-War3ErrorPath

if (-not $errorDir) {
    Write-Host "[!] 未能自动识别日志目录。" -ForegroundColor Yellow
    $errorDir = Read-Host "请粘贴魔兽 Errors 文件夹的完整路径"
}

Write-Host "[*] 正在监控目录: $errorDir" -ForegroundColor Green
Write-Host "[*] 请开始游戏测试，发生崩溃后此处将显示分析结果..." -ForegroundColor Gray

# --- 核心分析函数 ---
function Analyze-CrashFile($filePath) {
    Write-Host "`n[分析报告] 发现新崩溃日志: $(Split-Path $filePath -Leaf)" -ForegroundColor White -BackgroundColor DarkBlue
    $content = Get-Content $filePath -Raw -Encoding UTF8
    
    # 提取异常代码
    if ($content -match "Exception: (0x[0-9a-fA-F]+) \(([^)]+)\)") {
        $code = $matches[1]
        $desc = $matches[2]
        Write-Host "----------------------------------------------------------"
        Write-Host "异常类型: $code ($desc)" -ForegroundColor Red
    }

    # 提取错误地址
    if ($content -match "referenced memory at '(0x[0-9a-fA-F]+)'") {
        $memAddr = $matches[1]
        Write-Host "引用内存: $memAddr"
        if ($memAddr -eq "0x00000000") {
            Write-Host ">>> 判定: 【空指针引用】。建议检查单位、技能目标是否未判断是否存在。" -ForegroundColor Yellow
        }
    }

    # 提取堆栈 (简单提取前5层)
    Write-Host "`n堆栈回溯 (Stack Trace):"
    $lines = $content -split "`n"
    $stackCount = 0
    foreach ($line in $lines) {
        if ($line -match "(0x[0-9a-fA-F]+)\s+<([^+>]+)\+?(0x[0-9a-fA-F]+)?>") {
            Write-Host "  #$stackCount $($matches[2]) + $($matches[3]) ($($matches[1]))"
            $stackCount++
            if ($stackCount -ge 5) { break }
        }
    }

    # 简单死循环判定
    if ($content.Contains("Stack Trace") -and $stackCount -gt 3) {
        Write-Host "`n[诊断建议]" -ForegroundColor Cyan
        Write-Host "- 如果堆栈中出现大量重复的 Game.dll 偏移，请检查触发器是否存在死循环。"
    }
    Write-Host "----------------------------------------------------------"
}

# --- 实时文件监控 ---
$lastFile = Get-ChildItem $errorDir -Filter "*.txt" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

while ($true) {
    $currentLatest = Get-ChildItem $errorDir -Filter "*.txt" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    
    if ($currentLatest -and ($null -eq $lastFile -or $currentLatest.LastWriteTime -gt $lastFile.LastWriteTime)) {
        Start-Sleep -Seconds 1 # 等待文件写入完成
        Analyze-CrashFile $currentLatest.FullName
        $lastFile = $currentLatest
    }
    
    Start-Sleep -Seconds 2
}
