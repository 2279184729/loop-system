"""
Claude Code 父子多层嵌套自适应Loop系统
========================================
全栈高阶多Agent方案 - 复杂任务多层嵌套Loop调度
"""

__version__ = "2.2.0"
__author__ = "Loop System"
__description__ = "Claude Code 父子多层嵌套自适应Loop系统"

from .config import (
    Colors, SubTask, LoopState,
    MAX_PLAN_ITERATIONS, MAX_CHILD_ITERATIONS,
    MAX_GLOBAL_FIX_ITERATIONS, TASK_TIMEOUT,
    BASE_DIR, WORKSPACES_DIR, LOGS_DIR
)
from .orchestrator import Orchestrator
from .utils import Logger, Timer, setup_workspace, run_claude_cli

__all__ = [
    "Orchestrator",
    "Logger",
    "Timer",
    "setup_workspace",
    "run_claude_cli",
    "Colors",
    "SubTask",
    "LoopState",
    "MAX_PLAN_ITERATIONS",
    "MAX_CHILD_ITERATIONS",
    "MAX_GLOBAL_FIX_ITERATIONS",
    "TASK_TIMEOUT",
    "BASE_DIR",
    "WORKSPACES_DIR",
    "LOGS_DIR",
    "__version__",
]