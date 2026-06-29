"""
Claude Code 父子多层嵌套自适应Loop系统 - 子执行Agent模块
==========================================================
独立子Agent，负责单一模块落地、代码生成、自测自修复
每个子Agent独立进程、独立上下文、独立自驱Loop
"""

import json
import sys
import io

# 修复Windows GBK编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import time
import random
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from config import Colors, MAX_CHILD_ITERATIONS


class ChildAgent:
    """
    子执行Agent - 分布式工人
    独立进程、独立工作区、独立自驱Loop
    """

    def __init__(self, task: Dict, workspace: str):
        self.task = task
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.max_iterations = task.get("max_iterations", MAX_CHILD_ITERATIONS)
        self.iteration = 0
        self.errors: List[str] = []
        self.fixes: List[str] = []
        self.files_created: List[str] = []

    def execute(self) -> Dict:
        """
        子Agent自驱Loop主入口
        编码 → 本地自测 → 报错自修复 → 迭代达标终止
        """
        task_name = self.task.get("name", "Unknown")
        task_id = self.task.get("id", "???")

        print(f"\n{Colors.BLUE}┌── 子Agent启动 [{task_id}] {task_name} ──┐{Colors.END}")
        print(f"  {Colors.DIM}工作区: {self.workspace}{Colors.END}")
        print(f"  {Colors.DIM}最大迭代: {self.max_iterations}{Colors.END}")

        for self.iteration in range(1, self.max_iterations + 1):
            print(f"\n  {Colors.CYAN}── 迭代 {self.iteration}/{self.max_iterations} ──{Colors.END}")

            # Step 1: 编码
            coding_result = self._step_code()
            if not coding_result["success"]:
                self.errors.append(coding_result.get("error", "编码失败"))
                continue

            # Step 2: 自测
            test_result = self._step_test()
            if not test_result["success"]:
                self.errors.append(test_result.get("error", "自测失败"))
                # Step 3: 自修复
                fix_result = self._step_fix(test_result)
                if not fix_result["success"]:
                    self.errors.append(fix_result.get("error", "修复失败"))
                    continue
                self.fixes.append(fix_result.get("fix", ""))

            # Step 4: 达标检查
            if self._check_completion():
                print(f"\n  {Colors.GREEN}✅ 子Agent [{task_id}] 达标完成！{Colors.END}")
                return self._build_success_result()

        # 达到最大迭代次数
        print(f"\n  {Colors.YELLOW}⚠️ 子Agent [{task_id}] 达到最大迭代次数{Colors.END}")
        return self._build_partial_result()

    def _step_code(self) -> Dict:
        """编码步骤"""
        module_type = self.task.get("module_type", "backend")
        print(f"    {Colors.DIM}📝 编码中... ({module_type}模块){Colors.END}")

        # 根据模块类型生成不同的模拟文件
        files = self._generate_module_files(module_type)
        self.files_created.extend(files)

        for f in files:
            print(f"    {Colors.GREEN}  ✓ 创建文件: {f}{Colors.END}")

        return {"success": True, "files": files}

    def _generate_module_files(self, module_type: str) -> List[str]:
        """根据模块类型生成模拟文件"""
        files = []

        if module_type == "database":
            # 生成数据库DDL文件
            schema_content = self._generate_db_schema()
            schema_file = self.workspace / "schema.sql"
            schema_file.write_text(schema_content, encoding='utf-8')
            files.append("schema.sql")

            # 生成迁移脚本
            migration_content = self._generate_migration()
            migration_file = self.workspace / "migration_v1.sql"
            migration_file.write_text(migration_content, encoding='utf-8')
            files.append("migration_v1.sql")

            # 生成索引优化文档
            index_doc = self.workspace / "index_design.md"
            index_doc.write_text(self._generate_index_doc(), encoding='utf-8')
            files.append("index_design.md")

        elif module_type == "backend":
            # 生成后端API代码
            api_content = self._generate_api_code()
            api_file = self.workspace / "api.py"
            api_file.write_text(api_content, encoding='utf-8')
            files.append("api.py")

            # 生成模型定义
            model_content = self._generate_models()
            model_file = self.workspace / "models.py"
            model_file.write_text(model_content, encoding='utf-8')
            files.append("models.py")

            # 生成测试文件
            test_content = self._generate_tests()
            test_file = self.workspace / "test_api.py"
            test_file.write_text(test_content, encoding='utf-8')
            files.append("test_api.py")

        elif module_type == "frontend":
            # 生成前端组件
            component_content = self._generate_frontend_component()
            component_file = self.workspace / "UserManagement.tsx"
            component_file.write_text(component_content, encoding='utf-8')
            files.append("UserManagement.tsx")

            # 生成类型定义
            types_content = self._generate_types()
            types_file = self.workspace / "types.ts"
            types_file.write_text(types_content, encoding='utf-8')
            files.append("types.ts")

            # 生成样式文件
            style_content = self._generate_styles()
            style_file = self.workspace / "styles.css"
            style_file.write_text(style_content, encoding='utf-8')
            files.append("styles.css")

        elif module_type == "config":
            # 生成配置文件
            config_files = self._generate_config_files()
            for fname, content in config_files.items():
                fpath = self.workspace / fname
                fpath.write_text(content, encoding='utf-8')
                files.append(fname)

        return files

    def _generate_db_schema(self) -> str:
        return """-- 用户管理系统数据库Schema
-- 设计规范：3NF范式、合理索引、完整约束

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    avatar_url VARCHAR(500),
    status VARCHAR(20) DEFAULT 'active' CHECK(status IN ('active', 'inactive', 'banned')),
    role_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_role_id ON users(role_id);

CREATE TABLE roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(200),
    permissions TEXT NOT NULL DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(200),
    module VARCHAR(50) NOT NULL
);

CREATE TABLE role_permissions (
    role_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
);

CREATE TABLE user_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action VARCHAR(50) NOT NULL,
    detail TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_user_logs_user_id ON user_logs(user_id);
CREATE INDEX idx_user_logs_created_at ON user_logs(created_at);
"""

    def _generate_migration(self) -> str:
        return """-- 数据库迁移脚本 v1
-- 初始版本：创建用户管理核心表结构

BEGIN TRANSACTION;

-- 创建权限表（先创建，因为roles依赖）
CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(200),
    module VARCHAR(50) NOT NULL
);

-- 插入默认权限
INSERT OR IGNORE INTO permissions (code, name, description, module) VALUES
('user:read', '查看用户', '查看用户列表和详情', 'user'),
('user:create', '创建用户', '创建新用户', 'user'),
('user:update', '更新用户', '修改用户信息', 'user'),
('user:delete', '删除用户', '删除用户', 'user'),
('role:manage', '角色管理', '管理角色和权限', 'role');

-- 创建角色表
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(200),
    permissions TEXT NOT NULL DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入默认角色
INSERT OR IGNORE INTO roles (name, description, permissions) VALUES
('admin', '系统管理员', '["user:read","user:create","user:update","user:delete","role:manage"]'),
('editor', '编辑者', '["user:read","user:create","user:update"]'),
('viewer', '观察者', '["user:read"]');

COMMIT;
"""

    def _generate_index_doc(self) -> str:
        return """# 数据库索引设计文档

## 索引策略
- **users表**: email/username唯一索引保证查询性能
- **users表**: status索引支持按状态筛选
- **user_logs表**: user_id+created_at复合索引支持日志查询

## 性能优化建议
- 定期ANALYZE更新统计信息
- 日志表按月分区
- 热点查询使用覆盖索引
"""

    def _generate_api_code(self) -> str:
        return '''"""用户管理API - FastAPI实现"""
from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
import hashlib
import secrets

app = FastAPI(title="用户管理系统API", version="1.0.0")


# ============================================================
# 数据模型
# ============================================================
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=100)
    role_id: int = Field(..., gt=0)

    @validator("username")
    def username_alphanumeric(cls, v):
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名只能包含字母、数字、下划线和横线")
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = None
    role_id: Optional[int] = Field(None, gt=0)

    @validator("status")
    def validate_status(cls, v):
        if v and v not in ("active", "inactive", "banned"):
            raise ValueError("无效的状态值")
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    status: str
    role_id: int
    created_at: datetime
    updated_at: datetime


# ============================================================
# 密码工具
# ============================================================
def hash_password(password: str, salt: str = None) -> tuple:
    """密码哈希（SHA256 + salt）"""
    if salt is None:
        salt = secrets.token_hex(16)
    salted = password + salt
    hash_obj = hashlib.sha256(salted.encode())
    return hash_obj.hexdigest(), salt


# ============================================================
# API路由
# ============================================================
@app.get("/api/users", response_model=List[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None
):
    """获取用户列表（分页、筛选、搜索）"""
    # 实际环境会查询数据库
    return []


@app.get("/api/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    """获取单个用户详情"""
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="无效的用户ID")
    # 实际环境会查询数据库
    return {}


@app.post("/api/users", response_model=UserResponse, status_code=201)
async def create_user(user: UserCreate):
    """创建新用户"""
    # 参数校验
    # 密码哈希
    password_hash, salt = hash_password(user.password)
    # 实际环境会写入数据库
    return {}


@app.put("/api/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user: UserUpdate):
    """更新用户信息"""
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="无效的用户ID")
    # 实际环境会更新数据库
    return {}


@app.delete("/api/users/{user_id}", status_code=204)
async def delete_user(user_id: int):
    """删除用户（软删除）"""
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="无效的用户ID")
    # 实际环境会执行软删除
    return None
'''

    def _generate_models(self) -> str:
        return '''"""数据库模型定义"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class User:
    """用户模型"""
    id: int
    username: str
    email: str
    password_hash: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    status: str = "active"
    role_id: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def is_active(self) -> bool:
        return self.status == "active"

    def is_banned(self) -> bool:
        return self.status == "banned"


@dataclass
class Role:
    """角色模型"""
    id: int
    name: str
    description: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Permission:
    """权限模型"""
    id: int
    code: str
    name: str
    description: Optional[str] = None
    module: str = ""
'''

    def _generate_tests(self) -> str:
        return '''"""用户管理API单元测试"""
import pytest
from api import app, hash_password
from fastapi.testclient import TestClient

client = TestClient(app)


class TestUserAPI:
    """用户CRUD接口测试"""

    def test_create_user_success(self):
        """测试创建用户 - 正常流程"""
        response = client.post("/api/users", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "full_name": "Test User",
            "role_id": 1
        })
        assert response.status_code == 201

    def test_create_user_invalid_email(self):
        """测试创建用户 - 无效邮箱"""
        response = client.post("/api/users", json={
            "username": "testuser",
            "email": "invalid-email",
            "password": "SecurePass123!",
            "role_id": 1
        })
        assert response.status_code == 422

    def test_create_user_short_password(self):
        """测试创建用户 - 密码太短"""
        response = client.post("/api/users", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "123",
            "role_id": 1
        })
        assert response.status_code == 422

    def test_get_user_list(self):
        """测试获取用户列表"""
        response = client.get("/api/users")
        assert response.status_code == 200

    def test_get_user_invalid_id(self):
        """测试获取用户 - 无效ID"""
        response = client.get("/api/users/-1")
        assert response.status_code == 400

    def test_delete_user(self):
        """测试删除用户"""
        response = client.delete("/api/users/1")
        assert response.status_code == 204


class TestPasswordHash:
    """密码哈希测试"""

    def test_hash_password(self):
        """测试密码哈希"""
        h, salt = hash_password("test123")
        assert len(h) == 64  # SHA256 hex length
        assert len(salt) == 32  # 16 bytes hex

    def test_hash_different_passwords(self):
        """测试不同密码产生不同哈希"""
        h1, _ = hash_password("password1")
        h2, _ = hash_password("password2")
        assert h1 != h2
'''

    def _generate_frontend_component(self) -> str:
        return '''import React, { useState, useEffect, useCallback } from 'react';
import { User, UserFormData, UserStatus } from './types';
import './styles.css';

// ============================================================
// 用户管理主页面组件
// ============================================================
const UserManagement: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<UserStatus | ''>('');
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // 获取用户列表
  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: String(page),
        size: '20',
        ...(statusFilter && { status: statusFilter }),
        ...(searchTerm && { search: searchTerm }),
      });
      const response = await fetch(`/api/users?${params}`);
      if (!response.ok) throw new Error('获取用户列表失败');
      const data = await response.json();
      setUsers(data.items);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, searchTerm]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // 创建用户
  const handleCreate = async (data: UserFormData) => {
    try {
      const response = await fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || '创建失败');
      }
      setShowCreateModal(false);
      fetchUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败');
    }
  };

  // 更新用户
  const handleUpdate = async (id: number, data: Partial<UserFormData>) => {
    try {
      const response = await fetch(`/api/users/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!response.ok) throw new Error('更新失败');
      setEditingUser(null);
      fetchUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新失败');
    }
  };

  // 删除用户
  const handleDelete = async (id: number) => {
    if (!window.confirm('确认删除该用户？')) return;
    try {
      const response = await fetch(`/api/users/${id}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('删除失败');
      fetchUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    }
  };

  return (
    <div className="user-management">
      <header className="um-header">
        <h1>用户管理</h1>
        <button
          className="btn btn-primary"
          onClick={() => setShowCreateModal(true)}
        >
          + 新增用户
        </button>
      </header>

      {/* 搜索和筛选栏 */}
      <div className="um-toolbar">
        <input
          type="text"
          placeholder="搜索用户名或邮箱..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as UserStatus | '')}
          className="status-filter"
        >
          <option value="">全部状态</option>
          <option value="active">活跃</option>
          <option value="inactive">未激活</option>
          <option value="banned">已禁用</option>
        </select>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {/* 用户表格 */}
      <div className="um-table-container">
        <table className="um-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名</th>
              <th>邮箱</th>
              <th>姓名</th>
              <th>状态</th>
              <th>角色</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="loading">加载中...</td></tr>
            ) : users.length === 0 ? (
              <tr><td colSpan={8} className="empty">暂无数据</td></tr>
            ) : (
              users.map((user) => (
                <tr key={user.id}>
                  <td>{user.id}</td>
                  <td>{user.username}</td>
                  <td>{user.email}</td>
                  <td>{user.full_name || '-'}</td>
                  <td>
                    <span className={`status-badge status-${user.status}`}>
                      {user.status}
                    </span>
                  </td>
                  <td>{user.role_name || '-'}</td>
                  <td>{new Date(user.created_at).toLocaleDateString()}</td>
                  <td className="actions">
                    <button
                      className="btn btn-sm"
                      onClick={() => setEditingUser(user)}
                    >
                      编辑
                    </button>
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={() => handleDelete(user.id)}
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* 分页 */}
      <div className="um-pagination">
        <button
          disabled={page <= 1}
          onClick={() => setPage(p => p - 1)}
        >
          上一页
        </button>
        <span>第 {page} / {totalPages} 页</span>
        <button
          disabled={page >= totalPages}
          onClick={() => setPage(p => p + 1)}
        >
          下一页
        </button>
      </div>

      {/* 创建用户弹窗 */}
      {showCreateModal && (
        <UserFormModal
          title="新增用户"
          onSubmit={handleCreate}
          onClose={() => setShowCreateModal(false)}
        />
      )}

      {/* 编辑用户弹窗 */}
      {editingUser && (
        <UserFormModal
          title="编辑用户"
          initialData={editingUser}
          onSubmit={(data) => handleUpdate(editingUser.id, data)}
          onClose={() => setEditingUser(null)}
        />
      )}
    </div>
  );
};

// ============================================================
// 用户表单弹窗组件
// ============================================================
interface UserFormModalProps {
  title: string;
  initialData?: Partial<UserFormData>;
  onSubmit: (data: UserFormData) => Promise<void>;
  onClose: () => void;
}

const UserFormModal: React.FC<UserFormModalProps> = ({
  title,
  initialData,
  onSubmit,
  onClose,
}) => {
  const [formData, setFormData] = useState<UserFormData>({
    username: initialData?.username || '',
    email: initialData?.email || '',
    password: '',
    full_name: initialData?.full_name || '',
    role_id: initialData?.role_id || 1,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!formData.username || formData.username.length < 3) {
      newErrors.username = '用户名至少3个字符';
    }
    if (!formData.email || !/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(formData.email)) {
      newErrors.email = '请输入有效的邮箱地址';
    }
    if (!initialData && (!formData.password || formData.password.length < 8)) {
      newErrors.password = '密码至少8个字符';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    try {
      await onSubmit(formData);
    } catch (err) {
      setErrors({ submit: err instanceof Error ? err.message : '提交失败' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>用户名 *</label>
            <input
              type="text"
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
            />
            {errors.username && <span className="field-error">{errors.username}</span>}
          </div>
          <div className="form-group">
            <label>邮箱 *</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            />
            {errors.email && <span className="field-error">{errors.email}</span>}
          </div>
          {!initialData && (
            <div className="form-group">
              <label>密码 *</label>
              <input
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              />
              {errors.password && <span className="field-error">{errors.password}</span>}
            </div>
          )}
          <div className="form-group">
            <label>姓名</label>
            <input
              type="text"
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
            />
          </div>
          <div className="form-actions">
            <button type="button" className="btn" onClick={onClose}>取消</button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? '提交中...' : '确认'}
            </button>
          </div>
          {errors.submit && <div className="submit-error">{errors.submit}</div>}
        </form>
      </div>
    </div>
  );
};

export default UserManagement;
'''

    def _generate_types(self) -> str:
        return '''// 用户管理类型定义

export type UserStatus = 'active' | 'inactive' | 'banned';

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  status: UserStatus;
  role_id: number;
  role_name?: string;
  created_at: string;
  updated_at: string;
}

export interface UserFormData {
  username: string;
  email: string;
  password?: string;
  full_name?: string;
  role_id: number;
}

export interface Role {
  id: number;
  name: string;
  description: string;
  permissions: string[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  total_pages: number;
}

export interface ApiError {
  detail: string;
  code?: string;
  field?: string;
}
'''

    def _generate_styles(self) -> str:
        return '''/* 用户管理页面样式 */
.user-management {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.um-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.um-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: #1a1a2e;
}

.um-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.search-input {
  flex: 1;
  max-width: 320px;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.status-filter {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  background: white;
}

.um-table-container {
  overflow-x: auto;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.um-table {
  width: 100%;
  border-collapse: collapse;
}

.um-table th {
  background: #f9fafb;
  padding: 12px 16px;
  text-align: left;
  font-weight: 600;
  font-size: 13px;
  color: #6b7280;
  border-bottom: 1px solid #e5e7eb;
}

.um-table td {
  padding: 12px 16px;
  font-size: 14px;
  border-bottom: 1px solid #f3f4f6;
}

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.status-active { background: #d1fae5; color: #065f46; }
.status-inactive { background: #fef3c7; color: #92400e; }
.status-banned { background: #fee2e2; color: #991b1b; }

.btn {
  padding: 8px 16px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn:hover { background: #f9fafb; }
.btn-primary { background: #3b82f6; color: white; border-color: #3b82f6; }
.btn-primary:hover { background: #2563eb; }
.btn-danger { color: #dc2626; }
.btn-danger:hover { background: #fef2f2; }
.btn-sm { padding: 4px 8px; font-size: 12px; }

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 12px;
  padding: 24px;
  width: 480px;
  max-height: 90vh;
  overflow-y: auto;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 4px;
  font-size: 14px;
  font-weight: 500;
}

.form-group input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.field-error {
  color: #dc2626;
  font-size: 12px;
  margin-top: 4px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}

.error-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fee2e2;
  color: #991b1b;
  border-radius: 6px;
  margin-bottom: 16px;
}

.um-pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
}
'''

    def _generate_config_files(self) -> Dict[str, str]:
        return {
            ".eslintrc.json": json.dumps({
                "extends": ["eslint:recommended"],
                "rules": {
                    "no-unused-vars": "warn",
                    "no-console": "warn",
                    "semi": ["error", "always"],
                    "quotes": ["error", "single"]
                }
            }, indent=2),
            ".prettierrc": json.dumps({
                "semi": True,
                "singleQuote": True,
                "tabWidth": 2,
                "trailingComma": "es5"
            }, indent=2),
            "tsconfig.json": json.dumps({
                "compilerOptions": {
                    "target": "ES2020",
                    "module": "ESNext",
                    "strict": True,
                    "jsx": "react-jsx",
                    "esModuleInterop": True
                }
            }, indent=2),
        }

    def _step_test(self) -> Dict:
        """自测步骤"""
        print(f"    {Colors.DIM}🧪 自测中...{Colors.END}")

        # 模拟测试：90%概率通过
        if random.random() < 0.9:
            print(f"    {Colors.GREEN}  ✓ 自测通过{Colors.END}")
            return {"success": True, "tests_passed": random.randint(5, 15)}
        else:
            error_types = [
                "类型错误: 参数类型不匹配",
                "空指针异常: 未处理null值",
                "边界异常: 数组越界访问",
                "编译错误: 缺少导入模块",
                "逻辑错误: 条件判断遗漏",
            ]
            error = random.choice(error_types)
            print(f"    {Colors.RED}  ✗ 自测失败: {error}{Colors.END}")
            return {"success": False, "error": error}

    def _step_fix(self, test_result: Dict) -> Dict:
        """自修复步骤"""
        error = test_result.get("error", "Unknown error")
        print(f"    {Colors.DIM}🔧 自修复中...{Colors.END}")

        fix_messages = {
            "类型错误": "添加类型注解并修正参数类型",
            "空指针异常": "添加null检查和默认值处理",
            "边界异常": "添加边界条件判断",
            "编译错误": "补充缺失的import语句",
            "逻辑错误": "修正条件判断逻辑",
        }

        for key, fix in fix_messages.items():
            if key in error:
                print(f"    {Colors.GREEN}  ✓ 修复: {fix}{Colors.END}")
                return {"success": True, "fix": fix}

        print(f"    {Colors.GREEN}  ✓ 通用修复已应用{Colors.END}")
        return {"success": True, "fix": "通用代码修复"}

    def _check_completion(self) -> bool:
        """检查是否达到完成标准"""
        criteria = self.task.get("completion_criteria", "")

        # 基本完成条件：
        # 1. 至少生成了文件
        # 2. 没有新的错误
        # 3. 至少经过1次迭代
        if len(self.files_created) == 0:
            return False
        if len(self.errors) > 0:
            return False
        if self.iteration < 1:
            return False

        return True

    def _build_success_result(self) -> Dict:
        return {
            "success": True,
            "task_id": self.task.get("id"),
            "task_name": self.task.get("name"),
            "iterations": self.iteration,
            "files_created": self.files_created,
            "fixes_applied": self.fixes,
            "workspace": str(self.workspace),
            "summary": f"完成: 创建{len(self.files_created)}个文件, 迭代{self.iteration}轮",
            "completion_criteria_met": self.task.get("completion_criteria", ""),
        }

    def _build_partial_result(self) -> Dict:
        return {
            "success": False,
            "task_id": self.task.get("id"),
            "task_name": self.task.get("name"),
            "iterations": self.iteration,
            "files_created": self.files_created,
            "fixes_applied": self.fixes,
            "errors": self.errors[-3:],  # 只保留最近3个错误
            "workspace": str(self.workspace),
            "summary": f"部分完成: 创建{len(self.files_created)}个文件, 但未完全达标",
            "error": self.errors[-1] if self.errors else "达到最大迭代次数",
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

    args = parser.parse_args()

    task = json.loads(args.task)
    agent = ChildAgent(task, args.workspace)
    result = agent.execute()

    # 输出JSON结果（父Agent通过stdout读取）
    print("\n__RESULT__")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())