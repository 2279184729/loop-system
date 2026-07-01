"""
Claude Code 父子多层嵌套自适应Loop系统 - 工具函数
==================================================
"""

import json
import time
import subprocess
import sys
import os
import shutil
import shlex
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from config import (
    Colors, SIMPLE_TASK_KEYWORDS, COMPLEX_TASK_KEYWORDS,
    LOGS_DIR, WORKSPACES_DIR, ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    ANTHROPIC_BASE_URL, TOOL_DEFINITIONS
)

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
def run_child_agent(workspace: str, task: Dict, project_dir: str = None,
                    timeout: int = 3600) -> Dict:
    """
    启动子Agent进程
    返回: {success, output, errors, iterations}
    """
    task_json = json.dumps(task, ensure_ascii=False)
    child_script = Path(__file__).parent / "child_agent.py"

    cmd = [sys.executable, str(child_script), "--task", task_json, "--workspace", workspace]
    if project_dir:
        cmd.extend(["--project-dir", project_dir])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )

        # 从输出中提取 __RESULT__ 标记后的 JSON
        output = result.stdout
        if "__RESULT__" in output:
            json_str = output.split("__RESULT__")[-1].strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 回退：尝试解析最后一行
        try:
            return json.loads(output.strip().split('\n')[-1])
        except (json.JSONDecodeError, IndexError):
            return {
                "success": result.returncode == 0,
                "output": output,
                "errors": result.stderr,
                "return_code": result.returncode
            }

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

# ============================================================
# Claude API 客户端
# ============================================================
def create_llm_client():
    """创建 Anthropic API 客户端"""
    api_key = ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    if not api_key:
        raise RuntimeError(
            "未设置 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN 环境变量。\n"
            "请在 config.py 中设置或通过环境变量导出。"
        )
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key, base_url=ANTHROPIC_BASE_URL)
    except ImportError:
        raise RuntimeError("请安装 anthropic SDK: pip install anthropic")


# ============================================================
# 通用 Agent Loop（Claude API + Tool Use）
# ============================================================
def _execute_single_tool(tool_name: str, tool_input: dict, workspace: str,
                         project_dir: str = None) -> str:
    """执行单个工具调用并返回结果字符串"""
    ws = Path(workspace)
    proj = Path(project_dir) if project_dir else ws

    try:
        if tool_name == "read_file":
            path = tool_input.get("path", "")
            file_path = Path(path)
            if not file_path.is_absolute():
                # 先尝试工作区，再尝试项目目录
                if (ws / path).exists():
                    file_path = ws / path
                elif proj and (proj / path).exists():
                    file_path = proj / path
                else:
                    file_path = ws / path
            if not file_path.exists():
                return f"错误: 文件不存在: {file_path}"
            content = file_path.read_text(encoding='utf-8', errors='replace')
            return f"文件: {file_path}\n{content}"

        elif tool_name == "write_file":
            path = tool_input.get("path", "")
            content = tool_input.get("content", "")
            file_path = ws / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')
            return f"文件已写入: {file_path} ({len(content)} 字符)"

        elif tool_name == "edit_file":
            path = tool_input.get("path", "")
            old_str = tool_input.get("old_string", "")
            new_str = tool_input.get("new_string", "")
            file_path = ws / path
            if not file_path.exists():
                return f"错误: 文件不存在: {file_path}"
            current = file_path.read_text(encoding='utf-8')
            if old_str not in current:
                return f"错误: 未找到要替换的文本。文件内容:\n{current[:500]}"
            updated = current.replace(old_str, new_str, 1)
            file_path.write_text(updated, encoding='utf-8')
            return f"文件已编辑: {file_path}"

        elif tool_name == "run_command":
            command = tool_input.get("command", "")
            command = _translate_command(command)
            shell = _get_shell()
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=120, cwd=str(ws), encoding='utf-8', errors='replace',
                executable=shell
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]:\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[退出码: {result.returncode}]"
            return output.strip() or "(无输出)"

        else:
            return f"未知工具: {tool_name}"

    except subprocess.TimeoutExpired:
        return "错误: 命令执行超时（120秒）"
    except Exception as e:
        return f"工具执行错误: {type(e).__name__}: {e}"


def run_agent_loop(task_description: str, workspace: str,
                   system_prompt: str, project_dir: str = None,
                   max_iterations: int = 15, tools: list = None) -> Dict:
    """
    运行 Claude API Agent 循环（带工具调用）。
    返回: {"success": bool, "result": str, "iterations": int, "files_created": [...]}
    """
    if tools is None:
        tools = TOOL_DEFINITIONS

    client = create_llm_client()
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)

    messages = [{"role": "user", "content": task_description}]
    files_created = set()

    for iteration in range(1, max_iterations + 1):
        print(f"  {Colors.CYAN}── Agent 迭代 {iteration}/{max_iterations} ──{Colors.END}")

        try:
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=16384,
                system=system_prompt,
                tools=tools,
                messages=messages
            )
        except Exception as e:
            return {
                "success": False,
                "result": f"API 调用失败: {e}",
                "iterations": iteration,
                "files_created": list(files_created)
            }

        # 解析响应
        text_parts = []
        tool_uses = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)
            # 跳过 thinking / redacted_thinking 块

        # 将 assistant 响应添加到消息历史
        messages.append({"role": "assistant", "content": response.content})

        # 如果没有工具调用，Agent 认为任务完成
        if not tool_uses:
            result_text = "\n".join(text_parts)
            print(f"  {Colors.GREEN}✓ Agent 完成 ({iteration} 轮迭代){Colors.END}")
            return {
                "success": True,
                "result": result_text,
                "iterations": iteration,
                "files_created": list(files_created)
            }

        # 执行工具调用
        tool_results = []
        for tool_use in tool_uses:
            print(f"  {Colors.DIM}🔧 {tool_use.name}: {tool_use.input.get('path', tool_use.input.get('command', ''))[:60]}{Colors.END}")
            result = _execute_single_tool(
                tool_use.name, tool_use.input, str(ws), project_dir
            )

            if tool_use.name == "write_file":
                files_created.add(tool_use.input.get("path", ""))

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result[:8000]  # 限制结果长度
            })

        messages.append({"role": "user", "content": tool_results})

    return {
        "success": False,
        "result": f"达到最大迭代次数 ({max_iterations})",
        "iterations": max_iterations,
        "files_created": list(files_created)
    }