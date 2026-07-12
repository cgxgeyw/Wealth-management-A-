# A 股交易智能体

这是一个面向 A 股市场的投研辅助平台。当前阶段先搭建电脑端服务框架，暂不实现 Agent。

## 技术栈

- 后端：Python + FastAPI
- 前端：React + TypeScript + Vite
- 数据库：PostgreSQL，后续接入
- 缓存：Redis，后续接入

## 目录结构

```text
backend/   FastAPI 服务
frontend/  React 电脑端 Web
docs/      设计文档
```

## 启动后端

Windows PowerShell 可直接从仓库根目录运行：

```powershell
.\start-backend.ps1
```

默认启用热重载；使用 `.\start-backend.ps1 -NoReload` 可关闭，使用 `-Port 8010` 可指定端口。

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

## 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认地址：

```text
http://127.0.0.1:5173
```

## 当前已实现

- 服务健康检查：`GET /api/health`
- 模块列表：`GET /api/modules`
- 数据源列表：`GET /api/data/providers`
- 数据路由列表：`GET /api/data/routes`
- 采集日志：`GET /api/data/fetch-logs`
- 数据源健康检查：`POST /api/data/health-check`
