# 演示项目：用户管理系统
# 此项目用于演示Claude Code父子多层嵌套自适应Loop系统

# 后端入口
from fastapi import FastAPI

app = FastAPI(title="用户管理系统")

@app.get("/")
def root():
    return {"message": "用户管理系统API", "version": "1.0.0"}

# TODO: 将由子Agent自动生成完整API代码