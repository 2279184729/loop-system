"""
Claude Code 父子多层嵌套自适应Loop系统 - 子执行Agent模块
==========================================================
独立子Agent，负责单一模块落地、代码生成、自测自修复
通过 Claude API + Tool Use 实现真实代码生成和验证
"""

import json
import sys
import io

# 修复Windows GBK编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import subprocess
from pathlib import Path
from typing import Dict, List

from config import Colors, MAX_CHILD_ITERATIONS, CHILD_AGENT_SYSTEM_PROMPT
from utils import run_agent_loop


class ChildAgent:
    """
    子执行Agent - 分布式工人
    通过 Claude API 实现真实代码生成、测试和自修复
    """

    def __init__(self, task: Dict, workspace: str, project_dir: str = None):
        self.task = task
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.project_dir = project_dir
        self.max_iterations = task.get("max_iterations", MAX_CHILD_ITERATIONS)
        self.task_name = task.get("name", "Unknown")
        self.task_id = task.get("id", "???")
        self.module_type = task.get("module_type", "backend")
        self.completion_criteria = task.get("completion_criteria", "")
        self.files_created: List[str] = []

    def execute(self) -> Dict:
        """
        子Agent自驱Loop主入口
        编码 → 自测 → 报错自修复 → 迭代达标终止
        """
        print(f"\n{Colors.BLUE}┌── 子Agent启动 [{self.task_id}] {self.task_name} ──┐{Colors.END}")
        print(f"  {Colors.DIM}工作区: {self.workspace}{Colors.END}")
        print(f"  {Colors.DIM}模块类型: {self.module_type}{Colors.END}")
        if self.project_dir:
            print(f"  {Colors.DIM}项目目录: {self.project_dir}{Colors.END}")

        # 构建任务描述
        task_desc = self._build_task_description()

        # 阶段1: 代码生成（Agent Loop）
        print(f"\n  {Colors.CYAN}── 阶段1: 代码生成 ──{Colors.END}")
        result = run_agent_loop(
            task_description=task_desc,
            workspace=str(self.workspace),
            system_prompt=CHILD_AGENT_SYSTEM_PROMPT,
            project_dir=self.project_dir,
            max_iterations=self.max_iterations
        )
        self.files_created = result.get("files_created", [])

        if not result["success"]:
            print(f"\n  {Colors.YELLOW}⚠️ 代码生成未完全成功{Colors.END}")
            return self._build_result(False, result.get("result", "代码生成失败"), [])

        # 阶段2: 运行测试
        print(f"\n  {Colors.CYAN}── 阶段2: 运行测试 ──{Colors.END}")
        test_result = self._run_tests()

        if test_result["passed"]:
            print(f"\n  {Colors.GREEN}✅ 子Agent [{self.task_id}] 所有测试通过！{Colors.END}")
            return self._build_result(True, result["result"], test_result.get("details", []))

        # 阶段3: 自修复（将测试错误反馈给 Claude）
        print(f"\n  {Colors.CYAN}── 阶段3: 自修复 ──{Colors.END}")
        fix_result = self._auto_fix(result["result"], test_result)

        if fix_result["success"]:
            print(f"\n  {Colors.GREEN}✅ 子Agent [{self.task_id}] 修复后测试通过！{Colors.END}")
            return self._build_result(True, fix_result["result"], fix_result.get("details", []))
        else:
            print(f"\n  {Colors.YELLOW}⚠️ 子Agent [{self.task_id}] 修复后仍有问题{Colors.END}")
            return self._build_result(False, fix_result["result"], test_result.get("details", []))

    def _build_task_description(self) -> str:
        """构建发给 Claude 的任务描述"""
        desc = self.task.get("description", self.task_name)
        criteria = self.completion_criteria

        parts = [f"## 任务: {self.task_name}\n"]
        parts.append(f"**模块类型**: {self.module_type}")
        parts.append(f"**任务描述**: {desc}")
        if criteria:
            parts.append(f"**完成标准**: {criteria}")
        parts.append(f"\n所有输出文件必须写入工作区: {self.workspace}")

        if self.project_dir:
            parts.append(f"\n如需了解项目上下文，可读取项目目录: {self.project_dir}")

        return "\n".join(parts)

    def _run_tests(self) -> Dict:
        """在工作区中运行测试"""
        details = []

        # 查找测试文件
        test_patterns = ("test_*.py", "Test_*.py", "*_test.py", "*_Test.py", "*.test.*", "*.Test.*")
        test_files = []
        for pattern in test_patterns:
            test_files.extend(self.workspace.glob(pattern))

        if not test_files:
            print(f"  {Colors.DIM}未找到测试文件，跳过测试{Colors.END}")
            return {"passed": True, "details": ["未找到测试文件"]}

        for test_file in test_files:
            print(f"  {Colors.DIM}🧪 运行: {test_file.name}{Colors.END}")
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short"],
                    capture_output=True, text=True, timeout=120,
                    cwd=str(self.workspace), encoding='utf-8', errors='replace'
                )
                output = result.stdout + result.stderr
                details.append(output)

                if result.returncode == 0:
                    print(f"  {Colors.GREEN}  ✓ 测试通过{Colors.END}")
                else:
                    print(f"  {Colors.RED}  ✗ 测试失败{Colors.END}")
            except subprocess.TimeoutExpired:
                details.append(f"{test_file.name}: 测试超时")
                print(f"  {Colors.RED}  ✗ 测试超时{Colors.END}")
            except Exception as e:
                details.append(f"{test_file.name}: 运行错误 - {e}")
                print(f"  {Colors.RED}  ✗ 运行错误: {e}{Colors.END}")

        # 也检查是否有 package.json 中的测试脚本
        package_json = self.workspace / "package.json"
        if package_json.exists():
            print(f"  {Colors.DIM}🧪 运行: npm test{Colors.END}")
            try:
                result = subprocess.run(
                    ["npm", "test"], capture_output=True, text=True, timeout=120,
                    cwd=str(self.workspace), encoding='utf-8', errors='replace'
                )
                output = result.stdout + result.stderr
                details.append(f"npm test:\n{output}")
                if result.returncode == 0:
                    print(f"  {Colors.GREEN}  ✓ npm test 通过{Colors.END}")
                else:
                    print(f"  {Colors.RED}  ✗ npm test 失败{Colors.END}")
            except Exception as e:
                details.append(f"npm test: 运行错误 - {e}")

        all_passed = all("FAILED" not in d and "failed" not in d.lower() and "error" not in d.lower()
                         for d in details if d)

        return {"passed": all_passed, "details": details}

    def _auto_fix(self, previous_result: str, test_result: Dict) -> Dict:
        """将测试失败信息反馈给 Claude 进行修复"""
        test_output = "\n".join(test_result.get("details", []))

        fix_prompt = f"""测试失败，请修复代码。

## 之前的代码生成结果
{previous_result[:2000]}

## 测试输出
{test_output[:4000]}

请分析测试失败原因，使用 edit_file 工具修复代码，然后运行测试验证。
所有修改必须在工作区 {self.workspace} 内进行。"""

        return run_agent_loop(
            task_description=fix_prompt,
            workspace=str(self.workspace),
            system_prompt=CHILD_AGENT_SYSTEM_PROMPT,
            project_dir=self.project_dir,
            max_iterations=5
        )

    def _build_result(self, success: bool, summary: str, details: List[str]) -> Dict:
        return {
            "success": success,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "files_created": self.files_created,
            "workspace": str(self.workspace),
            "summary": summary[:500] if summary else "",
            "details": details,
            "completion_criteria_met": self.completion_criteria if success else "",
        }


# ============================================================
# 命令行入口
# ============================================================
def main():
    """子Agent命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Claude Code子执行Agent")
    parser.add_argument("--task", type=str, required=True, help="任务JSON")
    parser.add_argument("--workspace", type=str, required=True, help="工作区路径")
    parser.add_argument("--project-dir", type=str, default=None, help="项目目录路径")

    args = parser.parse_args()

    task = json.loads(args.task)
    agent = ChildAgent(task, args.workspace, args.project_dir)
    result = agent.execute()

    # 输出JSON结果（父Agent通过stdout读取）
    print("\n__RESULT__")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())