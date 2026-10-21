# 个人网站

个人项目展示网站：FastAPI 提供默认个人信息，Vue 3 + Vite 渲染单页，包含后端生成随机点数的骰子小游戏。暂不包含数据库、登录或后台管理。CI 仅测试和构建，不部署服务器。

## 开发环境

本地默认 Python 3.13，CI 同时覆盖线上现用的 3.14；uv 0.12.3、Node.js 22.22.1（见 frontend/.nvmrc）、npm。后端依赖在项目内 `.venv` 安装，不改动全局 Python 环境。

首次安装（从本目录执行）：

```sh
cd backend
uv sync --locked --python 3.13
cd ../frontend
npm ci
```

## 启动

终端一（本目录）：

```sh
cd backend
uv run --locked uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

终端二（本目录）：

```sh
cd frontend
npm run dev
```

打开 http://127.0.0.1:5180 。后端接口文档：http://127.0.0.1:8010/docs 。两个终端分别按 Ctrl+C 停止服务。

前端通过 Vite 将 `/api` 请求代理到后端 8010 端口。若修改后端端口，同步修改 `frontend/vite.config.js`。生产部署时需单独配置反向代理。

## 修改与构建

- 默认个人介绍：`backend/app/main.py`；公开项目列表及完整描述：`frontend/src/App.vue` 的 `projects`。本网站自身不列入项目作品。
- 首页由个人介绍和两栏内容组成：左侧项目卡片列表，旅行助手排首位；右侧小工具放置骰子。820px及以下侧栏移到列表下方，540px及以下项目卡片上下排列。卡片可点击或按回车打开原生详情弹窗，展示完整描述、功能和演示/源码入口；Esc、关闭按钮或遮罩可关闭。预览图为 `frontend/src/assets/trip-preview.png`，截自本机运行的旅行助手首页（需求填写页面）；卡片和详情均展示完整截图。在线演示已启用，链接为 `/trip/`，在新标签页打开；本机开发和本地构建预览默认打开 `http://127.0.0.1:5173/`，生产构建仍使用 `/trip/`，由 Nginx 提供该路径。个人资料接口失败不阻塞精选项目展示。
- 页面结构：`frontend/src/App.vue`；样式：`frontend/src/style.css`。
- 骰子：点击页面骰子，前端调用 `POST /api/dice/roll`，后端返回 1～6 点；不保存数据。组件位于 `frontend/src/components/DiceGame.vue`。
- 健康检查：`GET /api/health`；个人信息：`GET /api/profile`。
- 前端构建：在 `frontend` 执行 `npm run build`，结果输出到 `dist/`。`npm run preview` 可预览构建，仍需后端运行。

状态见 [搭建计划](docs/implementation-plan.md)，验证证据见 [验证记录](docs/validation-log.md)。

## 本地检查与 CI

使用 nvm 时，先在 frontend 执行 `nvm install`、`nvm use`；不使用 nvm 时自行安装 `.nvmrc` 指定版本。安装 uv 0.12.3 后，在项目根目录执行：

```sh
bash scripts/check.sh
```

脚本按锁文件同步后端依赖、执行5项HTTP契约测试、检查现有Gunicorn启动配置，然后执行 `npm ci` 和生产构建。任一步失败即退出。会更新本地虚拟环境、node_modules和dist，不启动常驻服务、不访问线上API。首次安装依赖需要联网。

后端使用标准库 unittest 和 FastAPI TestClient（当前 Starlette 使用 httpx2），无需另起后端进程。接口测试不代表浏览器布局或随机分布已验收。修改页面后仍需人工检查桌面/窄屏、详情弹窗、骰子交互。本地已移除生产旅行助手代理。旅行助手需单独在本机启动；未启动时演示入口无法连接，不会自动转到线上。

`.github/workflows/ci.yml` 在分支推送、面向main的PR或手动触发时运行同一命令，分别覆盖Python 3.13/3.14。没有部署步骤或服务器凭据。需要先提交、推送才能得到GitHub实际运行结果；分支保护仍需另行设置，CI文件本身不会禁止合并失败PR。

日常顺序：任务分支修改 → `bash scripts/check.sh` → 人工检查页面 → 查看差异 → 提交并推送任务分支 → 查看两个CI检查 → 创建PR。当前部署差异与本阶段状态见[执行计划](docs/implementation-plan.md)，验收证据见[验证记录](docs/validation-log.md)。

依赖变更时，后端更新 `pyproject.toml` 并运行 `uv lock`，前端使用npm更新依赖与package-lock.json；依赖声明和锁文件一起提交。不要在服务器上直接运行本地检查脚本：它会同步环境并重建dist，线上部署另行安排。

## 本地联调与构建预览

只改个人网站时，按上面的两个终端启动即可，不需要启动旅行助手。需要联调旅行助手时，在其项目目录按该项目README启动本地服务（前端5173、后端8000）；个人网站后端使用8010，不冲突。旅行助手自身的模型和地图调用仍取决于它的本地配置，不属于离线模拟测试。

在frontend执行 `npm run preview:local` 会先构建到dist-local，再在 http://127.0.0.1:4173 预览；API仍代理本机8010，演示链接仍指向本机5173。`npm run build` 只生成生产dist，演示地址为/trip/；普通 `npm run preview` 用于查看生产产物，本机没有生产Nginx的/trip/路由，不能用于验收旅行助手跳转。

如需修改本地演示地址，将 `.env.development.example` 复制为 `.env.development.local` 并修改 `VITE_TRIP_DEMO_URL`，重启开发服务或重建本地预览。要访问线上演示，应显式填写完整线上URL；此时操作会访问生产服务。不要把本地覆盖写进通用.env.local，以免影响生产构建。VITE_变量会进入浏览器，禁止填写密钥。
