"""
Claude Code Loop系统 - 状态持久化与断点续传
=============================================
支持任务状态保存、恢复、检查点管理。
崩溃或中断后可从最近的检查点恢复执行。
"""

import json
import pickle
import shutil
import sys
import io
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime
from config import Colors, BASE_DIR

# 修复Windows GBK编码问题（仅当stdout未被重定向时）
if sys.platform == 'win32':
    try:
        if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        pass  # stdout 已被重定向或关闭


class CheckpointManager:
    """
    检查点管理器
    支持任务状态的保存和恢复
    """

    CHECKPOINT_DIR = BASE_DIR / ".checkpoints"

    def __init__(self, task_id: str = None):
        self.task_id = task_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.checkpoint_dir = self.CHECKPOINT_DIR / self.task_id
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints: Dict[str, Path] = {}

    def save(self, name: str, state: Dict[str, Any]) -> Path:
        """
        保存检查点

        Args:
            name: 检查点名称（如 "phase1_plan_done"）
            state: 要保存的状态字典

        Returns:
            检查点文件路径
        """
        timestamp = datetime.now().isoformat()
        checkpoint_data = {
            "name": name,
            "timestamp": timestamp,
            "task_id": self.task_id,
            "state": state
        }

        # 保存 JSON 格式（人类可读）
        json_path = self.checkpoint_dir / f"{name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, ensure_ascii=False, indent=2, default=str)

        # 保存 Pickle 格式（完整Python对象）
        pickle_path = self.checkpoint_dir / f"{name}.pkl"
        with open(pickle_path, 'wb') as f:
            pickle.dump(checkpoint_data, f)

        self.checkpoints[name] = json_path
        print(f"{Colors.DIM}  💾 检查点已保存: {name}{Colors.END}")
        return json_path

    def load(self, name: str) -> Optional[Dict[str, Any]]:
        """
        加载检查点

        Args:
            name: 检查点名称

        Returns:
            状态字典，如果不存在返回 None
        """
        # 优先加载 Pickle（完整对象）
        pickle_path = self.checkpoint_dir / f"{name}.pkl"
        if pickle_path.exists():
            try:
                with open(pickle_path, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                pass

        # 降级加载 JSON
        json_path = self.checkpoint_dir / f"{name}.json"
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        return None

    def load_latest(self) -> Optional[Dict[str, Any]]:
        """
        加载最新的检查点

        Returns:
            最新的状态字典
        """
        if not self.checkpoint_dir.exists():
            return None

        # 找最新的 JSON 文件
        json_files = sorted(
            self.checkpoint_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if json_files:
            name = json_files[0].stem
            return self.load(name)

        return None

    def list_checkpoints(self) -> list:
        """列出所有检查点"""
        if not self.checkpoint_dir.exists():
            return []

        checkpoints = []
        for f in sorted(self.checkpoint_dir.glob("*.json")):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    checkpoints.append({
                        "name": data.get("name"),
                        "timestamp": data.get("timestamp"),
                        "file": str(f)
                    })
            except Exception:
                pass
        return checkpoints

    def cleanup(self, keep_latest: int = 5):
        """
        清理旧检查点

        Args:
            keep_latest: 保留最近几个检查点
        """
        json_files = sorted(
            self.checkpoint_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        for f in json_files[keep_latest:]:
            f.unlink(missing_ok=True)
            # 同时删除对应的 pickle 文件
            pickle_file = f.with_suffix(".pkl")
            pickle_file.unlink(missing_ok=True)

    def delete_all(self):
        """删除所有检查点"""
        if self.checkpoint_dir.exists():
            shutil.rmtree(self.checkpoint_dir)

    def save_orchestrator_state(
        self,
        name: str,
        orchestrator: Any
    ) -> Path:
        """
        保存 Orchestrator 完整状态

        Args:
            name: 检查点名称
            orchestrator: Orchestrator 实例

        Returns:
            检查点文件路径
        """
        state = {
            "phase": orchestrator.state.phase,
            "iteration": orchestrator.state.iteration,
            "total_subtasks": orchestrator.state.total_subtasks,
            "completed_subtasks": orchestrator.state.completed_subtasks,
            "failed_subtasks": orchestrator.state.failed_subtasks,
            "plan": orchestrator.plan,
            "subtasks": [
                {
                    "id": st.id,
                    "name": st.name,
                    "description": st.description,
                    "workspace": st.workspace,
                    "module_type": st.module_type,
                    "dependencies": st.dependencies,
                    "completion_criteria": st.completion_criteria,
                    "priority": st.priority,
                    "max_iterations": st.max_iterations,
                    "status": st.status,
                }
                for st in orchestrator.subtasks
            ],
            "all_results": orchestrator.all_results,
            "elapsed_seconds": orchestrator.timer.elapsed(),
            "project_dir": str(orchestrator.project_dir),
        }
        return self.save(name, state)

    def restore_orchestrator_state(
        self,
        name: str,
        orchestrator: Any
    ) -> bool:
        """
        恢复 Orchestrator 状态

        Args:
            name: 检查点名称
            orchestrator: Orchestrator 实例（会被修改）

        Returns:
            是否恢复成功
        """
        data = self.load(name)
        if not data:
            return False

        state = data.get("state", data)
        if not state:
            return False

        # 恢复状态
        orchestrator.state.phase = state.get("phase", "init")
        orchestrator.state.iteration = state.get("iteration", 0)
        orchestrator.state.total_subtasks = state.get("total_subtasks", 0)
        orchestrator.state.completed_subtasks = state.get("completed_subtasks", 0)
        orchestrator.state.failed_subtasks = state.get("failed_subtasks", 0)
        orchestrator.plan = state.get("plan")
        orchestrator.all_results = state.get("all_results", [])

        # 恢复子任务
        from config import SubTask
        orchestrator.subtasks = []
        for st_data in state.get("subtasks", []):
            st = SubTask(
                id=st_data["id"],
                name=st_data["name"],
                description=st_data.get("description", ""),
                workspace=st_data.get("workspace", ""),
                module_type=st_data.get("module_type", "backend"),
                dependencies=st_data.get("dependencies", []),
                completion_criteria=st_data.get("completion_criteria", ""),
                priority=st_data.get("priority", 0),
                max_iterations=st_data.get("max_iterations", 15),
            )
            st.status = st_data.get("status", "pending")
            orchestrator.subtasks.append(st)

        return True

    @classmethod
    def list_all_tasks(cls) -> list:
        """列出所有任务"""
        if not cls.CHECKPOINT_DIR.exists():
            return []

        tasks = []
        for task_dir in sorted(cls.CHECKPOINT_DIR.iterdir()):
            if task_dir.is_dir():
                json_files = list(task_dir.glob("*.json"))
                if json_files:
                    latest = max(json_files, key=lambda p: p.stat().st_mtime)
                    try:
                        with open(latest, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            tasks.append({
                                "task_id": data.get("task_id"),
                                "latest_checkpoint": data.get("name"),
                                "timestamp": data.get("timestamp"),
                                "checkpoints_count": len(json_files),
                            })
                    except Exception:
                        pass
        return tasks


# 用于保存和恢复简单 Python 对象的辅助函数
def save_json(path: Path, data: dict):
    """保存 JSON 到文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def load_json(path: Path) -> Optional[dict]:
    """从文件加载 JSON"""
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


if __name__ == "__main__":
    # 测试检查点功能
    cm = CheckpointManager("test_task")

    # 保存检查点
    cm.save("phase1_start", {"phase": "plan", "iteration": 1})
    cm.save("phase1_done", {"phase": "plan", "iteration": 2, "plan": {"arch": "test"}})
    cm.save("phase2_done", {"phase": "execute", "completed": 4, "failed": 0})

    # 列出检查点
    print("所有检查点:")
    for cp in cm.list_checkpoints():
        print(f"  - {cp['name']} ({cp['timestamp']})")

    # 加载最新
    latest = cm.load_latest()
    print(f"\n最新检查点: {latest['name']}")

    # 清理
    cm.delete_all()
    print("检查点已清理")