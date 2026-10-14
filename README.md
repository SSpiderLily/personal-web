# 个人网站

最小展示网站：FastAPI 提供默认个人信息，Vue 3 + Vite 渲染单页，包含后端生成随机点数的骰子小游戏。暂不包含数据库、登录、后台管理或部署配置。

## 开发环境

Python 3.13、uv、Node.js 22.12+、npm。后端依赖在项目内 `.venv` 安装，不改动全局 Python 环境。

首次安装（从本目录执行）：

```sh
cd backend
uv sync --locked --python /Library/Frameworks/Python.framework/Versions/3.13/bin/python3
cd ../frontend
npm ci
```

## 启动

终端一（本目录）：

```sh
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

终端二（本目录）：

```sh
cd frontend
npm run dev
```

打开 http://127.0.0.1:5180 。后端接口文档：http://127.0.0.1:8010/docs 。两个终端分别按 Ctrl+C 停止服务。

前端通过 Vite 将 `/api` 请求代理到后端 8010 端口。若修改后端端口，同步修改 `frontend/vite.config.js`。生产部署时需单独配置反向代理。

## 修改与构建

- 默认介绍和项目内容：`backend/app/main.py`。
- 页面结构：`frontend/src/App.vue`；样式：`frontend/src/style.css`。
- 骰子：点击页面骰子，前端调用 `POST /api/dice/roll`，后端返回 1～6 点；不保存数据。组件位于 `frontend/src/components/DiceGame.vue`。
- 健康检查：`GET /api/health`；个人信息：`GET /api/profile`。
- 前端构建：在 `frontend` 执行 `npm run build`，结果输出到 `dist/`。`npm run preview` 可预览构建，仍需后端运行。

状态见 [搭建计划](docs/implementation-plan.md)，验证证据见 [验证记录](docs/validation-log.md)。

本机 PATH 中存在不可运行的旧 Python 3.7，因此首次安装显式指定 Python 3.13 路径。其他机器请替换为本机可用的 Python 3.13 路径。
