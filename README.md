# 个人网站

Vue 3 + Vite 展示个人信息、旅行助手项目和小工具占位，FastAPI 提供个人信息与骰子点数。公开业务接口仍使用现有数据；后台已接通单管理员真实登录、会话和受保护框架，业务编辑模块待后续接入。

后台需求与进度见[后台计划](docs/admin-management-plan.md)；既有部署历史与未核实事项见[部署归档](docs/archive/2026-10-21-auto-deployment-plan.md)；测试与发布证据见[验证记录](docs/validation-log.md)。

## 本地开发

使用 Python 3.13（CI 同时覆盖 3.14）、uv 0.12.3、Node.js 22.22.1（`frontend/.nvmrc`）和 npm。Python 依赖安装在项目虚拟环境，不修改全局环境。

首次安装，从项目根目录执行：

```sh
cd backend
uv sync --locked --python 3.13
cd ../frontend
npm ci
```

从项目根目录分别在两个终端启动。第一个命令自动管理 SSH 隧道和后端，不再需要单独的 SSH 终端：

```sh
bash scripts/dev.sh
```

```sh
cd frontend
npm run dev
```

首页为 http://127.0.0.1:5180 ，API 文档为 http://127.0.0.1:8010/docs 。前端将 `/api` 代理到 8010；修改端口时同步 `frontend/vite.config.js`。两个终端分别按 Ctrl+C 停止。

## 后端环境配置

所有后端配置集中在 `backend/app/settings.py` 的 `Settings` 声明，业务代码只通过 `get_settings()` 读取。进程环境变量优先于本地文件，配置在每个进程首次读取后缓存，修改后重启后端。`APP_ENV` 支持 development、test、production；切换到 test 或 production 必须通过进程环境变量，不能在本地 `.env` 中切换。

本地首次在 backend 目录执行 `test -f .env || cp .env.example .env`，再编辑 `.env`。该文件不提交 Git；建议权限设为 `chmod 600 .env`。路径按配置模块位置解析，从其他目录启动也读取同一个 backend/.env。默认开发参数指向 SSH 隧道 `127.0.0.1:15432` 和 `personal_web_dev` 账号/数据库，密码仅在本机填写，不发送或提交。生产模板为 `backend/.env.production.example`，真实生产配置保存在服务器 `/etc/personal-web/app.env`。

本地启动使用 `bash scripts/dev.sh`。它只允许 development 环境，先用现有 SSH 密钥/agent 建立隧道，等待本地转发端口就绪后启动 Uvicorn reload。SSH 认证失败、端口占用或启动超时会明确失败；运行中隧道断开会停止后端。按 Ctrl+C 或收到 SIGTERM 时只清理本次命令创建的 SSH 与后端进程组，不结束已有进程。已有手动隧道占用端口时请先自行关闭，脚本不会盲目复用未知连接。

SSH 参数与数据库参数统一放在 backend/.env：DEV_SSH_HOST 为服务器地址或 SSH config 别名，DEV_SSH_USER 为登录账号，DEV_SSH_PORT 默认 22，DEV_DB_REMOTE_PORT 默认 5432，DEV_BACKEND_PORT 默认 8010。DB_HOST 保持 127.0.0.1，DB_PORT 默认 15432。新副本需把 .env.example 中的 DEV_SSH_HOST 占位值改成实际地址；本机现有 .env 已追加验证过的服务器地址，原数据库密码保持不变。首次使用的机器需先配置可用的 SSH 密钥、agent 和已核对的 known_hosts；自动启动不弹出密码或指纹确认提示，不保存 SSH 密码，也不关闭主机校验。

15432 只是 Mac 的本地入口，云端数据库仍用 5432，SSH 走服务器 22；无需在云防火墙放通 15432 或公网数据库端口。自动建隧道仅发生在本地启动命令中，不在 FastAPI 导入或生产启动时执行。生产仍由原有 Gunicorn/systemd 启动。

只验证配置读取时不需要隧道；在 backend 目录执行以下命令，只打印环境、数据库位置和 debug，不打印密码：

```sh
uv run --locked python -c 'from app.settings import get_settings; s = get_settings(); print(s.app_env, s.db_host, s.db_port, s.db_name, s.debug)'
```

test、production 模式完全忽略本地 `.env`。生产必须显式提供 DB_HOST、DB_PORT、DB_NAME、DB_USER、非空 DB_PASSWORD，且 DEBUG=false；缺失或非法值会阻止启动，错误文本不显示输入值。配置密码使用 SecretStr 包装，不在对象显示或配置 JSON 中输出；不要主动记录其原文或完整验证错误数据。

现已提供 psycopg 连接与事务作用域：`app.database.connection()` 用于独立读取，`transaction()` 用于原子写入；正常退出提交，异常回滚，退出关闭连接。配置仅经 Settings/get_settings() 读取，非空的 libpq PG* 连接/会话环境覆盖会在建连前被拒绝，请清除这类变量并使用 DB_* 配置。模块导入不连接、不建隧道、不迁移；现有公开接口仍不访问数据库；管理会话与鉴权使用数据库。开发环境建连前需填写密码；test 模式只允许专用本地 personal_web_test_* 目标，不能使用默认开发库。

## 开发库迁移

从项目根目录启动 `bash scripts/dev.sh` 保持开发隧道运行后，在另一终端执行版本迁移：

```sh
cd backend
uv run --locked python -m app.migrate
```

入口只接受明确的开发库/同名账号，或隔离测试目标；production 在连接前拒绝。迁移与历史记录使用同一事务和串行锁，历史必须与文件版本及 SHA-256 一致；重复执行无变化，任何待执行版本失败则整批回滚。已执行文件不可修改，新结构另加 `NNN_name.sql`；迁移文件不含事务控制语句，不支持事务外操作，不自动修复手工结构漂移。此命令不自动随应用启动执行，也不用于生产部署。

兼容的 psql 入口仅处理初始 001，后续版本使用上面的 Python 入口。初始字段、外键和约束以 `backend/migrations/001_admin_schema.sql` 为准。`apply_dev.sql` 是 psql 执行入口，仅允许 `personal_web_dev` 数据库和同名账号；十张业务表之外，`schema_migrations` 保存版本及 SHA-256。迁移在单个事务内执行，失败回滚；相同版本及校验和重复执行时跳过，不覆盖业务数据。已执行的迁移文件不可再修改，结构变更另建后续迁移。版本跳过不自动修复手工改表造成的结构偏移。

保持本地开发启动入口建立的 SSH 隧道运行后，从项目根目录执行以下命令。`psql` 需在 PATH 中；本机客户端为 `/Library/PostgreSQL/17/bin/psql`，可用此完整路径替换。密码仅在交互提示中输入，不写入命令或 Git。

```sh
migration_checksum="$(shasum -a 256 backend/migrations/001_admin_schema.sql | cut -d ' ' -f 1)"
psql -X -W -h 127.0.0.1 -p 15432 -U personal_web_dev -d personal_web_dev -v ON_ERROR_STOP=1 -v migration_checksum="$migration_checksum" -f backend/migrations/apply_dev.sql
```

仅在初始业务表仍为空时，可执行回滚约束验证：

```sh
psql -X -W -h 127.0.0.1 -p 15432 -U personal_web_dev -d personal_web_dev -v ON_ERROR_STOP=1 -f backend/migrations/tests/verify_dev.sql
```

验证入口自动回滚测试记录，不能单独运行其中的断言片段；它不是日常清库命令。SQL 迁移不自动创建真实管理员、个人资料或工具种子数据，也不接入应用数据库连接。`updated_at` 由后续后端写入时更新；详情块、截图交换位置的事务须先将对应唯一约束设为 DEFERRED，提交前会检查最终顺序唯一。正式接口仍须保证已发布内容每次保存的完整性、图文事务一致、图片鉴权及跨日访客标识稳定；行为边界见[后台计划](docs/admin-management-plan.md)。此入口不用于生产库。

## 开发环境管理员初始化

先配置开发库并保持 `bash scripts/dev.sh` 运行，再在另一个交互终端执行。首次使用数据库时先运行上方迁移；已有迁移重复运行不会覆盖数据。

```sh
cd backend
uv run --locked python -m app.migrate
uv run --locked python -m app.admin_init
```

按提示输入账号（1—64字符）及两次密码（12—128字符）。密码输入不回显，不放在命令参数、聊天或环境变量中。初始化只创建一个账号，已有账号时拒绝覆盖；无默认账号密码，无密码重置入口。不要对已有账号反复初始化。

访问前端 `/admin` 登录；本轮工作目录预览使用 http://127.0.0.1:5182/admin 。会话默认8小时，`ADMIN_SESSION_HOURS` 可设1—168。退出失败时页面保留身份并提示重试，服务端撤销成功后才回到登录页。浏览器只使用 HttpOnly、SameSite=Strict Cookie，CSRF值只存内存；真实开发库账号初始化与本地隔离测试是两项不同验收。

`ADMIN_ALLOWED_ORIGINS` 使用精确来源的 JSON 数组，例如 `ADMIN_ALLOWED_ORIGINS='["http://127.0.0.1:5182"]'`。开发默认允许 localhost/127.0.0.1 的5180、5182端口；更换前端端口时须显式配置并重启后端。不开放跨域访问。

生产默认不开放管理接口：必须配置可信 HTTPS 来源，且应用实际识别为 HTTPS。反向代理和可信代理配置在部署阶段验证，不能信任任意客户端转发头。阶段 B 的初始化命令拒绝 production；生产首次账号初始化、HTTPS、真实反向代理和发布验收仍待部署阶段处理，不能直接照用开发初始化步骤。

## 现有功能与修改入口

- 个人信息：`backend/app/main.py`；页面与项目内容：`frontend/src/App.vue`；样式：`frontend/src/style.css`。公开作品仅旅行助手，不包含个人网站自身；个人信息加载失败仍可浏览项目并重试。
- 项目：卡片可点击或按回车打开详情，支持 Esc、关闭按钮和遮罩关闭、恢复焦点及背景滚动。预览图 `frontend/src/assets/trip-preview.png` 来自旅行助手实际需求填写页，完整比例展示。
- 小工具：`ToolGrid.vue` 目前仅九个占位图标；`DiceGame.vue` 是独立悬浮骰子，点数由 `POST /api/dice/roll` 生成，不保存数据。支持减少动态偏好、超时重试和 WebGL 不可用时的简化显示；动画与点数逻辑在 `frontend/src/dice/`。
- 健康与个人信息接口分别为 `GET /api/health`、`GET /api/profile`。后端接口定义和字段以代码为准。

- 后台：访问 `/admin`，使用真实管理员账号登录。刷新恢复服务端会话，退出撤销会话；四个业务模块暂为待接入说明。开发和生产构建使用同一真实接口，生产管理接口须另行落实 HTTPS 配置。

## 检查与预览

在项目根目录执行 `bash scripts/check.sh`。它安装锁定依赖，运行部署保护、后端和前端测试，检查 Gunicorn 配置，再构建前端；会更新 `.venv`、`node_modules` 和构建产物，不启动常驻服务、不调用线上 API。首次安装需要联网，不在生产服务器上直接运行该脚本。

- 单独检查前端：`npm --prefix frontend test`；生产构建：`npm --prefix frontend run build`，输出 `frontend/dist/`。
- 本地构建预览：在 frontend 执行 `npm run preview:local`，输出 `dist-local/` 并在 http://127.0.0.1:4173 提供页面，API 仍需本机 8010 后端。
- 旅行助手演示：开发与本地构建预览默认指向本机 5173，需另启旅行助手服务（前端 5173、后端 8000）；个人网站不代理到生产服务。生产构建使用 `/trip/`。普通 `npm run preview` 预览生产产物，本机没有生产 Nginx 的 `/trip/` 路由，不能用它验收演示跳转。
- 覆盖本地演示地址：将 `frontend/.env.development.example` 复制为 `.env.development.local`，修改 `VITE_TRIP_DEMO_URL` 后重启或重新构建。勿写入通用 `.env.local`；`VITE_` 会进入浏览器，不存放密钥。填写线上地址会访问真实服务。
- 依赖变更时同步声明与锁文件：后端 `pyproject.toml` / `uv.lock`，前端 `package.json` / `package-lock.json`。修改页面后另查桌面、窄屏、详情和骰子交互，构建通过不代表这些体验已验收。


数据库专项另执行：

```sh
bash scripts/test-db.sh
# 如需指定本机 PostgreSQL 工具目录：
PG_BIN=/Library/PostgreSQL/17/bin bash scripts/test-db.sh
```

该入口使用本机 initdb/pg_ctl/psql，每次新建并清理临时集群和数据库，仅监听独立 Unix socket，不需要 SSH，也不使用现有开发/生产库。普通统一检查会明确跳过真实 PostgreSQL 用例，必须另跑此专项才能验收数据库功能。可通过 PG_BIN 指定工具目录；未安装服务端程序时专项明确失败。当前已实测 macOS PostgreSQL 17.11，Linux 工具发现逻辑尚未实测；云端开发库 18.6 仅做新驱动只读冒烟。

## 发布与恢复

日常流程：任务分支修改 → 本地检查与页面验证 → 提交推送 → PR 检查 → 获得发布授权后合并。`.github/workflows/ci.yml` 在分支、PR 和手动触发时运行统一检查；部署仅允许 main 且全部检查通过。CI 本身不阻止合并失败 PR，主分支保护的未核实事项见部署归档。

自动发布要求仓库变量 `DEPLOY_ENABLED=true`；手动发布在 Actions 的 CI → Run workflow 中选择 main 并勾选 deploy。服务器配置也须 `enabled=true`。历史开关和真实发布证据以验证记录为准，合并前核对实际开关，避免把提交授权等同于发布授权。

GitHub `production` 环境限制 main；变量为 `DEPLOY_HOST`、`DEPLOY_USER`、`DEPLOY_ENABLED`，Secrets 为 `DEPLOY_SSH_KEY`、`DEPLOY_KNOWN_HOSTS`。Actions 使用单独登录密钥连接 ubuntu；服务器使用自身 GitHub SSH 密钥拉取代码，私钥不在仓库中。

已记录的生产配置：

- `/opt/personal-web-deploy/current` 指向当前 release；保留旧 release，暂不自动清理。`/opt/personal-web-tools/bin` 提供 Node 22.22.1、uv 0.12.3，Python 为 `/usr/bin/python3` 的 3.14。
- `/etc/personal-web/deploy.json` 为运行配置，使用 GitHub SSH 仓库地址及腾讯 HTTPS 依赖镜像；服务名为 `fastapi-personal-web`，Gunicorn 双 worker 监听本机 8000。
- `/usr/local/lib/personal-web/deploy.py` 是服务器部署入口；修改仓库脚本后须显式同步此文件，发布不会自动覆盖它。

部署脚本校验锁定依赖与包哈希，准备新 release 后才切换、重启并检查 API、首页、资源和版本标记。失败尝试恢复上一链接，仍返回发布失败；发布锁、Actions 并发组和过期提交检查防止交叠覆盖。重启可能短暂中断，进程强杀或断电不能保证自动回退。

### 首次加载生产配置（需要在服务器操作）

以下步骤用于首次接入或重建环境。当前服务器已完成接入并复验，证据见[验证记录](docs/validation-log.md)。配置文件独立于 release，后续发布继续使用同一个文件；生产模板中的空密码必须替换为生产账号密码。密码和其他密钥不放在前端、Git 或聊天中。

1. 创建配置目录和文件。已有文件时保留内容；若是首次接入，按 `backend/.env.production.example` 填写全部参数。使用 `sudoedit` 编辑时，密码不会出现在命令参数或 shell 历史里：

   ```sh
   sudo install -d -m 0755 /etc/personal-web
   if ! sudo test -e /etc/personal-web/app.env; then
     sudo install -o root -g root -m 0600 /dev/null /etc/personal-web/app.env
   fi
   sudoedit /etc/personal-web/app.env
   sudo chown root:root /etc/personal-web/app.env
   sudo chmod 600 /etc/personal-web/app.env
   ```

2. 执行 `sudo systemctl edit fastapi-personal-web`，保留已有配置并加入：

   ```ini
   [Service]
   EnvironmentFile=/etc/personal-web/app.env
   ```

3. 执行 `sudo systemctl daemon-reload`。包含统一配置模块的代码按既有流程发布后，服务重启会加载生产配置。若要手动验证重启，执行：

   ```sh
   sudo systemctl restart fastapi-personal-web
   sudo systemctl is-active fastapi-personal-web
   curl -fsS http://127.0.0.1:8000/api/health
   ```

应分别返回 active 和健康结果。它们只证明服务/原健康接口运行，不证明数据库连接成功。上线前还须核对实际生产配置、服务进程、数据库连接及既有回归。配置值改变时修改 app.env 并重启服务；仅修改文件内容无需再次 daemon-reload。不要通过打印整个服务环境或配置对象来核对密码。

当前页面提交号可查看 http://124.223.69.7/__release.txt 并与目标提交核对；旅行助手 `/trip/` 使用独立目录和服务，不随个人网站发布。

首次发布前的旧站点保留在 `/opt/personal-web`，备份位于 `/opt/personal-web-deploy/backups/first-deploy-20261021`。该目录的 `restore-old.sh` 会恢复首次发布前站点并重启个人网站、重载 Nginx；它不等同于回退最近一个 release。真实故障回退尚未演练，未确认事项见部署归档。

## 文档维护

文档维护与计划归档按 [production 统一规则](../AGENTS.md#文档管理)执行。
