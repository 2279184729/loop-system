"""
产品迭代循环引擎
=================
plan → build → test → review → next 持续迭代循环
支持自动 git commit、进度追踪、状态持久化
"""

import json
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

import time
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from config import Colors
from utils import (
    print_banner, print_phase, print_step, print_success,
    print_error, print_warning, print_info, Timer
)
from project_scanner import scan_project, get_project_summary, ProjectContext

# 尝试导入 Orchestrator
try:
    from orchestrator import Orchestrator
except ImportError:
    Orchestrator = None


# ============================================================
# 产品状态
# ============================================================
@dataclass
class Feature:
    """产品特性"""
    id: str
    name: str
    description: str
    status: str = "planned"  # planned → building → testing → done
    priority: int = 0  # 0=最高
    iteration: int = 0  # 在哪个迭代中完成
    files_changed: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ProductState:
    """产品状态"""
    name: str
    project_dir: str
    features: List[Feature] = field(default_factory=list)
    current_iteration: int = 0
    total_iterations: int = 0
    history: List[Dict] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# 迭代循环引擎
# ============================================================
class IterationLoop:
    """
    产品迭代循环引擎
    持续循环: plan → build → test → review → next
    """

    def __init__(
        self,
        project_dir: str = None,
        product_name: str = None,
        max_iterations: int = 10,
        auto_commit: bool = True
    ):
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.max_iterations = max_iterations
        self.auto_commit = auto_commit

        # 产品状态
        self.state = ProductState(
            name=product_name or self.project_dir.name,
            project_dir=str(self.project_dir),
            total_iterations=max_iterations,
        )

        # 项目上下文
        self.ctx: Optional[ProjectContext] = None

        # Orchestrator
        self.orchestrator = None
        if Orchestrator:
            self.orchestrator = Orchestrator(project_dir=str(self.project_dir))

        self.timer = Timer()

    def run(self, product_goal: str) -> Dict:
        """
        主入口：运行产品迭代循环

        Args:
            product_goal: 产品目标描述

        Returns:
            迭代结果摘要
        """
        print_banner(f"🚀 产品迭代循环启动: {self.state.name}", Colors.CYAN)
        print_info(f"目标: {product_goal}")
        print_info(f"项目目录: {self.project_dir}")
        print_info(f"最大迭代: {self.max_iterations} | 自动提交: {'是' if self.auto_commit else '否'}")

        # ---- 阶段0: 初始扫描 ----
        self._phase0_scan()

        # ---- 阶段1: 特性规划 ----
        self._phase1_plan_features(product_goal)

        # ---- 迭代循环 ----
        for iteration in range(1, self.max_iterations + 1):
            self.state.current_iteration = iteration
            print_banner(f"🔄 迭代 {iteration}/{self.max_iterations}", Colors.BLUE)

            # 获取当前要做的特性
            features = self._get_pending_features()
            if not features:
                print_success("所有特性已完成，迭代结束")
                break

            feature = features[0]  # 取最高优先级

            # Step 1: Build
            if not self._step_build(feature):
                print_warning(f"特性 '{feature.name}' 构建失败，跳过")
                feature.status = "failed"
                continue

            # Step 2: Test
            if not self._step_test(feature):
                print_warning(f"特性 '{feature.name}' 测试失败，尝试修复")
                # 给一次修复机会
                if not self._step_fix(feature):
                    continue

            # Step 3: Review
            self._step_review(feature)

            # Step 4: Commit
            if self.auto_commit:
                self._step_commit(feature)

            # 记录迭代历史
            self.state.history.append({
                "iteration": iteration,
                "feature": feature.name,
                "status": feature.status,
                "files_changed": feature.files_changed,
                "timestamp": datetime.now().isoformat(),
            })

            print_success(f"迭代 {iteration} 完成: {feature.name} → {feature.status}")

        # ---- 最终总结 ----
        return self._finalize()

    # ================================================================
    # 阶段0: 项目扫描
    # ================================================================
    def _phase0_scan(self):
        print_phase("阶段0: 项目上下文扫描")
        self.ctx = scan_project(str(self.project_dir))
        summary = get_project_summary(self.ctx)
        print_info(f"项目文件: {self.ctx.total_files} | 代码行: {self.ctx.total_lines}")
        print_info(f"语言: {dict(self.ctx.languages)}")
        self.timer.checkpoint("phase0_scan")

    # ================================================================
    # 阶段1: 特性规划
    # ================================================================
    def _phase1_plan_features(self, product_goal: str):
        print_phase("阶段1: 特性规划")

        # 解析产品目标，生成特性列表
        features = self._parse_features(product_goal)

        for i, feat in enumerate(features):
            feat.id = f"FEAT-{i+1:03d}"
            feat.priority = i
            self.state.features.append(feat)
            print_step(f"[{feat.id}] {feat.name} (优先级: {feat.priority})")
            print_info(f"  {feat.description}")

        print_success(f"规划了 {len(features)} 个特性")
        self.timer.checkpoint("phase1_plan")

    def _parse_features(self, product_goal: str) -> List[Feature]:
        """从产品目标解析特性列表"""
        features = []

        # 启发式解析：按句号、分号、换行拆分
        goal_lower = product_goal.lower()

        # 常见特性模式
        feature_patterns = [
            ("用户认证", "实现用户注册、登录、登出功能"),
            ("日志系统", "添加结构化日志记录和日志级别管理"),
            ("错误处理", "统一错误处理和异常响应格式"),
            ("数据验证", "添加请求参数校验和数据模型验证"),
            ("API文档", "生成和维护API文档"),
            ("单元测试", "为核心模块添加单元测试覆盖"),
            ("配置管理", "实现多环境配置管理"),
            ("数据库迁移", "数据库Schema版本管理和迁移"),
            ("缓存层", "添加缓存层提升性能"),
            ("监控告警", "添加应用监控和告警机制"),
            ("权限控制", "实现RBAC权限控制系统"),
            ("文件上传", "实现文件上传和管理功能"),
            ("搜索功能", "添加全文搜索功能"),
            ("国际化", "实现多语言国际化支持"),
            ("性能优化", "代码性能分析和优化"),
        ]

        # 匹配产品目标中的特性
        for keyword, default_desc in feature_patterns:
            if keyword.lower() in goal_lower:
                features.append(Feature(
                    id="",  # 稍后分配
                    name=keyword,
                    description=default_desc,
                    status="planned",
                ))

        # 如果没有匹配到任何特性，创建通用特性
        if not features:
            # 将产品目标拆分为多个特性
            parts = product_goal.replace("；", ";").replace("。", ";").split(";")
            for i, part in enumerate(parts[:5]):  # 最多5个
                part = part.strip()
                if len(part) > 5:
                    features.append(Feature(
                        id="",
                        name=f"特性{i+1}: {part[:30]}",
                        description=part,
                        status="planned",
                    ))

        return features

    # ================================================================
    # 迭代步骤
    # ================================================================
    def _get_pending_features(self) -> List[Feature]:
        """获取待执行的特性（按优先级排序）"""
        return sorted(
            [f for f in self.state.features if f.status == "planned"],
            key=lambda x: x.priority
        )

    def _step_build(self, feature: Feature) -> bool:
        """构建特性"""
        print_phase(f"🏗️ 构建: {feature.name}")
        feature.status = "building"

        task = f"为项目添加{feature.name}功能: {feature.description}"

        if self.orchestrator:
            # 使用 Orchestrator 执行
            result = self.orchestrator.execute(task)
            if result.get("status") == "completed":
                feature.files_changed = result.get("files_modified", [])
                feature.status = "testing"
                print_success(f"构建完成: {feature.name}")
                return True
            else:
                print_error(f"构建失败: {feature.name}")
                return False
        else:
            # 模拟构建
            print_step(f"任务: {task}")
            print_step("分析现有代码...")
            print_step("生成代码...")
            print_step("应用修改...")
            print_success(f"模拟构建完成: {feature.name}")
            feature.status = "testing"
            return True

    def _step_test(self, feature: Feature) -> bool:
        """测试特性"""
        print_step(f"🧪 测试: {feature.name}")

        # 运行项目测试
        test_files = list(self.project_dir.rglob("test_*.py")) + \
                     list(self.project_dir.rglob("*_test.py"))

        if test_files:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", str(self.project_dir), "-q", "--tb=short"],
                    capture_output=True, text=True, timeout=60,
                    cwd=str(self.project_dir),
                    encoding='utf-8', errors='replace'
                )
                if result.returncode == 0:
                    print_success("测试全部通过")
                    feature.status = "done"
                    return True
                else:
                    print_warning(f"测试失败:\n{result.stderr[:500]}")
                    return False
            except FileNotFoundError:
                print_info("pytest 未安装，跳过测试")
                feature.status = "done"
                return True
            except subprocess.TimeoutExpired:
                print_warning("测试超时")
                return False
        else:
            print_info("无测试文件，跳过测试")
            feature.status = "done"
            return True

    def _step_fix(self, feature: Feature) -> bool:
        """修复特性"""
        print_step(f"🔧 修复: {feature.name}")

        # 尝试使用 Orchestrator 修复
        if self.orchestrator:
            fix_task = f"修复{feature.name}相关的测试失败问题"
            result = self.orchestrator.execute(fix_task)
            if result.get("status") == "completed":
                feature.status = "done"
                print_success("修复成功")
                return True

        print_warning("修复失败")
        return False

    def _step_review(self, feature: Feature):
        """审查特性"""
        print_step(f"📋 审查: {feature.name}")

        if feature.files_changed:
            print_info(f"变更文件: {', '.join(feature.files_changed)}")
        else:
            print_info("无文件变更")

        # 检查代码质量
        if self.ctx:
            py_files = [f for f in feature.files_changed if f.endswith('.py')]
            for f in py_files:
                full_path = self.project_dir / f
                if full_path.exists():
                    try:
                        compile(full_path.read_text(encoding='utf-8'), f, 'exec')
                        print_success(f"语法检查通过: {f}")
                    except SyntaxError as e:
                        print_error(f"语法错误: {f} - {e}")

        print_success(f"审查完成: {feature.name}")

    def _step_commit(self, feature: Feature):
        """Git 提交"""
        try:
            # 检查是否有变更
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True,
                cwd=str(self.project_dir)
            )
            if result.stdout.strip():
                subprocess.run(
                    ["git", "add", "-A"],
                    capture_output=True, text=True,
                    cwd=str(self.project_dir)
                )
                commit_msg = f"feat: {feature.name} (迭代 {self.state.current_iteration})"
                subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    capture_output=True, text=True,
                    cwd=str(self.project_dir)
                )
                print_success(f"已提交: {commit_msg}")
            else:
                print_info("无变更，跳过提交")
        except Exception as e:
            print_warning(f"Git 提交失败: {e}")

    # ================================================================
    # 最终汇总
    # ================================================================
    def _finalize(self) -> Dict:
        """生成最终结果"""
        elapsed = self.timer.elapsed()

        done = sum(1 for f in self.state.features if f.status == "done")
        failed = sum(1 for f in self.state.features if f.status == "failed")
        planned = sum(1 for f in self.state.features if f.status == "planned")

        result = {
            "product": self.state.name,
            "total_iterations": self.state.current_iteration,
            "features_total": len(self.state.features),
            "features_done": done,
            "features_failed": failed,
            "features_remaining": planned,
            "elapsed_seconds": round(elapsed, 2),
            "history": self.state.history,
        }

        print_banner(
            f"🏁 产品迭代完成 | {done}/{len(self.state.features)} 特性 | 耗时 {elapsed:.2f}秒",
            Colors.GREEN
        )

        print(f"\n{Colors.BOLD}📊 迭代摘要:{Colors.END}")
        for h in self.state.history:
            icon = "✅" if h["status"] == "done" else "❌"
            print(f"  {icon} 迭代{h['iteration']}: {h['feature']} ({h['status']})")

        return result


# ============================================================
# 命令行入口
# ============================================================
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Loop System 产品迭代循环引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python iterate.py "为项目添加用户认证和日志系统"
  python iterate.py --max-iterations 3 "重构项目代码结构"
  python iterate.py --no-commit "添加单元测试覆盖"
  python iterate.py --project-dir ./my-app "添加API文档和错误处理"
        """
    )
    parser.add_argument("goal", nargs="?", default="增强项目功能和代码质量",
                        help="产品迭代目标")
    parser.add_argument("--project-dir", "-d", default=None,
                        help="项目目录 (默认: 当前目录)")
    parser.add_argument("--max-iterations", "-n", type=int, default=5,
                        help="最大迭代次数 (默认: 5)")
    parser.add_argument("--no-commit", action="store_true",
                        help="禁用自动 git commit")
    parser.add_argument("--product-name", "-p", default=None,
                        help="产品名称")

    args = parser.parse_args()

    loop = IterationLoop(
        project_dir=args.project_dir,
        product_name=args.product_name,
        max_iterations=args.max_iterations,
        auto_commit=not args.no_commit,
    )

    result = loop.run(args.goal)

    print(f"\n{Colors.CYAN}JSON结果:{Colors.END}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()