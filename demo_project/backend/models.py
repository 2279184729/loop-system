"""
用户模型定义
=============
演示项目的基础数据模型。
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"


@dataclass
class User:
    """用户模型"""
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    status: UserStatus = UserStatus.ACTIVE
    role: str = "viewer"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "status": self.status.value,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Role:
    """角色模型"""
    id: int
    name: str
    description: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    phone_number: Optional[str] = None  # 自动添加字段


# 预定义权限
PERMISSIONS = {
    "user:read": "查看用户",
    "user:create": "创建用户",
    "user:update": "更新用户",
    "user:delete": "删除用户",
    "role:manage": "角色管理",
}

# 预定义角色
DEFAULT_ROLES = [
    Role(id=1, name="admin", description="系统管理员",
         permissions=list(PERMISSIONS.keys())),
    Role(id=2, name="editor", description="编辑者",
         permissions=["user:read", "user:create", "user:update"]),
    Role(id=3, name="viewer", description="观察者",
         permissions=["user:read"]),
]