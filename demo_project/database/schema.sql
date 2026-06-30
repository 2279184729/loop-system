-- 演示项目数据库Schema
-- 用户管理系统基础表结构

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active',
    role VARCHAR(50) DEFAULT 'viewer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- 插入示例数据
INSERT OR IGNORE INTO users (username, email, password_hash, full_name, role) VALUES
('admin', 'admin@example.com', 'hash_admin_placeholder', '系统管理员', 'admin'),
('editor', 'editor@example.com', 'hash_editor_placeholder', '编辑用户', 'editor'),
('viewer', 'viewer@example.com', 'hash_viewer_placeholder', '只读用户', 'viewer');