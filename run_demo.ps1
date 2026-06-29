# Claude Code 父子多层嵌套自适应Loop系统 - Windows启动脚本
# 双击运行或命令行执行

param(
    [string]$Task = "",
    [switch]$Demo = $false
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Claude Code 父子多层嵌套自适应Loop系统" -ForegroundColor Cyan
Write-Host "  Windows PowerShell Launcher v2.1" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# 检查Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  [OK] Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Python未安装，请先安装Python 3.9+" -ForegroundColor Red
    exit 1
}

# 检查依赖
Write-Host "  [INFO] 检查依赖..." -ForegroundColor Gray
pip install fastapi pydantic 2>&1 | Out-Null

if ($Demo) {
    Write-Host ""
    Write-Host "  启动完整演示模式..." -ForegroundColor Yellow
    Write-Host ""
    python run_demo.py
} elseif ($Task) {
    Write-Host ""
    Write-Host "  执行任务: $Task" -ForegroundColor Yellow
    Write-Host ""
    python orchestrator.py $Task
} else {
    Write-Host ""
    Write-Host "  用法:" -ForegroundColor Yellow
    Write-Host "    .\run_demo.ps1 -Demo              # 运行完整演示" -ForegroundColor Gray
    Write-Host "    .\run_demo.ps1 -Task '任务描述'    # 执行指定任务" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  示例:" -ForegroundColor Yellow
    Write-Host "    .\run_demo.ps1 -Demo" -ForegroundColor Gray
    Write-Host '    .\run_demo.ps1 -Task "修复登录接口空指针bug"' -ForegroundColor Gray
    Write-Host '    .\run_demo.ps1 -Task "从零搭建全栈用户管理系统"' -ForegroundColor Gray
    Write-Host ""

    # 默认运行演示
    Write-Host "  未指定参数，默认启动演示模式..." -ForegroundColor Yellow
    Write-Host ""
    python run_demo.py
}