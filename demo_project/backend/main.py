"""
演示项目 - 后端主入口
=====================
一个完整的 FastAPI 用户管理后端，作为演示项目的起点。
由 Loop System 的父Agent规划、子Agent生成。
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime

app = FastAPI(
    title="用户管理系统 API",
    description="演示项目 - 由 Loop System 自动维护",
    version="0.1.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 数据存储（演示用内存存储）
# ============================================================
_users_db: List[dict] = [
    {
        "id": 1, "username": "admin", "email": "admin@example.com",
        "full_name": "系统管理员", "status": "active", "role": "admin",
        "created_at": "2024-01-01T00:00:00", "updated_at": "2024-01-01T00:00:00"
    },
    {
        "id": 2, "username": "editor", "email": "editor@example.com",
        "full_name": "编辑用户", "status": "active", "role": "editor",
        "created_at": "2024-01-02T00:00:00", "updated_at": "2024-01-02T00:00:00"
    },
]
_next_id = 3


# ============================================================
# API 路由
# ============================================================
@app.get("/")
async def root():
    """根路由 - 健康检查"""
    return {
        "status": "ok",
        "service": "用户管理系统",
        "version": "0.1.0",
        "maintained_by": "Loop System",
        "users_count": len(_users_db)
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/users")
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None
):
    """获取用户列表（分页、筛选、搜索）"""
    filtered = _users_db

    if status:
        filtered = [u for u in filtered if u["status"] == status]

    if search:
        search_lower = search.lower()
        filtered = [
            u for u in filtered
            if search_lower in u["username"].lower()
            or search_lower in u["email"].lower()
            or (u.get("full_name") and search_lower in u["full_name"].lower())
        ]

    total = len(filtered)
    total_pages = max(1, (total + size - 1) // size)
    start = (page - 1) * size
    items = filtered[start:start + size]

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "total_pages": total_pages
    }


@app.get("/api/users/{user_id}")
async def get_user(user_id: int):
    """获取单个用户详情"""
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="无效的用户ID")

    for user in _users_db:
        if user["id"] == user_id:
            return user

    raise HTTPException(status_code=404, detail="用户不存在")


@app.post("/api/users", status_code=201)
async def create_user(user_data: dict):
    """创建新用户"""
    global _next_id

    # 基本校验
    if not user_data.get("username"):
        raise HTTPException(status_code=422, detail="用户名不能为空")
    if not user_data.get("email"):
        raise HTTPException(status_code=422, detail="邮箱不能为空")

    # 检查重复
    for u in _users_db:
        if u["username"] == user_data["username"]:
            raise HTTPException(status_code=409, detail="用户名已存在")
        if u["email"] == user_data["email"]:
            raise HTTPException(status_code=409, detail="邮箱已存在")

    now = datetime.now().isoformat()
    new_user = {
        "id": _next_id,
        "username": user_data["username"],
        "email": user_data["email"],
        "full_name": user_data.get("full_name"),
        "status": user_data.get("status", "active"),
        "role": user_data.get("role", "viewer"),
        "created_at": now,
        "updated_at": now,
    }
    _users_db.append(new_user)
    _next_id += 1
    return new_user


@app.put("/api/users/{user_id}")
async def update_user(user_id: int, user_data: dict):
    """更新用户信息"""
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="无效的用户ID")

    for i, user in enumerate(_users_db):
        if user["id"] == user_id:
            allowed_fields = {"email", "full_name", "status", "role"}
            for key, value in user_data.items():
                if key in allowed_fields:
                    _users_db[i][key] = value
            _users_db[i]["updated_at"] = datetime.now().isoformat()
            return _users_db[i]

    raise HTTPException(status_code=404, detail="用户不存在")


@app.delete("/api/users/{user_id}", status_code=204)
async def delete_user(user_id: int):
    """删除用户（软删除 - 标记为 inactive）"""
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="无效的用户ID")

    for i, user in enumerate(_users_db):
        if user["id"] == user_id:
            _users_db[i]["status"] = "inactive"
            _users_db[i]["updated_at"] = datetime.now().isoformat()
            return None

    raise HTTPException(status_code=404, detail="用户不存在")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)