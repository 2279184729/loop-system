"""
Claude Code 父子多层嵌套自适应Loop系统 - 工具函数
==================================================
"""

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from config import Colors, LOGS_DIR, WORKSPACES_DIR

# ============================================================
# 跨平台兼容层
# ============================================================
_IS_WINDOWS = sys.platform == "win32"

# 常见 Unix → Windows 命令映射
_UNIX_TO_WIN_CMD = {
    "ls": "dir",
    "cat": "type",
    "cp": "copy",
    "mv": "move",
    "rm": "del",
    "rmdir": "rmdir",
    "grep": "findstr",
    "which": "where",
    "touch": "echo. >",  # 近似
    "clear": "cls",
    "pwd": "cd",
}

# Windows 上可用的 Unix shell 优先级
_UNIX_SHELLS = ["bash", "wsl", "zsh", "sh"]


def _find_unix_shell() -> Optional[str]:
    """在 Windows 上查找可用的 Unix shell（Git Bash / WSL / MSYS2）"""
    if not _IS_WINDOWS:
        return None
    for shell in _UNIX_SHELLS:
        if shutil.which(shell):
            return shell
    return None


def _get_shell() -> Optional[str]:
    """返回当前平台可用的最佳 shell，None 表示使用系统默认"""
    if not _IS_WINDOWS:
        return None  # Linux/macOS 直接用默认 shell
    return _find_unix_shell()


def _translate_command(command: str) -> str:
    """将常见 Unix 命令翻译为 Windows 等效命令"""
    if not _IS_WINDOWS:
        return command

    shell = _find_unix_shell()
    if shell:
        # 有 Unix shell 可用，直接透传
        return command

    # 没有 Unix shell，翻译常见命令
    parts = command.strip().split(maxsplit=1)
    base_cmd = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    if base_cmd in _UNIX_TO_WIN_CMD:
        win_cmd = _UNIX_TO_WIN_CMD[base_cmd]
        if base_cmd == "rm" and args.startswith("-rf "):
            return f"rmdir /s /q {args[4:]}"
        elif base_cmd == "rm" and args.startswith("-r "):
            return f"rmdir /s /q {args[3:]}"
        elif base_cmd == "rm":
            return f"del /q {args}"
        elif base_cmd == "touch":
            return f"type nul > {args}"
        elif base_cmd == "grep":
            return f"findstr {args}"
        return f"{win_cmd} {args}".strip()

    return command

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
    workspace = WORKSPACES_DIR / name
    if workspace.exists():
        shutil.rmtree(workspace)

# ============================================================
# Claude CLI 调用
# ============================================================
def run_claude_cli(prompt: str, workspace: str, timeout: int = 3600) -> Dict:
    """
    调用 claude CLI 执行任务（非交互模式）
    返回: {"success": bool, "output": str, "errors": str}
    """
    # 确保 workspace 有权限配置，允许文件操作
    ws_path = Path(workspace)
    ws_path.mkdir(parents=True, exist_ok=True)
    claude_dir = ws_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings_file = claude_dir / "settings.local.json"
    if not settings_file.exists():
        settings_file.write_text(json.dumps({
            "permissions": {
                "allow": [
                    "Read(*)",
                    "Write(*)",
                    "Edit(*)",
                    "Bash(*)",
                    "Glob(*)",
                    "Grep(*)"
                ]
            }
        }, indent=2), encoding='utf-8')

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--add-dir", workspace],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workspace,
            encoding='utf-8',
            errors='replace'
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "errors": result.stderr,
            "return_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"任务超时 ({timeout}s)"}
    except FileNotFoundError:
        return {"success": False, "error": "claude CLI 未找到，请确保已安装 Claude Code"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def parse_json_from_output(output: str) -> Optional[Any]:
    """从 claude CLI 输出中提取 JSON（支持 markdown 代码块）"""
    raw = output
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]
    try:
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return None


# ============================================================
# 子Agent调度
# ============================================================
def run_child_agent(workspace: str, task: Dict, project_dir: str = None,
                    timeout: int = 3600) -> Dict:
    """
    使用 claude CLI 执行子任务
    返回: {success, output, errors, workspace, summary}
    """
    # 确保工作区目录存在
    ws_path = Path(workspace)
    ws_path.mkdir(parents=True, exist_ok=True)

    task_id = task.get("id", "???")
    task_name = task.get("name", "Unknown")
    task_desc = task.get("description", "")
    module_type = task.get("module_type", "backend")
    completion_criteria = task.get("completion_criteria", "")

    prompt_parts = [
        f"## 子任务 [{task_id}]: {task_name}",
        "",
        f"**模块类型**: {module_type}",
        f"**任务描述**: {task_desc}",
    ]
    if completion_criteria:
        prompt_parts.append(f"**完成标准**: {completion_criteria}")
    if project_dir:
        prompt_parts.append(f"**项目目录**（只读参考）: {project_dir}")

    prompt_parts.extend([
        "",
        f"**工作区目录**: {workspace}",
        "所有输出文件必须写入此工作区目录。",
        "",
        "**工作流程**:",
        "1. 如需了解项目上下文，先读取项目目录中的相关文件",
        "2. 在工作区中创建/修改你负责的模块文件",
        "3. 运行测试验证你的代码",
        "4. 如果测试失败，分析错误并修复",
        "5. 确认完成标准已满足后，总结完成内容",
        "",
        "**重要原则**:",
        "- 只专注于分配给你的子任务",
        "- 生成生产级质量的代码",
        "- 确保代码可独立运行和测试",
        "- 跨平台兼容",
    ])

    prompt = "\n".join(prompt_parts)
    result = run_claude_cli(prompt, workspace, timeout)
    result["workspace"] = workspace
    if result["success"]:
        result["summary"] = result.get("output", "")[:500]
    return result


def run_agent_loop(task_description: str, workspace: str,
                   system_prompt: str = "", project_dir: str = None,
                   max_iterations: int = 5) -> Dict:
    """
    通过 claude CLI 执行 Agent Loop 任务
    返回: {success, result, files_created}
    """
    prompt_parts = []
    if system_prompt:
        prompt_parts.append(system_prompt)
    prompt_parts.append(task_description)
    if project_dir:
        prompt_parts.append(f"\n项目目录（只读参考）: {project_dir}")
    prompt_parts.append(f"\n工作区: {workspace}")

    prompt = "\n\n".join(prompt_parts)

    result = run_claude_cli(prompt, workspace, timeout=max_iterations * 600)
    files_created = _find_created_files(workspace)

    return {
        "success": result["success"],
        "result": result.get("output", result.get("error", "")),
        "files_created": files_created,
    }


def _find_created_files(workspace: str) -> List[str]:
    """列出工作区中的文件"""
    ws_path = Path(workspace)
    if not ws_path.exists():
        return []
    files = []
    for item in ws_path.rglob("*"):
        if item.is_file() and ".claude" not in item.parts:
            files.append(str(item.relative_to(ws_path)))
    return files

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