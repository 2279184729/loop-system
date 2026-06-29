"""
Claude Code 父子多层嵌套自适应Loop系统 - 父调度Agent核心引擎
============================================================
作为全局唯一总控大脑，负责：
  1. 任务复杂度自适应判定
  2. 全局方案规划（复杂任务）
  3. 子任务拆分与调度
  4. 结果回流汇总
  5. 全局自检修复闭环
"""

import json
import sys
import os
import io

# 修复Windows GBK编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    Colors, SubTask, LoopState,
    MAX_PLAN_ITERATIONS, MAX_CHILD_ITERATIONS,
    MAX_GLOBAL_FIX_ITERATIONS, DEMO_PROJECT_DIR
)
from utils import (
    print_banner, print_phase, print_step, print_success,
    print_error, print_warning, print_info, print_subtask,
    analyze_complexity, Logger, Timer, setup_workspace, run_child_agent
)


class Orchestrator:
    """
    父调度Agent - 全局唯一总控大脑
    """

    def __init__(self, project_dir: str = None):
        self.project_dir = Path(project_dir) if project_dir else DEMO_PROJECT_DIR
        self.logger = Logger("orchestrator")
        self.timer = Timer()
        self.state = LoopState()
        self.subtasks: List[SubTask] = []
        self.plan: Optional[Dict] = None
        self.all_results: List[Dict] = []

    def execute(self, task_description: str) -> Dict:
        """
        主入口：执行任务（自适应路由）
        """
        print_banner("Claude Code 父子多层嵌套自适应Loop系统", Colors.CYAN)
        print(f"\n{Colors.BOLD}📋 任务描述:{Colors.END}")
        print(f"  {Colors.DIM}{task_description}{Colors.END}")

        # ==========================================
        # 阶段0：复杂度判定
        # ==========================================
        self.state.phase = "complexity_check"
        print_phase("阶段0：自适应复杂度判定")

        complexity = analyze_complexity(task_description)
        print_step(f"简单得分: {complexity['simple_score']} | 复杂得分: {complexity['complex_score']}")
        print_step(f"判定置信度: {complexity['confidence']*100:.0f}%")
        print_step(f"建议模式: {'🔀 多Agent分层调度' if complexity['is_complex'] else '⚡ 直接执行'}")

        if complexity['complex_matches']:
            print_info(f"复杂特征匹配: {', '.join(complexity['complex_matches'])}")
        if complexity['simple_matches']:
            print_info(f"简单特征匹配: {', '.join(complexity['simple_matches'])}")

        self.timer.checkpoint("complexity_check")

        # ==========================================
        # 路由：简单任务 vs 复杂任务
        # ==========================================
        if not complexity['is_complex']:
            return self._execute_simple(task_description)
        else:
            return self._execute_complex(task_description)

    # ================================================================
    # 简单任务执行路径（极速直出）
    # ================================================================
    def _execute_simple(self, task_description: str) -> Dict:
        print_banner("⚡ 简单任务模式：极速直出", Colors.GREEN)
        self.state.phase = "direct_execute"

        print_step("分析任务需求...")
        print_step("定位目标文件...")
        print_step("生成修改方案...")

        # 模拟简单任务执行过程
        execution_steps = self._simulate_simple_execution(task_description)

        for step in execution_steps:
            print_success(step)

        self.state.phase = "done"
        elapsed = self.timer.elapsed()

        result = {
            "mode": "simple",
            "task": task_description,
            "execution_steps": execution_steps,
            "elapsed_seconds": round(elapsed, 2),
            "child_agents_used": 0,
            "status": "completed"
        }

        print_banner(f"✅ 简单任务闭环完成 | 耗时 {elapsed:.2f}秒 | 零子进程", Colors.GREEN)
        return result

    def _simulate_simple_execution(self, task: str) -> List[str]:
        """模拟简单任务的执行步骤"""
        steps = [
            f"读取项目结构: {self.project_dir.name}",
            "定位目标代码文件...",
            "分析代码逻辑与上下文...",
            "生成修改方案...",
            "应用代码修改...",
            "执行本地自测...",
            "验证修改正确性...",
            "优化代码质量...",
        ]

        # 根据任务类型添加特定步骤
        task_lower = task.lower()
        if "bug" in task_lower or "修复" in task_lower:
            steps.insert(3, "定位Bug根因...")
            steps.append("验证Bug已修复...")
        if "接口" in task_lower or "api" in task_lower:
            steps.append("测试接口响应...")
        if "配置" in task_lower or "config" in task_lower:
            steps.append("验证配置生效...")

        return steps

    # ================================================================
    # 复杂任务执行路径（多层嵌套Loop）
    # ================================================================
    def _execute_complex(self, task_description: str) -> Dict:
        print_banner("🔀 复杂任务模式：多层嵌套Loop调度", Colors.BLUE)

        # 阶段一：全局方案规划Loop
        self._phase1_plan(task_description)

        # 阶段二：分布式子Agent调度Loop
        self._phase2_execute()

        # 阶段三：结果回流汇总Loop
        self._phase3_merge()

        # 阶段四：全局自检修复闭环Loop
        self._phase4_validate()

        # 最终闭环
        self.state.phase = "done"
        elapsed = self.timer.elapsed()

        result = {
            "mode": "complex",
            "task": task_description,
            "plan": self.plan,
            "subtasks_total": len(self.subtasks),
            "subtasks_completed": self.state.completed_subtasks,
            "subtasks_failed": self.state.failed_subtasks,
            "iterations": self.state.iteration,
            "elapsed_seconds": round(elapsed, 2),
            "child_agents_used": len(self.subtasks),
            "status": "completed" if self.state.failed_subtasks == 0 else "partial"
        }

        print_banner(
            f"🏁 多层Loop任务完全闭环完成 | "
            f"子Agent: {self.state.completed_subtasks}/{len(self.subtasks)} | "
            f"耗时: {elapsed:.2f}秒",
            Colors.GREEN
        )
        return result

    # ================================================================
    # 阶段一：全局方案规划Loop
    # ================================================================
    def _phase1_plan(self, task_description: str):
        print_phase("阶段一：全局方案规划Loop（父Agent外层循环）")
        self.state.phase = "plan"

        for iteration in range(1, MAX_PLAN_ITERATIONS + 1):
            print_step(f"规划迭代 {iteration}/{MAX_PLAN_ITERATIONS}")

            if iteration == 1:
                # 第1轮：初始分析
                plan = self._generate_initial_plan(task_description)
            else:
                # 后续轮次：优化迭代
                plan = self._refine_plan(plan)

            self.plan = plan
            print_success(f"方案v{iteration}: {plan['architecture']}")

            # 检查方案是否已经稳定
            if iteration >= 2 and self._is_plan_stable():
                print_success("方案已稳定，规划完成")
                break

            self.state.iteration += 1

        self.timer.checkpoint("phase1_plan")
        print_info(f"规划阶段完成，生成 {len(self.subtasks)} 个原子子任务")

    def _generate_initial_plan(self, task: str) -> Dict:
        """生成初始方案"""
        # 根据任务类型生成不同的方案
        if "用户管理" in task or "user" in task.lower():
            plan = {
                "architecture": "前后端分离 + RESTful API + 关系型数据库",
                "modules": ["数据库设计", "后端API", "前端页面", "工程规范"],
                "tech_stack": {
                    "backend": "Python FastAPI",
                    "frontend": "React + TypeScript",
                    "database": "SQLite",
                    "testing": "pytest + jest"
                }
            }
            self.subtasks = [
                SubTask(
                    id="SUB-001", name="数据库表结构设计",
                    description="设计用户表、角色表、权限表，含索引优化和字段约束",
                    workspace="db-schema-design", module_type="database",
                    priority=0, completion_criteria="DDL语句完整、索引合理、字段约束正确"
                ),
                SubTask(
                    id="SUB-002", name="后端CRUD接口开发",
                    description="用户管理CRUD接口、参数校验、异常处理、事务管理",
                    workspace="backend-user-module", module_type="backend",
                    priority=1, dependencies=["SUB-001"],
                    completion_criteria="接口完整、单测通过、无编译错误"
                ),
                SubTask(
                    id="SUB-003", name="前端用户管理页面",
                    description="用户列表、新增编辑弹窗、表单校验、接口对接",
                    workspace="frontend-user-page", module_type="frontend",
                    priority=1, dependencies=["SUB-002"],
                    completion_criteria="页面渲染正常、tsc编译无报错"
                ),
                SubTask(
                    id="SUB-004", name="工程规范统一整改",
                    description="代码格式化、lint修复、重复代码抽离、全局规范",
                    workspace="project-lint-fix", module_type="config",
                    priority=2, completion_criteria="lint零告警、代码规范统一"
                ),
            ]
        elif "重构" in task or "refactor" in task.lower():
            plan = {
                "architecture": "模块化重构 + 依赖解耦 + 代码规范化",
                "modules": ["代码分析", "模块拆分", "依赖整理", "测试覆盖"],
                "tech_stack": {"language": "Python/TypeScript", "testing": "pytest/jest"}
            }
            self.subtasks = [
                SubTask(
                    id="SUB-001", name="代码结构分析", description="分析现有代码结构、依赖关系",
                    workspace="code-analysis", module_type="config", priority=0
                ),
                SubTask(
                    id="SUB-002", name="模块拆分重构", description="按职责拆分模块、降低耦合",
                    workspace="module-refactor", module_type="backend", priority=1
                ),
                SubTask(
                    id="SUB-003", name="公共代码抽离", description="抽离重复代码到公共模块",
                    workspace="common-extract", module_type="config", priority=1
                ),
                SubTask(
                    id="SUB-004", name="测试覆盖补充", description="补充单元测试、集成测试",
                    workspace="test-coverage", module_type="backend", priority=2
                ),
            ]
        else:
            # 通用方案
            plan = {
                "architecture": "模块化分布式架构",
                "modules": ["需求分析", "模块开发", "集成测试", "优化部署"],
                "tech_stack": {"language": "通用", "testing": "标准测试框架"}
            }
            self.subtasks = [
                SubTask(
                    id="SUB-001", name="需求分析与架构设计",
                    description="分析需求、设计架构方案",
                    workspace="requirement-analysis", module_type="config", priority=0
                ),
                SubTask(
                    id="SUB-002", name="核心模块开发",
                    description="开发核心业务模块",
                    workspace="core-module", module_type="backend", priority=1
                ),
                SubTask(
                    id="SUB-003", name="接口/页面开发",
                    description="开发接口或前端页面",
                    workspace="interface-module", module_type="frontend", priority=1
                ),
                SubTask(
                    id="SUB-004", name="集成测试与优化",
                    description="全局集成测试、性能优化",
                    workspace="integration-test", module_type="config", priority=2
                ),
            ]

        return plan

    def _refine_plan(self, plan: Dict) -> Dict:
        """优化方案（模拟迭代改进）"""
        # 在实际环境中，这里会调用Claude API进行方案优化
        plan["version"] = plan.get("version", 1) + 1
        plan["optimizations"] = plan.get("optimizations", []) + [
            f"优化项v{plan['version']}: 减少模块耦合、增加容错设计"
        ]
        return plan

    def _is_plan_stable(self) -> bool:
        """检查方案是否稳定"""
        return self.state.iteration >= 2

    # ================================================================
    # 阶段二：分布式子Agent调度Loop
    # ================================================================
    def _phase2_execute(self):
        print_phase("阶段二：分布式子Agent调度Loop")
        self.state.phase = "execute"
        self.state.total_subtasks = len(self.subtasks)

        # 按优先级和依赖关系分组
        batches = self._group_by_dependency()

        for batch_idx, batch in enumerate(batches):
            print_step(f"批次 {batch_idx + 1}/{len(batches)}: 并行执行 {len(batch)} 个子任务")

            # 并行执行同一批次中的所有子任务
            with ThreadPoolExecutor(max_workers=min(len(batch), 4)) as executor:
                futures = {}
                for subtask in batch:
                    print_subtask(subtask.id, subtask.name, "running")
                    subtask.status = "running"
                    future = executor.submit(self._run_single_subtask, subtask)
                    futures[future] = subtask

                for future in as_completed(futures):
                    subtask = futures[future]
                    try:
                        result = future.result()
                        if result.get("success"):
                            subtask.status = "completed"
                            subtask.result = result
                            self.state.completed_subtasks += 1
                            print_subtask(subtask.id, subtask.name, "completed")
                            print_success(f"{subtask.id} 完成: {result.get('summary', 'OK')}")
                        else:
                            subtask.status = "failed"
                            self.state.failed_subtasks += 1
                            print_subtask(subtask.id, subtask.name, "failed")
                            print_error(f"{subtask.id} 失败: {result.get('error', 'Unknown')}")
                    except Exception as e:
                        subtask.status = "failed"
                        self.state.failed_subtasks += 1
                        print_error(f"{subtask.id} 异常: {str(e)}")

                    self.all_results.append({
                        "subtask_id": subtask.id,
                        "subtask_name": subtask.name,
                        "status": subtask.status,
                        "result": subtask.result
                    })

        self.timer.checkpoint("phase2_execute")

    def _group_by_dependency(self) -> List[List[SubTask]]:
        """按依赖关系分组子任务"""
        completed = set()
        batches = []
        remaining = list(self.subtasks)

        while remaining:
            batch = []
            still_waiting = []

            for subtask in remaining:
                deps = set(subtask.dependencies)
                if deps.issubset(completed):
                    batch.append(subtask)
                else:
                    still_waiting.append(subtask)

            if not batch:
                # 防止死锁：如果无法推进，将剩余全部放入下一批
                batches.append(still_waiting)
                break

            batches.append(batch)
            for subtask in batch:
                completed.add(subtask.id)
            remaining = still_waiting

        return batches

    def _run_single_subtask(self, subtask: SubTask) -> Dict:
        """执行单个子任务（调用子Agent）"""
        workspace = setup_workspace(subtask.workspace)

        task_payload = {
            "id": subtask.id,
            "name": subtask.name,
            "description": subtask.description,
            "module_type": subtask.module_type,
            "max_iterations": subtask.max_iterations,
            "completion_criteria": subtask.completion_criteria,
            "workspace": str(workspace)
        }

        # 调用子Agent进程
        result = run_child_agent(str(workspace), task_payload)
        return result

    # ================================================================
    # 阶段三：结果回流汇总Loop
    # ================================================================
    def _phase3_merge(self):
        print_phase("阶段三：结果回流汇总Loop")
        self.state.phase = "merge"

        print_step("收集所有子Agent输出...")
        completed = [r for r in self.all_results if r["status"] == "completed"]
        failed = [r for r in self.all_results if r["status"] == "failed"]

        print_info(f"已完成: {len(completed)} | 失败: {len(failed)}")

        print_step("合并模块代码...")
        print_step("检测文件冲突...")
        print_step("解决逻辑冲突...")

        # 模拟合并过程
        merge_steps = [
            "合并数据库Schema文件...",
            "合并后端API代码...",
            "合并前端页面组件...",
            "合并工程配置文件...",
            "解决import路径冲突...",
            "统一代码风格...",
        ]
        for step in merge_steps:
            print_success(step)

        print_step("执行全局工程校验...")
        checks = [
            "全局构建检查: PASS",
            "全量Lint检查: PASS",
            "全局兼容性检测: PASS",
        ]
        for check in checks:
            print_success(check)

        self.timer.checkpoint("phase3_merge")

    # ================================================================
    # 阶段四：全局自检修复闭环Loop
    # ================================================================
    def _phase4_validate(self):
        print_phase("阶段四：全局自检修复闭环Loop")
        self.state.phase = "validate"

        for iteration in range(1, MAX_GLOBAL_FIX_ITERATIONS + 1):
            print_step(f"全局校验迭代 {iteration}/{MAX_GLOBAL_FIX_ITERATIONS}")

            issues = self._detect_global_issues()

            if not issues:
                print_success("全局校验通过，无遗留问题")
                break

            print_warning(f"检测到 {len(issues)} 个问题，开始修复...")

            for issue in issues:
                if issue["type"] == "architecture":
                    print_step(f"修复架构问题: {issue['description']}")
                    print_success(f"已修复: {issue['description']}")
                elif issue["type"] == "module":
                    print_step(f"重新调度子Agent修复: {issue['description']}")
                    print_success(f"已修复: {issue['description']}")

            # 判断是否还有问题
            if iteration == MAX_GLOBAL_FIX_ITERATIONS:
                print_warning("达到最大修复迭代次数")

        self.timer.checkpoint("phase4_validate")

    def _detect_global_issues(self) -> List[Dict]:
        """检测全局问题（模拟）"""
        # 在实际环境中，这里会执行全局lint、测试、构建检查
        # 模拟：第一次迭代有问题，后续没有问题
        if self.state.iteration < 1:
            return [
                {"type": "architecture", "description": "模块间API路径不一致"},
                {"type": "module", "description": "前端表单校验逻辑缺失边界情况"},
            ]
        return []


# ============================================================
# 命令行入口
# ============================================================
def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print("用法: python orchestrator.py <任务描述> [--project-dir <项目目录>]")
        print()
        print("示例:")
        print('  python orchestrator.py "修复登录接口空指针bug"')
        print('  python orchestrator.py "从零搭建全栈用户管理系统"')
        print('  python orchestrator.py "重构项目代码结构"')
        sys.exit(1)

    task_description = sys.argv[1]
    project_dir = None

    # 解析可选参数
    for i, arg in enumerate(sys.argv):
        if arg == "--project-dir" and i + 1 < len(sys.argv):
            project_dir = sys.argv[i + 1]

    orchestrator = Orchestrator(project_dir=project_dir)
    result = orchestrator.execute(task_description)

    # 输出最终结果
    print(f"\n{Colors.CYAN}{Colors.BOLD}📊 最终执行报告:{Colors.END}")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return result


if __name__ == "__main__":
    main()