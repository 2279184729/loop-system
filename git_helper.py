"""
Git 集成助手
============
提供自动提交、分支管理、变更摘要、回滚等功能。
为 Loop 系统的产品迭代提供版本控制安全网。
"""

import sys
import io

# 修复Windows GBK编码问题
if sys.platform == 'win32':
    try:
        if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        pass

import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class GitHelper:
    """Git 操作助手"""

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        self._verify_git()

    def _verify_git(self):
        """验证是否在 Git 仓库中"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True, text=True,
                cwd=str(self.repo_path)
            )
            if result.returncode != 0:
                raise RuntimeError(f"不是 Git 仓库: {self.repo_path}")
        except FileNotFoundError:
            raise RuntimeError("Git 未安装")

    def _run(self, args: List[str], check: bool = False) -> subprocess.CompletedProcess:
        """运行 Git 命令"""
        return subprocess.run(
            ["git"] + args,
            capture_output=True, text=True,
            cwd=str(self.repo_path),
            encoding='utf-8', errors='replace'
        )

    # ================================================================
    # 基本操作
    # ================================================================
    def status(self) -> Dict:
        """获取仓库状态"""
        result = self._run(["status", "--porcelain"])
        lines = [l for l in result.stdout.splitlines() if l.strip()]

        modified = [l for l in lines if l.startswith(" M") or l.startswith("M ")]
        added = [l for l in lines if l.startswith("A ") or l.startswith("??")]
        deleted = [l for l in lines if l.startswith(" D") or l.startswith("D ")]

        return {
            "total_changes": len(lines),
            "modified": modified,
            "added": added,
            "deleted": deleted,
            "is_clean": len(lines) == 0,
            "raw": result.stdout
        }

    def auto_commit(self, message: str = None, add_all: bool = True) -> Dict:
        """
        自动提交所有变更

        Args:
            message: 提交信息（默认自动生成）
            add_all: 是否 git add -A

        Returns:
            {"success": bool, "hash": str, "message": str}
        """
        status = self.status()
        if status["is_clean"]:
            return {"success": True, "hash": None, "message": "无变更，跳过提交"}

        if add_all:
            self._run(["add", "-A"])

        if not message:
            # 自动生成提交信息
            changed = status["modified"] + status["added"] + status["deleted"]
            files_summary = ", ".join([c[3:] for c in changed[:5]])
            if len(changed) > 5:
                files_summary += f" ... 还有 {len(changed) - 5} 个文件"
            message = f"auto: {files_summary}"

        result = self._run(["commit", "-m", message])
        if result.returncode == 0:
            # 获取 commit hash
            hash_result = self._run(["rev-parse", "--short", "HEAD"])
            commit_hash = hash_result.stdout.strip()
            return {
                "success": True,
                "hash": commit_hash,
                "message": message,
                "files_changed": len(status["modified"]) + len(status["added"]) + len(status["deleted"])
            }
        else:
            return {"success": False, "hash": None, "message": result.stderr}

    def create_feature_branch(self, name: str) -> Dict:
        """
        创建特性分支

        Args:
            name: 分支名称

        Returns:
            {"success": bool, "branch": str}
        """
        # 清理分支名
        safe_name = name.lower().replace(" ", "-").replace("/", "-")[:50]
        branch_name = f"feature/{safe_name}"

        result = self._run(["checkout", "-b", branch_name])
        return {
            "success": result.returncode == 0,
            "branch": branch_name if result.returncode == 0 else None,
            "error": result.stderr if result.returncode != 0 else ""
        }

    def get_diff(self, staged: bool = False) -> str:
        """
        获取变更摘要

        Args:
            staged: 是否只显示已暂存的变更

        Returns:
            diff 文本
        """
        args = ["diff"]
        if staged:
            args.append("--staged")
        args.append("--stat")

        result = self._run(args)
        return result.stdout

    def get_diff_detail(self, file_path: str = None) -> str:
        """
        获取详细变更

        Args:
            file_path: 指定文件路径（可选）

        Returns:
            详细 diff 文本
        """
        args = ["diff", "--unified=5"]
        if file_path:
            args.append("--")
            args.append(file_path)

        result = self._run(args)
        return result.stdout

    def rollback(self, to: str = "HEAD~1") -> Dict:
        """
        回滚到指定提交

        Args:
            to: 回滚目标（默认回滚1个提交）

        Returns:
            {"success": bool, "message": str}
        """
        # 先检查是否有未提交的变更
        status = self.status()
        if not status["is_clean"]:
            return {
                "success": False,
                "message": f"有 {status['total_changes']} 个未提交的变更，请先提交或暂存"
            }

        result = self._run(["reset", "--hard", to])
        return {
            "success": result.returncode == 0,
            "message": f"已回滚到 {to}" if result.returncode == 0 else result.stderr
        }

    def get_log(self, count: int = 10) -> List[Dict]:
        """
        获取最近的提交日志

        Args:
            count: 返回条数

        Returns:
            提交记录列表
        """
        result = self._run([
            "log", f"-{count}",
            "--format=%H|%h|%s|%an|%ad",
            "--date=short"
        ])

        commits = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({
                    "hash": parts[0],
                    "short_hash": parts[1],
                    "message": parts[2],
                    "author": parts[3],
                    "date": parts[4],
                })

        return commits

    def get_current_branch(self) -> str:
        """获取当前分支名"""
        result = self._run(["branch", "--show-current"])
        return result.stdout.strip()

    def stash_changes(self, message: str = None) -> Dict:
        """
        暂存当前变更

        Args:
            message: 暂存说明

        Returns:
            {"success": bool, "message": str}
        """
        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])

        result = self._run(args)
        return {
            "success": result.returncode == 0,
            "message": "变更已暂存" if result.returncode == 0 else result.stderr
        }

    def pop_stash(self) -> Dict:
        """恢复最近的暂存"""
        result = self._run(["stash", "pop"])
        return {
            "success": result.returncode == 0,
            "message": "暂存已恢复" if result.returncode == 0 else result.stderr
        }

    def get_summary(self) -> Dict:
        """获取仓库摘要"""
        branch = self.get_current_branch()
        status = self.status()
        log = self.get_log(5)

        return {
            "branch": branch,
            "is_clean": status["is_clean"],
            "pending_changes": status["total_changes"],
            "recent_commits": log,
            "repo_path": str(self.repo_path),
        }


# ============================================================
# 便捷函数
# ============================================================
def auto_commit(project_dir: str, message: str = None) -> Dict:
    """便捷函数：自动提交"""
    try:
        gh = GitHelper(project_dir)
        return gh.auto_commit(message)
    except RuntimeError as e:
        return {"success": False, "hash": None, "message": str(e)}


def get_diff(project_dir: str) -> str:
    """便捷函数：获取变更摘要"""
    try:
        gh = GitHelper(project_dir)
        return gh.get_diff()
    except RuntimeError:
        return ""


def rollback(project_dir: str, to: str = "HEAD~1") -> Dict:
    """便捷函数：回滚"""
    try:
        gh = GitHelper(project_dir)
        return gh.rollback(to)
    except RuntimeError as e:
        return {"success": False, "message": str(e)}


# ============================================================
# 测试
# ============================================================
if __name__ == "__main__":
    import sys

    repo = sys.argv[1] if len(sys.argv) > 1 else "."

    try:
        gh = GitHelper(repo)
        summary = gh.get_summary()
        print(f"分支: {summary['branch']}")
        print(f"状态: {'干净' if summary['is_clean'] else '有变更'}")
        print(f"待处理变更: {summary['pending_changes']}")
        print(f"\n最近提交:")
        for c in summary['recent_commits']:
            print(f"  {c['short_hash']} ({c['date']}) {c['message']} - {c['author']}")
    except RuntimeError as e:
        print(f"错误: {e}")