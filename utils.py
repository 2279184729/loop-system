"""
Claude Code 父子多层嵌套自适应Loop系统 - 工具函数
==================================================
"""

import json
import time
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from config import (
    Colors, SIMPLE_TASK_KEYWORDS, COMPLEX_TASK_KEYWORDS,
    LOGS_DIR, WORKSPACES_DIR
)

# ============================================================
# 终端输出工具
# ============================================================
def print_banner(text: str, color: str = Colors.CYAN):
    """打印横幅"""
    width = 80
    print(f"\n{color}{'='*width}{Colors.END}")
    print(f"{color}{Colors.BOLD}{text.center(width)}{Colors.END}")
    print(f"{color}{'='*width}{Colors.END}\n")

def print_phase(text: str, color: str = Colors.BLUE):
    """打印阶段标题"""
    print(f"\n{color}{Colors.BOLD}┌── {text} ──┐{Colors.END}")

def print_step(text: str, color: str = Colors.CYAN):
    """打印步骤"""
    print(f"{color}  ➤ {text}{Colors.END}")

def print_success(text: str):
    """打印成功信息"""
    print(f"{Colors.GREEN}  ✅ {text}{Colors.END}")

def print_error(text: str):
    """打印错误信息"""
    print(f"{Colors.RED}  ❌ {text}{Colors.END}")

def print_warning(text: str):
    """打印警告"""
    print(f"{Colors.YELLOW}  ⚠️  {text}{Colors.END}")

def print_info(text: str):
    """打印信息"""
    print(f"{Colors.DIM}  ℹ️  {text}{Colors.END}")

def print_subtask(task_id: str, name: str, status: str):
    """打印子任务状态"""
    status_icons = {
        "pending": "⏳",
        "running": "🔄",
        "completed": "✅",
        "failed": "❌"
    }
    icon = status_icons.get(status, "❓")
    print(f"  {icon} [{task_id}] {name}")

# ============================================================
# 复杂度判定引擎
# ============================================================
def analyze_complexity(task_description: str) -> Dict[str, Any]:
    """
    自适应复杂度判定引擎
    返回: {is_complex, confidence, reasons, suggested_mode}
    """
    task_lower = task_description.lower()

    simple_score = 0
    complex_score = 0
    simple_matches = []
    complex_matches = []

    # 关键词匹配
    for keyword in SIMPLE_TASK_KEYWORDS:
        if keyword.lower() in task_lower:
            simple_score += 1
            simple_matches.append(keyword)

    for keyword in COMPLEX_TASK_KEYWORDS:
        if keyword.lower() in task_lower:
            complex_score += 2  # 复杂关键词权重大
            complex_matches.append(keyword)

    # 额外启发式规则
    # 文件数量推论
    if "多个文件" in task_lower or "多文件" in task_lower:
        complex_score += 3

    # 跨模块推论
    if any(kw in task_lower for kw in ["前后端", "fullstack", "全栈", "端到端", "end-to-end"]):
        complex_score += 5

    # 判定结果
    if complex_score > simple_score:
        is_complex = True
        confidence = min(0.95, complex_score / max(complex_score + simple_score, 1))
        suggested_mode = "multi_agent"
    elif simple_score > complex_score:
        is_complex = False
        confidence = min(0.95, simple_score / max(complex_score + simple_score, 1))
        suggested_mode = "direct"
    else:
        # 分数相等，默认走复杂模式（安全起见）
        is_complex = True
        confidence = 0.5
        suggested_mode = "multi_agent"

    return {
        "is_complex": is_complex,
        "confidence": round(confidence, 2),
        "simple_score": simple_score,
        "complex_score": complex_score,
        "simple_matches": simple_matches,
        "complex_matches": complex_matches,
        "suggested_mode": suggested_mode
    }

# ============================================================
# 日志系统
# ============================================================
class Logger:
    """统一日志系统"""

    def __init__(self, name: str = "orchestrator"):
        self.name = name
        self.log_file = LOGS_DIR / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.entries: List[Dict] = []

    def log(self, level: str, message: str, **kwargs):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            **kwargs
        }
        self.entries.append(entry)

        # 写入文件
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def info(self, message: str, **kwargs):
        self.log("INFO", message, **kwargs)
        print_info(message)

    def success(self, message: str, **kwargs):
        self.log("SUCCESS", message, **kwargs)
        print_success(message)

    def error(self, message: str, **kwargs):
        self.log("ERROR", message, **kwargs)
        print_error(message)

    def warning(self, message: str, **kwargs):
        self.log("WARNING", message, **kwargs)
        print_warning(message)

    def get_summary(self) -> Dict:
        """获取日志摘要"""
        levels = {}
        for entry in self.entries:
            level = entry["level"]
            levels[level] = levels.get(level, 0) + 1
        return {
            "total_entries": len(self.entries),
            "by_level": levels,
            "log_file": str(self.log_file)
        }

# ============================================================
# 工作区管理
# ============================================================
def setup_workspace(name: str) -> Path:
    """创建独立工作区"""
    workspace = WORKSPACES_DIR / name
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace

def cleanup_workspace(name: str):
    """清理工作区"""
    import shutil
    workspace = WORKSPACES_DIR / name
    if workspace.exists():
        shutil.rmtree(workspace)

# ============================================================
# 子进程管理
# ============================================================
def run_child_agent(workspace: str, task: Dict, timeout: int = 3600) -> Dict:
    """
    启动子Agent进程
    返回: {success, output, errors, iterations}
    """
    task_json = json.dumps(task, ensure_ascii=False)
    child_script = Path(__file__).parent / "child_agent.py"

    try:
        result = subprocess.run(
            [sys.executable, str(child_script), "--task", task_json, "--workspace", workspace],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )

        try:
            output = json.loads(result.stdout.strip().split('\n')[-1])
        except:
            output = {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr,
                "return_code": result.returncode
            }

        return output
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Task timeout", "timeout": timeout}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================
# 时间追踪
# ============================================================
class Timer:
    """计时器"""
    def __init__(self):
        self.start_time = time.time()
        self.checkpoints: Dict[str, float] = {}

    def checkpoint(self, name: str):
        self.checkpoints[name] = time.time() - self.start_time

    def elapsed(self) -> float:
        return time.time() - self.start_time

    def summary(self) -> Dict:
        return {
            "total_seconds": self.elapsed(),
            "checkpoints": self.checkpoints
        }