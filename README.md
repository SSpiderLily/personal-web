# 个人网站

Vue 3 + Vite 展示个人信息、旅行助手项目和小工具占位，FastAPI 提供个人信息与骰子点数。后台已接通单管理员真实登录、项目编辑/发布/下架、网站资料与头像、小工具展示设置。项目和资料由数据库驱动，图片按当前公开引用受控读取；已接通公开首页与成功打开项目详情的访问记录，以及后台近7/30天统计。

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

现已提供 psycopg 连接与事务作用域：`app.database.connection()` 用于独立读取，`transaction()` 用于原子写入；正常退出提交，异常回滚，退出关闭连接。配置仅经 Settings/get_settings() 读取，非空的 libpq PG* 连接/会话环境覆盖会在建连前被拒绝，请清除这类变量并使用 DB_* 配置。模块导入不连接、不建隧道、不迁移；公开工具设置、管理会话及后台功能使用数据库；健康与骰子点数不依赖数据库；个人信息改从资料表读取，并兼容返回已发布项目摘要。开发环境建连前需填写密码；test 模式只允许专用本地 personal_web_test_* 目标，不能使用默认开发库。

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

验证入口自动回滚测试记录，不能单独运行其中的断言片段；它不是日常清库命令。001不创建管理员或个人资料；002幂等补充九个工具占位及独立骰子的默认展示记录，不覆盖已有设置；003追加现有项目展示字段和显式内容初始化标记。管理员仍由终端单独初始化。`updated_at` 由后续后端写入时更新；详情块、截图交换位置的事务须先将对应唯一约束设为 DEFERRED，提交前会检查最终顺序唯一。正式接口仍须保证已发布内容每次保存的完整性、图文事务一致、图片鉴权及跨日访客标识稳定；行为边界见[后台计划](docs/admin-management-plan.md)。此入口不用于生产库。

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

默认HTTPS模式的生产环境不开放未配置可信HTTPS来源的管理接口；临时HTTP+SSH模式见下方发布说明。反向代理和可信代理配置在部署阶段验证，不能信任任意客户端转发头。阶段 B 的初始化命令拒绝 production；生产首次账号初始化、HTTPS、真实反向代理和发布验收仍待部署阶段处理，不能直接照用开发初始化步骤。

## 现有功能与修改入口

- 个人信息：`backend/app/profile.py`；项目：`backend/app/projects.py`；页面接入：`frontend/src/App.vue`；样式：`frontend/src/style.css`。初始化只保留当前旅行助手作品，不加入个人网站示例；项目和资料独立加载，失败可分别重试，无项目时显示空态。
- 项目：卡片可点击或按回车打开详情，支持 Esc、关闭按钮和遮罩关闭、恢复焦点及背景滚动。预览图 `frontend/src/assets/trip-preview.png` 来自旅行助手实际需求填写页，完整比例展示。
- 小工具：后台可保存九个占位工具的显示/排序和独立骰子的显示。公开首页从 `/api/tools` 读取；读取成功前不挂载骰子，失败显示重试，全部隐藏时显示空态。`ToolGrid.vue` 仍仅占位图标；`DiceGame.vue` 的点数由 `POST /api/dice/roll` 生成，不保存点数。支持减少动态偏好、超时重试和 WebGL 不可用时的简化显示；动画与点数逻辑在 `frontend/src/dice/`。
- 健康与个人信息接口分别为 `GET /api/health`、`GET /api/profile`。后端接口定义和字段以代码为准。

- 后台：访问 `/admin`，使用真实管理员账号登录。刷新恢复服务端会话，退出撤销会话；项目管理、网站内容与小工具管理可实际保存设置，访问统计可查看近7天或近30天的网站访问人数和项目浏览人数，并切换区间、刷新或重试。开发和生产构建使用同一真实接口，生产管理接口须另行落实 HTTPS 配置。

## 项目与网站内容管理

阶段D先运行开发库迁移。只有尚未有项目/资料的新开发环境，才显式初始化当前网站内容：

```sh
cd backend
uv run --locked python -m app.migrate
uv run --locked python -m app.content_bootstrap
```

初始化仅限development及开发库/账号，保留旅行助手原有介绍、特色列表和真实截图，个人姓名/联系方式留空；不初始化或重置管理员。重复执行已有初始化标记时不覆盖后台修改；没有标记但已有项目/资料时明确拒绝。命令失败时不提交内容，并尝试清理本次新增图片；不是启动时自动灌数据，也不用于生产初始化。数据库和图片的备份/恢复仍归部署阶段。

在 `/admin` 的“项目管理”新增或编辑项目。先保存草稿，再用“预览当前编辑”查看未保存内容；发布后，“保存并更新”会校验完整内容并立即更新公开页面。发布需要名称、简介、至少一项技术栈、有效封面及有效详情块。项目、图文块、截图在一个事务保存；失败保留原公开内容和当前草稿。下架后公开列表/详情不可见，历史统计保留。列表可调整顺序，全部下架时首页显示空态。

“网站内容”可保存个人资料、逐行技能、联系方式、社交链接和头像；姓名、头像与联系方式可空。联系方式支持HTTP(S)、mailto和tel，社交/普通项目链接只接受安全HTTP(S)。旅行助手规范入口 `/trip/` 保存在数据库，浏览器按现有开发/生产规则解析。内容JSON上限256KiB，具体字段数量和长度由服务端校验；不支持HTML富文本。

切换后台模块保留已挂载编辑器的草稿；会话复核或保存遇到网络/503错误时可重试，确认401或退出后清除。公开页面读取 `GET /api/projects`、`GET /api/projects/{id}`、`GET /api/profile`；真实公开首页 `/` 加载时记录网站访问，成功打开已发布项目详情时通过本地 `project-opened` 事件记录项目访问；失败、关闭后返回的旧详情、后台预览和旅行助手 `/trip/` 不触发这些记录。

## 图片上传与统计基础

更新到阶段C后先运行上方开发库迁移，002会补充默认工具设置；此操作不覆盖管理员、会话或已保存工具状态。工具配置不完整或数据库不可用时明确报错，不能用固定默认值重新展示已隐藏项。

图片使用 `UPLOAD_DIR` 指定独立于worktree/release的绝对持久目录，在忽略的 `backend/.env` 中配置后重启开发后端，例如 `UPLOAD_DIR=/绝对路径/personal-web-data/development/uploads`。未配置时只有图片接口503，应用仍能启动。路径各级不允许符号链接，最终目录由应用用户持有且权限0700；首次合法上传自动创建目录，文件0600。macOS `/tmp` 是别名路径时应使用 `/private/tmp` 或规范化后的真实路径。生产路径和权限在8B另行落地，不直接复制开发路径。

上传为 `POST /api/admin/files`，一个名为file的multipart文件；只接受1字节—10MiB、最多4000万像素的静态PNG/JPEG/WebP。客户端须提供当前会话的CSRF及共用请求保护，由浏览器自动设置FormData的Content-Type。成功返回图片id、元数据和受控读取地址；该返回地址的读取须登录，用于草稿和管理员预览。共用组件为 `frontend/src/admin/ImageUpload.vue`，已供项目封面、图文块、截图和头像共用。匿名通过 `GET /api/files/{uuid}` 读取当前已发布项目引用或当前头像；无公开引用统一404。下架、替换、移除后新请求重新判定，仍有其他公开引用则保持可读；不能撤回已经下载的副本。公开与私有读取均no-store/nosniff。上传目录不作为静态目录公开，代码回退不会自动恢复数据库或图片。

统计基础提供受保护的 `GET /api/admin/statistics?days=7`（或30），按Asia/Shanghai自然日、含当天计算，整个区间独立去重。`POST /api/admin/visits` 是唯一允许匿名的统计写接口，仍检查精确Origin、JSON和共用请求头；该路径用于接收现有管理员Cookie并由服务端排除管理员。匿名标识固定一年有效期且跨日复用，不采集IP/UA指纹。阶段7B已接通公开页面记录与后台统计。网站人数和各项目人数分别按同一匿名浏览器在整个7/30天区间独立去重，不是浏览次数，也不能相加为网站总人数；服务端排除真实管理员会话，后台与预览不触发记录，已下架项目的历史统计保留。

访问记录不阻塞内容加载或交互，不显示阻断提示；每项开始处理后有5秒总预算，包含等待锁、网络请求和响应解析，失败或超时不自动重试。所有记录在同页串行；支持 Web Locks 的浏览器还使用同源排他锁协调各标签页，直到响应解析完成才释放。浏览器不支持 Web Locks 时只保证同页串行，首次同时打开多个标签页可能在访客 Cookie 稳定前建立多个匿名标识，导致人数偏多；这一降级不保证跨标签首次访问去重。

技术验证、浏览器联合验收和用户接受分别记入[验证记录](docs/validation-log.md)。当前提供开发预览；生产HTTPS、发布配套和生产真实流量验收仍由部署阶段单独验证。

## 检查与预览

在项目根目录执行 `bash scripts/check.sh`。它安装锁定依赖，运行后端、部署保护、真实临时备份恢复和前端测试，检查 Gunicorn 配置，再构建前端；会更新 `.venv`、`node_modules` 和构建产物，不启动常驻服务、不调用线上 API。首次安装需要联网。阶段F起该检查还要求本机PostgreSQL服务端/客户端工具；缺失明确失败，不把恢复测试跳过当作通过。不在生产服务器上直接运行该脚本。

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

该入口使用本机 initdb/pg_ctl/psql，每次新建并清理临时集群和数据库，仅监听独立 Unix socket，不需要 SSH，也不使用现有开发/生产库。普通后端发现会明确跳过真实 PostgreSQL 业务用例，必须另跑此专项；统一检查另有自建临时集群的真实备份恢复用例。CI两项都运行。可通过 PG_BIN 指定工具目录；未安装服务端程序时专项明确失败。当前已实测 macOS PostgreSQL 17.11，以及Ubuntu上的隔离PostgreSQL18.6；后者自建临时集群，不连接系统5432生产实例。恢复测试采用解析后的/tmp真实目录，兼容macOS符号链接与Linux路径。

## 发布与恢复

### 临时上线：HTTP 前台与 SSH 后台

用户已批准此临时模式：公开地址为 http://124.223.69.7 ，公网`/admin`和管理接口返回404；只有精确的匿名访问记录接口可公开写入。后台只监听服务器本机18880端口，18881为只读发布探针，两个端口都不开放公网。配置模板见`ops/nginx-http-ssh.conf.example`及`ops/deploy-http-ssh.json.example`，实际上线状态见[计划](docs/admin-management-plan.md)及[验证记录](docs/validation-log.md)。原HTTPS模式仍为代码默认值，以下三项必须显式配置：

```dotenv
PRODUCTION_MODE=http_ssh
PUBLIC_ORIGIN=http://124.223.69.7
ADMIN_ALLOWED_ORIGINS='["http://127.0.0.1:18880"]'
```

在Mac保持一个SSH终端运行，再用浏览器打开 http://127.0.0.1:18880/admin ：

```sh
ssh -NT -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=yes \
  -L 127.0.0.1:18880:127.0.0.1:18880 ubuntu@124.223.69.7
```

只使用127.0.0.1及固定18880端口，不换成localhost、局域网地址或公网IP；SSH断开后后台不可达。若端口已占用，先确认是否是自己已有的同一隧道，不盲目结束进程。管理Cookie仅在这个显式模式去掉Secure，仍为HttpOnly、SameSite=Strict及原路径；账号、会话、CSRF与上传校验保留。登录后通过隧道地址预览前台可排除管理员访问；另开公网IP属于另一个Cookie来源，会按匿名浏览器计数。

生产首个管理员在服务器真实终端初始化，不把密码放入命令或聊天：

```sh
sudo systemd-run --unit=personal-web-admin-init --pty --wait --collect \
  --service-type=exec -p User=ubuntu -p UMask=0077 \
  -p EnvironmentFile=/etc/personal-web/app.env \
  --working-directory=/opt/personal-web-deploy/current/backend \
  /opt/personal-web-deploy/current/backend/.venv/bin/python \
  -m app.production_admin_init --expect-database personal_web_prod \
  --expect-user personal_web_prod --execute \
  --lock-file /opt/personal-web-deploy/deploy.lock
```

按提示输入用户名和两次12—128字符密码。已有账号时拒绝覆盖；初始化后通过上述隧道登录。生产内容使用独立入口`python -m app.production_content_init --expect-database personal_web_prod --expect-user personal_web_prod`只读预检；仅在持锁停写且已备份时追加`--execute --lock-file /opt/personal-web-deploy/deploy.lock`录入版本控制中的真实旅行助手、介绍和图片。它不会导入开发库或覆盖已有内容；原开发bootstrap继续拒绝生产。

同机成套备份保存在`/var/backups/personal-web`，校验副本在`/var/backups/personal-web-mirror`，均为私有目录，每次发布前停写创建并校验。两份都在同一服务器，不能抵御整机损毁；本轮按用户明确取舍不要求异机备份。发布仍使用原持锁、备份、迁移、维护、健康和数据核验及代码回退流程，不自动恢复数据库。恢复演练使用独立空测试实例，不能向生产库直接试恢复。

日常流程：任务分支修改 → 本地检查与页面验证 → 提交推送 → PR 检查 → 获得发布授权后合并。`.github/workflows/ci.yml` 在分支、PR 和手动触发时运行统一检查；部署仅允许 main 且全部检查通过。CI 本身不阻止合并失败 PR，主分支保护的未核实事项见部署归档。

自动发布要求仓库变量 `DEPLOY_ENABLED=true`；手动发布在 Actions 的 CI → Run workflow 中选择 main 并勾选 deploy。服务器配置也须 `enabled=true`。历史开关和真实发布证据以验证记录为准，合并前核对实际开关，避免把提交授权等同于发布授权。

GitHub `production` 环境限制 main；变量为 `DEPLOY_HOST`、`DEPLOY_USER`、`DEPLOY_ENABLED`，Secrets 为 `DEPLOY_SSH_KEY`、`DEPLOY_KNOWN_HOSTS`。Actions 使用单独登录密钥连接 ubuntu；服务器使用自身 GitHub SSH 密钥拉取代码，私钥不在仓库中。

已记录的生产配置：

- `/opt/personal-web-deploy/current` 指向当前 release；保留旧 release，暂不自动清理。`/opt/personal-web-tools/bin` 提供 Node 22.22.1、uv 0.12.3，Python 为 `/usr/bin/python3` 的 3.14。
- `/etc/personal-web/deploy.json` 为运行配置，使用 GitHub SSH 仓库地址及腾讯 HTTPS 依赖镜像；服务名为 `fastapi-personal-web`，Gunicorn 双 worker 监听本机 8000。
- `/usr/local/lib/personal-web/deploy.py` 是服务器部署入口；修改仓库脚本后须显式同步此文件，发布不会自动覆盖它。

阶段F的新部署入口保留锁定依赖、包哈希、main/HEAD和启用开关保护，并强制要求`data_safety`配置；旧配置会明确拒绝部署。先构建，再建立维护响应、停止全部个人网站worker、完成数据库/图片备份及副本校验、执行串行迁移，最后切换并检查API/资源/版本、schema和数据库/图片。备份、迁移或新版本验证失败均尝试恢复兼容旧代码；旧服务及数据检查成功后才解除维护，恢复失败则继续维护并报错。代码失败不自动恢复数据库/图片。强杀、断电及部署进程外的写入仍需人工处理。2026-10-25服务器已安装新部署双文件，GitHub自动发布、服务器发布及data_safety开关均关闭；业务current仍是f01d1fe，新后台候选release准备不等同正式发布。

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

### 阶段 F 生产工具与操作顺序

本轮含修复的候选已安装到`/opt/personal-web-deploy/releases/543a1d700b69-s4tz5kgz`，代码基线为`543a1d7`；它没有被current引用。生产表已就绪，旧站仍运行f01d1fe。HTTPS、实际异机备份、生产账号和内容准备好后，仍须按下述流程从最新main构建和发布，不能手工切换旧候选绕过保护。

迁移和备份工具已在生产执行并核验；新后台代码已合并并在服务器构建候选release，但尚未切换current。用户本轮继续排除HTTPS，因此GitHub自动发布及服务器开关保持关闭。具体已验证范围及候选版本见[验证记录](docs/validation-log.md)。正式上线前按[后台计划](docs/admin-management-plan.md)核实真实域名/证书、服务用户、目录和异机备份。配置示例为`ops/deploy-data.json.example`、`ops/nginx-admin.conf.example`及`ops/systemd-override.conf.example`；默认禁用和占位值必须保留到对应前提有证据，不能直接复制示例后启用。

1. 先控制自动发布，固定目标提交和旧schema兼容性。新代码、模板与服务器安装脚本分别核对；安装`deploy.py`时须同时安装同目录`deploy_runtime.py`，该辅助模块不是单独的服务器命令。
2. uploads放在release之外，应用和部署使用同一实际用户；末级目录0700、图片0600，路径不含符号链接。备份根和副本根均为私有0700目录，彼此及uploads不能重叠；持久目录不能被旧release清理覆盖。备份副本必须另有异机隔离及加密挂载证据；第二路径字节校验本身不能证明这两项。
3. 配好真实HTTPS、证书续期及精确`ADMIN_ALLOWED_ORIGINS`。Nginx公网维护响应覆盖个人网站前台和所有`/api/`请求（含统计），保留现有`/trip/`配置；私图不设静态alias。独立127.0.0.1:8081探针监听只供本机使用，不对外反向代理。Gunicorn仅信任127.0.0.1转发协议。合并模板后须在服务器执行`sudo nginx -t`，成功才重载；模板不替代现有完整站点配置。
4. systemd继续使用外部`EnvironmentFile`。新部署适配器也须能读取同一文件；默认root:root0600可以继续用于服务，若部署用户无权限，适配器会在停服前拒绝。经确认后可由管理员将文件设为root拥有、仅专用部署组可读的0640，并仅授予现有应用/部署用户该组；不设0644，不在release中复制密钥。部署适配器只支持单行字面量`KEY=value`、必要引号和整行注释，不执行shell、不接受export、多行或环境展开；修改格式后需分别核对systemd与适配器加载结果，避免改变实际密码。
5. 核实没有其他写入者、已有可恢复备份及真实恢复演练，逐项填写`data_safety.prerequisites`证据后才启用。发布外层一次持有0600的`deploy.lock`，维护文件必须在uploads和备份之外，父目录允许部署用户创建、Nginx可检查。部署命令不再假定`/api/health`证明数据库正常。

迁移和首次账号初始化使用独立生产入口，开发命令保持拒绝production。下面是命令接口，必须在受控生产进程环境已加载后运行；不要在普通SSH环境直接执行，也不要`source`配置文件或把密码写在命令参数中：

```sh
# 默认只读，JSON列出已执行和待执行版本；无历史表时不建表。
python -m app.production_migrate \
  --expect-database personal_web_prod --expect-user personal_web_prod

# 受发布锁保护的显式迁移；集成流程另外继承自己的--lock-fd。
python -m app.production_migrate \
  --expect-database personal_web_prod --expect-user personal_web_prod \
  --execute --lock-file /opt/personal-web-deploy/deploy.lock

# 默认只读查看schema与是否已有账号；无默认账号，不自动初始化。
python -m app.production_admin_init \
  --expect-database personal_web_prod --expect-user personal_web_prod
```

首次管理员执行在以上命令追加`--execute --lock-file /opt/personal-web-deploy/deploy.lock`，必须真实TTY输入用户名及两次不回显密码；已有账号拒绝覆盖。可由管理员用`systemd-run --pty --wait --collect`建立临时服务，指定实际`User`、`WorkingDirectory`及同一`EnvironmentFile`后启动该命令，避免将凭据经过聊天或shell展开。生产命令只接受personal_web_prod同名库/账号并核实真实身份；只读调用不带执行锁参数。生产内容由独立production_content_init入口显式录入，不随启动自动运行，不复制开发库或开发账号；本轮已批准使用版本控制中的真实旅行助手内容。

备份工具由部署流程在所有写入者停止后调用，也可以在人工停写窗口内使用相同接口。`--writers-stopped`是操作方确认，工具本身不替操作者停止服务；独立备份后还须由外层恢复服务并验证，不能仅隐藏后台按钮：

```sh
# 使用已加载的受控环境，路径、PG版本和revision按实际替换。
python scripts/data_backup.py create \
  --uploads-dir /var/lib/personal-web/uploads \
  --backup-root /var/backups/personal-web \
  --replica-root /实际加密异机挂载目录/personal-web \
  --revision 完整40位旧应用提交SHA --pg-bin /实际PostgreSQL/bin \
  --lock-file /opt/personal-web-deploy/deploy.lock --execute --writers-stopped

# 只读校验整组归档和逐图片摘要；不代替恢复演练。
python scripts/data_backup.py verify --backup /绝对路径/备份组
```

备份组含`manifest.json`、`database.dump`、`uploads.tar`，记录旧应用提交、实际schema前缀、数据库/账号、内容摘要及逐文件摘要，不含明文配置。数据库dump自身包含业务数据及密码哈希/会话摘要，整组仍须按敏感数据保护。失败不清理旧有效组。本版不自动删除备份或安装定时任务；周期、日7份/周4份、恢复点和恢复时间尚待生产容量与演练确认。

`restore-test --backup PATH --uploads-dir NEW_PATH --pg-bin PATH --execute`仅接受`APP_ENV=test`、本机独立端口、`personal_web_test_*`空库/`personal_web_test`账号和全新私有图片目录。账号及空库须先在隔离实例创建，函数、类型等已有对象也会拒绝。实际恢复、表数据/序列、schema和图片引用均要通过才报告成功；验证失败保留测试目标供诊断，不自动删库。该入口不能覆盖生产库；真实生产恢复需要成套保存现场、停写、确认备份后数据损失并单独执行已审阅流程。

本地验证入口：`bash scripts/check.sh`及`bash scripts/test-db.sh`。部署测试需要真实PostgreSQL工具，`PW_REQUIRE_RECOVERY_TESTS=1`禁止静默跳过恢复用例。真实生产TLS、续期、Nginx重载、systemd配置加载和异机恢复未由本地构建证明，具体已验证范围见[验证记录](docs/validation-log.md)。

### IP 上线前手动配置（2026-10-25 实查后）

目标地址固定为`https://124.223.69.7`。以下保留完整手动步骤。2026-10-25后续用户已授权助手执行非HTTPS准备，完成项及证据见验证记录同日后续条目，不能再将本轮全部描述为只读。每一步失败即停止，不继续开启发布。无需重建生产库、重设数据库密码或改动开发库。

已落实：服务器端发布禁用、步骤3的目录/权限/UPLOAD_DIR及会话时长、步骤7的安全drop-in、步骤8的部署双文件和禁用保护。ADMIN_ALLOWED_ORIGINS保持未设置，未执行任何HTTPS/Nginx步骤。步骤8的health_url暂保留原http://127.0.0.1；步骤5确实建立8081后再改为http://127.0.0.1:8081。GitHub变量仍未确认。当前配置备份在`/etc/personal-web/nonhttps-prep-20261024T164402Z`；HTTPS修改前仍需另备份Nginx。完整步骤可作后续恢复/核对参考，已完成项不需盲目重做。

**1. 服务器：先暂停发布并保存当前配置。** GitHub仓库Settings → Secrets and variables → Actions → Variables中的`DEPLOY_ENABLED`设为false；本轮未读取到该变量实际值，服务器端开关是已确认开启的。以下只关闭服务器发布开关，不停止网站：

```sh
sudo install -d -o root -g root -m 0700 /etc/personal-web/prelaunch-20261025
sudo cp -an /etc/personal-web/app.env /etc/personal-web/prelaunch-20261025/app.env
sudo cp -an /etc/personal-web/deploy.json /etc/personal-web/prelaunch-20261025/deploy.json
sudo cp -an /etc/nginx/conf.d/personal-web.conf /etc/personal-web/prelaunch-20261025/personal-web.conf
sudo python3 - <<'PY'
import json, os
from pathlib import Path
p=Path('/etc/personal-web/deploy.json')
d=json.loads(p.read_text()); d['enabled']=False
q=p.with_name('deploy.json.pending')
q.write_text(json.dumps(d,indent=2)+'\n');q.chmod(0o644);os.replace(q,p)
print('Server deployment disabled; website unchanged.')
PY
flock -n /opt/personal-web-deploy/deploy.lock true
```

若最后命令失败，说明有发布持锁，先等待该流程结束并核对现状，不并发配置。

**2. Mac：上传已审阅的配置和两个部署文件。** 使用F工作目录，不从旧main/current取文件：

```sh
PW_F='/Users/rewind/rewind_Workspace/workwork/production/personal-web/.worktrees/admin-phase-f'
ssh ubuntu@124.223.69.7 'install -d -m 0700 /home/ubuntu/personal-web-f-ops'
scp "$PW_F/scripts/deploy.py" "$PW_F/scripts/deploy_runtime.py" \
  "$PW_F/ops/nginx-ip.conf.example" "$PW_F/ops/deploy-data.json.example" \
  "$PW_F/ops/systemd-override.conf.example" \
  ubuntu@124.223.69.7:/home/ubuntu/personal-web-f-ops/
```

该步骤仅上传运维文件，不包含新后台业务代码，也不切换current。

**3. 服务器：建立持久目录和受控配置读取权限。** 实际服务用户为ubuntu。专用组只允许该应用/部署用户加入：

```sh
sudo install -d -o ubuntu -g ubuntu -m 0755 /var/lib/personal-web
sudo install -d -o ubuntu -g ubuntu -m 0700 /var/lib/personal-web/uploads
sudo install -d -o ubuntu -g ubuntu -m 0700 /var/backups/personal-web
sudo groupadd --system --force personal-web-ops
sudo usermod -aG personal-web-ops ubuntu
sudo chown root:personal-web-ops /etc/personal-web/app.env
sudo chmod 0640 /etc/personal-web/app.env
sudo chmod 0600 /opt/personal-web-deploy/deploy.lock
sudo env TERM=xterm nano /etc/personal-web/app.env
```

保留原APP_ENV/DEBUG/DB_*及密码，只补充或修正以下三项。文件每个键仅一行，不使用export；不把密码发到聊天中：

```dotenv
UPLOAD_DIR=/var/lib/personal-web/uploads
ADMIN_ALLOWED_ORIGINS='["https://124.223.69.7"]'
ADMIN_SESSION_HOURS=8
```

编辑完成后退出SSH并重新登录，让ubuntu的新组生效。`sudo -u ubuntu test -r /etc/personal-web/app.env`应成功；不打印文件内容。这里使用`TERM=xterm`避免之前Ghostty终端类型导致nano失败。

**4. 服务器及云控制台：准备IP证书。** 腾讯云安全组须允许入站TCP80和443；保留SSH22，不开放数据库5432、后端8000或探针8081。当前UFW未启用，不为此盲目开启。服务器APT候选Certbot4.0不支持该IP方案，改用官方建议的Snap，并确认版本至少5.4：

```sh
sudo snap install certbot --classic
sudo /snap/bin/certbot --version
sudo install -d -o root -g root -m 0755 /var/www/personal-web-acme
sudo env TERM=xterm nano /etc/nginx/conf.d/personal-web.conf
```

在现有`server { ... }`内部加入以下location，保留所有原`/trip/`段；此时先不加入443或证书路径：

```nginx
location ^~ /.well-known/acme-challenge/ {
    root /var/www/personal-web-acme;
    default_type text/plain;
    try_files $uri =404;
}
```

```sh
sudo nginx -t && sudo systemctl reload nginx
sudo install -d -m 0755 /var/www/personal-web-acme/.well-known/acme-challenge
printf 'personal-web-acme-ok\n' | sudo tee /var/www/personal-web-acme/.well-known/acme-challenge/check >/dev/null
curl --fail http://124.223.69.7/.well-known/acme-challenge/check
```

最后一条应返回personal-web-acme-ok；还需从Mac执行同一curl确认公网可达。然后依次测试、正式申请，在终端按提示填写邮箱和确认条款：

```sh
sudo /snap/bin/certbot certonly --dry-run --webroot \
  --webroot-path /var/www/personal-web-acme \
  --ip-address 124.223.69.7 --preferred-profile shortlived --cert-name personal-web-ip
sudo /snap/bin/certbot certonly --webroot \
  --webroot-path /var/www/personal-web-acme \
  --ip-address 124.223.69.7 --preferred-profile shortlived --cert-name personal-web-ip
```

IP证书采用shortlived，约160小时有效；必须依赖自动续期。此方案用webroot，不能照搬`certbot --nginx -d IP`。参考[Let's Encrypt IP证书与Certbot官方步骤](https://letsencrypt.org/2026/03/11/shorter-certs-certbot)及[Certbot安装说明](https://eff-certbot.readthedocs.io/en/stable/install.html)。

**5. 服务器：证书存在后才安装完整IP配置。** 新文件按本次实际配置保留旅行助手路由与诊断保护，增加HTTPS、个人网站维护响应、静态404和仅本机8081探针。先查看diff，若原服务器配置在本次检查后又改过，应合并差异而非直接覆盖：

```sh
sudo test -s /etc/letsencrypt/live/personal-web-ip/fullchain.pem
sudo test -s /etc/letsencrypt/live/personal-web-ip/privkey.pem
sudo diff -u /etc/nginx/conf.d/personal-web.conf /home/ubuntu/personal-web-f-ops/nginx-ip.conf.example
# diff返回1代表存在差异，查看并确认后再执行下面两条。
sudo install -o root -g root -m 0644 /home/ubuntu/personal-web-f-ops/nginx-ip.conf.example /etc/nginx/conf.d/personal-web.conf
sudo nginx -t && sudo systemctl reload nginx
curl --fail https://124.223.69.7/api/health
curl --fail http://127.0.0.1:8081/api/health
curl --fail http://124.223.69.7/trip/health
curl --fail https://124.223.69.7/trip/health
```

必须不用`-k`就能HTTPS成功。新配置仅将个人网站HTTP请求跳转到HTTPS，保留现有旅行助手HTTP路由。若`nginx -t`失败，不reload；可用配置备份回退后重新检查：

```sh
sudo cp /etc/personal-web/prelaunch-20261025/personal-web.conf /etc/nginx/conf.d/personal-web.conf
sudo nginx -t && sudo systemctl reload nginx
```

以上回退只恢复本轮修改前Nginx配置，不恢复数据库或应用代码。

**6. 服务器：配置续期后重载。** Snap通常自带续期调度，仍须检查timer确实存在并启用，不能因安装成功就认为自动续期有效：

```sh
sudo install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
sudo tee /etc/letsencrypt/renewal-hooks/deploy/20-personal-web-nginx >/dev/null <<'SH'
#!/bin/sh
set -e
/usr/sbin/nginx -t
/usr/bin/systemctl reload nginx
SH
sudo chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/20-personal-web-nginx
sudo systemctl list-timers --all '*certbot*'
sudo /snap/bin/certbot renew --cert-name personal-web-ip --dry-run --run-deploy-hooks
```

必须确认存在下次运行时间且演练成功。若无活动续期timer，先解决调度再继续；6天IP证书不能依赖人工想起时续签。参考[Certbot续期说明](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates)。

**7. 服务器：合入systemd安全参数并重启现有应用。** 使用zz前缀确保晚于现有override.conf加载。该重启仍使用旧current，不迁移数据库：

```sh
sudo install -d -m 0755 /etc/systemd/system/fastapi-personal-web.service.d
sudo install -o root -g root -m 0644 \
  /home/ubuntu/personal-web-f-ops/systemd-override.conf.example \
  /etc/systemd/system/fastapi-personal-web.service.d/zz-production-safety.conf
sudo systemctl daemon-reload
sudo systemctl restart fastapi-personal-web
sudo systemctl is-active fastapi-personal-web
curl --fail https://124.223.69.7/api/health
```

**8. 服务器：更新部署入口，保持禁用。** 两个文件必须一起安装，保留原仓库、镜像和工具配置：

```sh
sudo install -o root -g root -m 0644 /home/ubuntu/personal-web-f-ops/deploy.py /usr/local/lib/personal-web/deploy.py
sudo install -o root -g root -m 0644 /home/ubuntu/personal-web-f-ops/deploy_runtime.py /usr/local/lib/personal-web/deploy_runtime.py
sudo python3 - <<'PY'
import json, os
from pathlib import Path
p=Path('/etc/personal-web/deploy.json');d=json.loads(p.read_text())
t=json.loads(Path('/home/ubuntu/personal-web-f-ops/deploy-data.json.example').read_text())
d.update(enabled=False,health_url=t['health_url'],health_host=t['health_host'],data_safety=t['data_safety'])
q=p.with_name('deploy.json.pending');q.write_text(json.dumps(d,indent=2)+'\n')
q.chmod(0o644);os.replace(q,p)
print('Installed data-safety configuration; deployment remains disabled.')
PY
```

此时`replica_root`为空、`data_safety.enabled=false`、所有prerequisites为false是正确的准备状态。不要为让命令通过而全部改true。

**9. 停止点：异机备份、恢复演练及新版本发布另行落实。** 未发现专用异机备份挂载，也未得到实际目的地。助手已新增当前无业务表生产库的同机基线备份，并在独立PG18.6临时实例恢复通过；后续已在Mac保存单次AES-256加密副本并从解密内容恢复通过；持续备份及服务器可用的异机挂载仍未配置，因此不能填写虚构的挂载凭据/命令。需要一个实际的加密异机存储或挂载方案；同机另一目录及旧first-deploy备份都不能替代。确定后先验证挂载，再创建子目录，避免挂载失效时退回系统盘：

```sh
# 仅在真实异机存储已经挂载到该路径后使用。
mountpoint -q /mnt/personal-web-backup && \
  sudo install -d -o ubuntu -g ubuntu -m 0700 /mnt/personal-web-backup/personal-web
```

随后将`replica_root`填为真实私有目录，并完成成套备份及隔离恢复演练，确认容量/耗时、旧schema兼容和全部写入者均受控，才逐项确认prerequisites。2026-10-25生产已独立完成001—003迁移，现有12张表和10项默认工具，尚无管理员/项目/资料/图片/访问数据。迁移工具暂存于`/home/ubuntu/personal-web-migrations/ad51bab`，当前current仍是旧f01d1fe，不要对旧current运行新模块。后续发布须验证目标release与现有schema校验和，再按保护流程处理任何新增迁移后才切换；生产管理员由用户TTY初始化，网站资料和旅行助手内容还须明确录入方案。开发初始化命令仍不能用于生产，不复制开发库/账号/会话/统计。

001—003及迁移后Mac快照恢复已通过；持续备份、新代码CI、生产内容及发布材料全部准备好后，才按单独发布授权打开服务器和GitHub开关。步骤1—8只是服务器配套准备，不代表生产上线或任务8验收完成。

### Mac 加密备份的读取

2026-10-25生产001—003迁移完成后，最新恢复点已更新为迁移后快照，包含12张表和10项默认工具配置。它仍无管理员、项目、资料、图片或访问记录；以后真实内容有变化时需另取新备份，不能把当前快照当作长期最新恢复点。原空库基线、迁移前及迁移后副本均保留，按各自回执区分，不能混用。

最新迁移后映像位于`/Users/rewind/rewind_Workspace/workwork/production/.personal-web-data/production/backups/postmigration-2026-10-25T072524267894Z-f01d1fe704f9-7f29ea1195d3.dmg`，配对口令文件位于`/Users/rewind/rewind_Workspace/workwork/production/.personal-web-data/production/keys/postmigration-2026-10-25T072524267894Z-f01d1fe704f9-7f29ea1195d3.key`。文件及回执均在Git外，目录0700、文件0600；口令文件不要放进映像或提交到Git。它是解密口令文件，不是证书私钥。

在Mac终端只读打开，无需显示或粘贴口令：

```sh
PW_BACKUP='/Users/rewind/rewind_Workspace/workwork/production/.personal-web-data/production/backups/postmigration-2026-10-25T072524267894Z-f01d1fe704f9-7f29ea1195d3.dmg'
PW_KEY='/Users/rewind/rewind_Workspace/workwork/production/.personal-web-data/production/keys/postmigration-2026-10-25T072524267894Z-f01d1fe704f9-7f29ea1195d3.key'
PW_MOUNT="$(mktemp -d /private/tmp/pw-backup-read-XXXXXX)"
hdiutil attach -readonly -nobrowse -stdinpass -mountpoint "$PW_MOUNT" "$PW_BACKUP" < "$PW_KEY"
ls -l "$PW_MOUNT"
# 查看/复制所需文件后，卸载并移除本次空挂载目录。
hdiutil detach "$PW_MOUNT"
rmdir "$PW_MOUNT"
```

迁移前/后的标准备份组含database.dump、uploads.tar、manifest.json；最早空库基线另用baseline-manifest.json，须按对应格式识别。迁移后快照已实际从Mac解密文件在独立PG18.6中恢复，并验证schema/数据摘要、12张表、10项工具及图片清单。恢复必须使用独立目标和兼容PG18.6工具，不向生产/开发库直接试恢复。摘要、源代码/版本及演练证据集中见[验证记录](docs/validation-log.md)同日条目和Git外回执；一次性Mac副本不等于已配置自动异机复制。

## 文档维护

文档维护与计划归档按原项目父级 `production/AGENTS.md` 的统一规则执行。
