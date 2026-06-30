// 演示项目 - 前端入口
// 一个简单的用户管理页面框架

export interface User {
  id: number;
  username: string;
  email: string;
  fullName: string;
  status: UserStatus;
  role: string;
  createdAt: string;
}

export type UserStatus = 'active' | 'inactive' | 'banned';

export interface ApiResponse<T> {
  data: T;
  message: string;
  success: boolean;
}

// API 基础配置
const API_BASE = 'http://localhost:8000';

// 用户 API 封装
export async function fetchUsers(params?: {
  page?: number;
  size?: number;
  status?: UserStatus;
  search?: string;
}): Promise<ApiResponse<User[]>> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set('page', String(params.page));
  if (params?.size) searchParams.set('size', String(params.size));
  if (params?.status) searchParams.set('status', params.status);
  if (params?.search) searchParams.set('search', params.search);

  const response = await fetch(`${API_BASE}/api/users?${searchParams}`);
  return response.json();
}

export async function createUser(userData: Partial<User>): Promise<ApiResponse<User>> {
  const response = await fetch(`${API_BASE}/api/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(userData),
  });
  return response.json();
}

export async function deleteUser(id: number): Promise<ApiResponse<null>> {
  const response = await fetch(`${API_BASE}/api/users/${id}`, {
    method: 'DELETE',
  });
  return response.json();
}

console.log('用户管理前端模块已加载 (演示项目)');