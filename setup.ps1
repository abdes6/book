<#
.SYNOPSIS
  个人藏书管理系统 — 一键安装启动脚本
.DESCRIPTION
  自动完成：环境检测 → 虚拟环境 → 依赖安装 → 配置生成 → 数据库初始化 → 启动
  用法: .\setup.ps1
#>

$ErrorActionPreference = "Stop"
$rootDir = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  个人藏书管理系统 — 一键安装启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. 检测 Python ──
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "[ERROR] 未找到 Python，请先安装 Python 3.10+" -ForegroundColor Red
    exit 1
}
$pyVer = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "[INFO] Python $pyVer ($($py.Source))" -ForegroundColor Green

# ── 2. 创建虚拟环境 ──
$venvDir = Join-Path $rootDir "venv"
if (-not (Test-Path $venvDir)) {
    Write-Host "[...] 创建虚拟环境..." -ForegroundColor Yellow
    & python -m venv $venvDir
    if (-not $?) { Write-Host "[ERROR] 虚拟环境创建失败" -ForegroundColor Red; exit 1 }
} else {
    Write-Host "[OK] 虚拟环境已存在" -ForegroundColor Green
}
$pip = Join-Path $venvDir "Scripts" "pip.exe"
$python = Join-Path $venvDir "Scripts" "python.exe"

# ── 3. 安装依赖 ──
Write-Host "[...] 安装依赖..." -ForegroundColor Yellow
& $pip install -r (Join-Path $rootDir "requirements.txt") --quiet
if (-not $?) { Write-Host "[ERROR] 依赖安装失败" -ForegroundColor Red; exit 1 }

# ── 4. 生成 .env（若不存在） ──
$envFile = Join-Path $rootDir ".env"
if (-not (Test-Path $envFile)) {
    # 生成随机 SECRET_KEY
    $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789".ToCharArray()
    $secret = -join (1..64 | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
    $dsKey = "your-deepseek-api-key"
    @"
# Flask 会话签名密钥（自动生成，请勿修改）
SECRET_KEY=$secret

# DeepSeek AI API 密钥（必填，AI 功能需要）
# 注册获取：https://platform.deepseek.com
DEEPSEEK_API_KEY=$dsKey
"@ | Set-Content $envFile -Encoding UTF8
    Write-Host ""
    Write-Host "[WARN] .env 文件已生成！请编辑 DEEPSEEK_API_KEY：" -ForegroundColor Yellow
    Write-Host "       打开 $envFile" -ForegroundColor Yellow
    Write-Host "       将 DEEPSEEK_API_KEY 替换为你的密钥（从 https://platform.deepseek.com 获取）" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "按回车键继续启动（或 Ctrl+C 退出编辑）..." -ForegroundColor Gray
    $null = Read-Host
} else {
    Write-Host "[OK] .env 已存在" -ForegroundColor Green
}

# ── 5. 禁用代理 + 启动 ──
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -Name ProxyEnable -Value 0
Write-Host ""
Write-Host "[...] 启动应用..." -ForegroundColor Yellow
Write-Host "访问地址：http://localhost:5000" -ForegroundColor Cyan
Write-Host ""
& $python (Join-Path $rootDir "run.py")
