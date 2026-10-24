# 验证记录

本文件只记录有日期、范围和边界的证据，不维护需求或任务进度。以下为当时的验证结果，不代表当前线上版本；源码与测试为实现依据，运行方式见 [README](../README.md)，未收尾事项见[部署归档](archive/2026-10-21-auto-deployment-plan.md)。

## 2026-10-13：框架与后端骰子

- macOS、Python 3.13.7、Node 22.22.1、npm 10.9.4 下依赖安装、锁文件生成与前端构建通过；本机 8010 的健康/个人信息和 5180 的页面/API 代理均返回 200。旧 Python 3.7 不可用，首次安装改用显式 Python 3.13 路径。
- 临时后端的 100 次掷骰请求均为 1～6 整数并覆盖六种点数；GET 返回 405，个人信息接口正常。样本不证明随机分布均匀。当时浏览器会话失败，初版渲染/点击和人工接受未确认，未部署。

## 2026-10-20：项目展示与详情

- 项目列表、实际旅行助手首页截图、完整详情和源码入口构建通过。约 493px 浏览器验证详情打开、滚动、Esc 关闭及焦点恢复；桌面侧栏骰子点击成功。截图来自本机 5173 的真实需求填写页（1280×720），未生成行程或调用模型；卡片/详情完整比例展示。
- 首次 `/trip/` 虽返回 200，HTML 标题和资源实际属于个人网站，不能作为旅行助手部署证据；用户随后要求暂缓接入，演示恢复禁用。此为历史状态，后续结果见下一条。
- 未做真实手机或个人信息失败交互专项验收；当时未部署个人网站，Git 交付结果以提交/PR 历史为准。

## 2026-10-21：旅行助手入口与本地隔离

- 重新启用 `/trip/` 后，公网及当时本机代理的标题为旅行助手，JS/CSS 使用 `/trip/` 前缀并返回 200，`/trip/health` 健康。浏览器确认入口可点击且新标签页属性保留，目标页面通过 HTTP 核对，不计为完整浏览器跳转验收。
- 随后移除生产代理：开发/本地构建默认 5173，生产使用 `/trip/`。两种构建及临时 5199/4199 经本机 8010 的代理检查通过；生产包不含本机 5173，本地包不含生产 IP。运行后替换代理未生效的首次断言失败，改用实际本地后端后通过。
- 未提交规划请求或验证旅行助手持久化；个人网站入口健康不代表旅行规划业务验收。

## 2026-10-21：本地检查与 GitHub CI

- 基线远端 `2e63c12`，服务器 `fb6fc8f` 的额外差异仅旧部署脚本。补齐 Gunicorn 26.2.0/httpx2，统一检查通过；无依赖目录的临时副本在 Python 3.14.7 上重新安装和构建通过，不等同于生产 Python 3.14.4 验收。
- 临时副本故意改错健康响应后，`test_health` 失败、脚本返回 1 并停止后续前端步骤；原仓库业务代码未注入故障。Gunicorn 配置检查不代表真实多进程启动。
- [PR #3](https://github.com/SSpiderLily/personal-web/pull/3) 的 `6375eaf` 在 [运行 39548296023](https://github.com/SSpiderLily/personal-web/actions/runs/39548296023) 上通过 Ubuntu 24.04 / Python 3.13、3.14 检查。main `6729e9f` 的 [运行 39548672670](https://github.com/SSpiderLily/personal-web/actions/runs/39548672670) 也通过；当时仅 check，没有部署作业，不能称已启用自动发布或合并保护。

## 2026-10-21：部署准备与离线验证

- 首次只读核对时，旧服务健康，但 Node 20.20.2 不满足前端要求、非交互 PATH 未找到 uv；旧脚本没有依赖同步、健康检查、回退或发布锁。旧 Nginx/systemd 仍指向旧目录，`/trip/` 独立。ubuntu 具有广泛 sudo 权限；防火墙/Secrets 等检查均是当时快照，不作为当前状态。
- 15 项离线部署测试通过，覆盖切换、构建失败、健康/重启/中断回退、回退失败、过期提交、构建时 main 前进、重复发布、锁、初始化/开关、版本/资源、依赖哈希和目录权限。系统命令、网络及构建为模拟；链接和锁使用真实临时目录。
- 首轮 macOS `/var` 与 `/private/var` 路径别名断言失败，规范化后通过；补充 release 的 0755 遍历权限并重跑通过。统一检查、YAML 与内嵌 shell 语法通过；未安装 actionlint，语法检查不代表真实部署验收。
- [PR #4](https://github.com/SSpiderLily/personal-web/pull/4) 的 `56a2b6436f9c13401a84a08d66c71bc899ba0197` 在 [运行 39550185995](https://github.com/SSpiderLily/personal-web/actions/runs/39550185995) 通过两版 Python。最终 `ba2f2ed` 的四项检查通过后合并为 `86924b65eec9978fdb8c90f93c7d39d5b7e26367`，远程/本地任务分支当时已清理。此时正式工作流仍只检查，部署草稿尚未启用。

## 2026-10-21：首次手动发布与 SSH 拉取

- 用户授权复用 ubuntu；发布 `936d8b26ad0f95f6bd49e9e61d029bc92a6d65ba`，旧代码、Git 与服务配置保留备份，Node/uv 独立安装并核对 Node 官方哈希。
- GitHub HTTPS fetch 遇到 GnuTLS `(-110)`，首次改传本机 Git bundle 并核对 SHA；依赖下载阻塞改为锁定导出加腾讯 HTTPS 镜像、强制包哈希安装。构建、Gunicorn 配置、临时健康检查和 `nginx -t` 通过后才切换。
- 公网首页、API、版本标记、JS/CSS、`/trip/` 与其健康接口均 200，版本标记匹配 SHA，旅行助手 index 哈希不变。自动发布当时未开启；旧站点恢复脚本仅语法检查通过，没有执行真实回退。
- 后续经用户授权复用服务器现有 GitHub SSH 密钥，严格主机核对下 ls-remote 和 fetch 成功，配置改用 SSH；此验证仅证明服务器→GitHub，不证明 Actions→服务器。

## 2026-10-21：Actions 发布与自动开关

- [PR #6](https://github.com/SSpiderLily/personal-web/pull/6) 合并为 `8bccaba03c819338bee4712081993a912f5e42c9`。[手动运行 39553907949](https://github.com/SSpiderLily/personal-web/actions/runs/39553907949) 的 Python 3.13/3.14 检查和 deploy 均成功；runner 登录服务器、服务器 SSH 拉取、构建、切换、重启及版本检查均已实际执行。
- 服务器 current/REVISION 与公网版本标记均匹配该完整 SHA；首页、API、JS/CSS、`/trip/` 及其健康接口均 200。没有进行真实故障回退或完整旅行规划业务验收。
- 当时已读回确认仓库 `DEPLOY_ENABLED=true`、服务器 `enabled=true`、production 仅 main，部署变量和 Secrets 已配置。此处是开关启用证据；后续首次 push main 自动发布与用户页面变化验收仍需核对，不能从手动成功推断。

## 2026-10-21：本地白屏恢复

5180 的旧 Vite 进程引用不存在的 Vue 预构建缓存，依赖请求 504。停止旧进程并以 `npm run dev -- --force` 重建后，浏览器正常显示首页、项目与骰子，真实点数请求和 API 代理正常；未修改业务代码或发布。

## 2026-10-21：悬浮 3D 骰子与九宫格

- 基线 `a74f5c98668d826282c0757a0cbcbe545eb29fdf`。15 项部署、5 项后端、12 项前端测试以及 Gunicorn 配置和构建通过。审查发现异步 3D 初始化覆盖点数、WebGL 丢失/恢复切换异常两项 P2，均先由真实 Vue 组件测试复现，再修复；另覆盖重复点击、卸载清理、备用显示和减少动态。
- 浏览器在 1280px 与 493px 下验证九宫格三列且无水平溢出、3D 初始化、真实后端掷骰、详情开关、本地演示仍为 5173，控制台无错误。用户调整位置后，493px 下骰子按钮/提示右缘 48px，项目卡片左缘 56px；受影响测试与构建再次通过。
- WebGL 切换使用组件模拟通知，没有真实 GPU 故障注入或真实手机验收。用户当时授权检查后提交、推送、合并；实际 PR/合并/部署以 GitHub 历史为准，不把授权本身当作完成。

## 2026-10-23：后台规划与文档整理

- 正式代码静态核对基线为本地 main `bbca380`；后台需求、PostgreSQL 与骰子展示开关已确认，交互草图方向被接受。草图使用内存演示，不能证明正式登录、上传、存储或统计已实现；任务与范围只维护在[后台计划](admin-management-plan.md)。
- 本轮合并后台重复文档、精简 README 与旧部署记录、更新索引并检查引用和文档差异；按用户要求归档已实现的部署阶段，并保留未核实验收事项。未运行应用、构建或业务测试，未连接生产环境、安装数据库、提交、推送或发布。

## 2026-10-23：本地 PostgreSQL 安装检查

- `/Library/PostgreSQL/17/bin/psql --version` 返回 17.11；安装目录包含独立数据目录。`/Library/LaunchDaemons/postgresql-17.plist` 设置 `RunAtLoad=true`，由系统用户 postgres 启动，未验证重启电脑后的实际行为。当前助手命令行 PATH 未找到 psql，可使用完整路径。
- 沙箱内 TCP 检查被系统拒绝；在授权的沙箱外只读检查中，`pg_isready -h 127.0.0.1 -p 5432` 返回 accepting connections。助手首次使用 postgres 账号连接返回 no password supplied。随后用户在本机终端输入密码执行 `SELECT version();`，提供的输出确认服务端为 PostgreSQL 17.11、aarch64，管理员密码认证和查询成功；助手未读取或索取密码。现有数据库/角色及项目账号的读写权限仍未验证。
- 静态检查后端依赖与源码，当前未声明 PostgreSQL 驱动、数据库连接或迁移配置。本轮未创建账号或数据库、未修改数据库配置或业务代码、未连接生产环境、未提交、推送或发布；项目现有未提交改动保留。

## 2026-10-23：数据库部署位置调整

- 用户明确改为在云服务器安装数据库并创建开发库和生产库，当前安排见[后台计划](admin-management-plan.md)。本轮核对 PostgreSQL 官方 Ubuntu 软件源、建库/授权和 SSH 隧道文档并提供操作指导；没有登录云服务器，云端系统、资源、现有实例、安装、数据库创建、权限、隧道和备份均未验证。未修改数据库或业务代码，未提交、推送或发布。

## 2026-10-23：云端 PGDG 下载失败

- 用户提供的 apt 输出显示使用 resolute-pgdg/main amd64，postgresql-17、postgresql-client-17 和 libpq5 下载失败；IPv6 报 Network is unreachable，IPv4 连接 146.75.115.52:443 超时。证据指向软件源下载链路问题，具体网络原因及安装后的服务状态未确认，不能据此认定仅为 IPv6 问题。
- 助手侧对 `https://repo.huaweicloud.com/postgresql/repos/apt/dists/resolute-pgdg/InRelease` 执行限时 IPv4 HEAD 请求返回 HTTP 200；不代表云服务器可达、镜像包已同步或安装成功。提供先测连通性、备份并仅替换 PGDG 源地址、保留签名校验再重试的步骤，执行结果待用户反馈。未连接或修改云服务器。

- 后续用户执行停用 pgdg.sources/pgdg.list 的指导，提供的 `apt update` 输出仅有腾讯 Ubuntu resolute 系列源和 NodeSource，均为 Hit，本次无下载错误；193 packages can be upgraded 仅为可升级提示。`pg_lsclusters` 只返回表头，未列出集群；未提供服务端包安装结果，不能确认已安装或运行。下一步安装 Ubuntu 源的 postgresql 包并重新检查；尚未建库或验证云端连接。

## 2026-10-23：云端 PostgreSQL 服务安装成功

- 用户提供的 `pg_lsclusters` 输出为 `18 main 5432 online postgres`，数据目录 `/var/lib/postgresql/18/main`，日志 `/var/log/postgresql/postgresql-18-main.log`，证明云端 PostgreSQL 18 集群运行。未提供服务端具体小版本、密码登录、监听范围、项目账号/数据库或备份证据；相关项仍待验证。
- 下一步指导用户创建独立开发/生产账号与数据库并校验连接及跨库权限。本轮仅依据用户输出更新文档，未登录或修改云服务器、未接入后端、未提交、推送或发布。

## 2026-10-23：云端建库与账号登录反馈

- 用户明确反馈开发库、生产库均已创建且可以登录；本轮没有提供具体命令输出，按用户确认记录，不等同于助手独立复验。账号命名与权限设置未再次核对，跨库访问限制、读写与迁移仍待验证。
- 提供 Mac 通过本机 127.0.0.1:15432 SSH 转发至云服务器 127.0.0.1:5432 的连接步骤；隧道和本地查询结果待用户反馈。未修改云服务器、数据库或业务代码，未提交、推送或发布。

## 2026-10-23：统一配置模块与本地环境配置

- 用户授权采用统一 Settings、本地 .env 与服务器外部 app.env 的简化方案；本次仅实现本地配置和模块，生产提供操作步骤。本轮在 codex/centralized-settings 分支保留此前未提交文档改动，未登录生产服务器，未提交、推送或发布。
- 新增 DEBUG 行为测试先得到 False，复现原代码不读取配置，再实现集中读取、固定文件路径、环境变量优先、生产/test 忽略本地文件、生产参数与 debug 校验，以及错误文本隐藏输入值。增加 pydantic-settings 2.16.1 和 python-dotenv 1.2.4，声明及锁文件同步，原依赖版本未变。
- Python 3.13.7 / Node 22.22.1 执行 bash scripts/check.sh 成功：15 项离线部署保护、16 项后端、12 项前端测试，Gunicorn 配置检查和前端构建全部通过。本轮未额外验证 Python 3.14 或真实浏览器交互。
- 从临时工作目录读取实际配置，确认 development / 127.0.0.1 / 15432 / personal_web_dev / debug=True；密码只报告是否已填，结果为否，不打印原文。实际 .env 权限 0600，git check-ignore 确认被忽略；两份模板无真实凭据。
- 独立审查未发现需修复的行为缺陷，额外确认生产异常的 str/repr 不含虚构密码，README 首次 systemd 操作与现有发布流程相容。README 已记录本地用法和生产首次步骤，INDEX 用途说明同步。
- 未安装数据库驱动、连接真实数据库或执行迁移。云端 SSH 隧道、跨库权限、真实 systemd 配置加载及备份仍未验证；配置测试不代表数据库接入或生产验收通过。

## 2026-10-23：本地经 SSH 隧道验证云端开发库

- 用户已在本机填写开发密码并授权验证。助手通过 get_settings() 读取配置，只核对 development / 127.0.0.1:15432 / personal_web_dev 数据库及账号；密码不进入命令或输出，使用 0600 临时 pgpass 文件并在测试后自动删除。
- 首次连接返回 Connection refused，尚未进入数据库认证；本机 15432 没有监听。随后以已记录的主机 124.223.69.7 和现有 SSH 身份，在严格已知主机校验下建立临时 SSH 隧道，仅转发本机 15432 至服务器 127.0.0.1:5432，没有执行远程命令或修改服务器配置。
- psql 强制 default_transaction_read_only=on，查询返回 PostgreSQL 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1)、数据库和账号 personal_web_dev、服务端地址 127.0.0.1/32、端口 5432、read_only=on；退出码 0。public schema CREATE 权限为 true，生产库 CONNECT 权限为 false；这仅验证权限元数据，未实际写入或连接生产库。
- 助手测试完成后关闭了当次临时 SSH 会话。当时需要手动保持隧道；后续已由本地自动启动入口替代，现行操作见 README。15432 为 Mac 入口，不是云防火墙端口。用户截图显示云防火墙已允许全部 IPv4 访问 5432，本轮未修改该规则，也未据此推断 PostgreSQL 的实际公网监听状态。
- README 补充端口关系，计划同步已验证项。仍未接入后端数据库驱动或迁移，未验证实际读写、生产账号反向隔离、生产应用加载配置或备份；未提交、推送或发布。

## 2026-10-23：本地启动自动建立 SSH 隧道

- 用户要求本地启动时自动建立隧道，省去单独 SSH 终端。新增 scripts/dev.sh 与仅显式调用的 app.dev，合并 SSH 与 Uvicorn reload；前端仍单独启动，生产入口不运行网络逻辑。Settings 集中声明 DEV_SSH_HOST/USER/PORT、DEV_DB_REMOTE_PORT 和 DEV_BACKEND_PORT，开发模板与现有本地 .env 的缺失非敏感项同步，原密码不显示且保持不变，.env 仍为 0600 且被 Git 忽略。
- 实际运行 bash scripts/dev.sh：自动 SSH 隧道就绪，8010 的 /api/health 返回 200；从本地配置读取凭据，经 15432 用 psql 强制只读查询，返回 PostgreSQL 18.6、personal_web_dev 数据库/账号和服务端 5432，退出码 0。临时密码文件 0600 且自动删除，密码不进入参数或输出。重复启动返回端口占用错误和退出码 1，原后端仍健康；Ctrl+C 后退出码 0，15432 和 8010 均释放。
- 独立审查发现两项生命周期问题，并均先由失败测试复现后修复：真实 ssh -G 展示继承后台化设置，现强制前台并禁用共享 master；真实受控父/子进程复现父进程退出后仍有 worker 占端口，现等待整个自有进程组并在宽限期后强制清理。进程释放测试短轮询端口，避免把 SIGKILL 的调度延迟误判为残留。审查复核通过；修复后再次实际启动与停止正常。
- 最终 bash scripts/check.sh 通过：15 项部署保护、26 项后端、12 项前端测试，以及 Gunicorn 检查和前端构建。新增用例不访问云端，使用模拟子进程、临时 SSH 配置或受控本地进程；实际云端验证单独记录于上一条。未额外验证 Python 3.14 和真实浏览器交互。
- README 默认后端启动已改为自动入口，INDEX 的用途说明同步；本次计划子步骤完成。没有新增数据库驱动或迁移，没有写数据库、修改生产服务器配置、提交、推送或发布。测试启动的服务和隧道均已停止。

## 2026-10-23：云端开发库初始表结构

- 用户授权按已审阅草案在开发库建表。经现有 SSH 身份、严格主机核验和临时本地转发，只连接 personal_web_dev 数据库及同名账号，服务端为 127.0.0.1:5432、PostgreSQL 18.6；建表前 public 无业务对象，账号有 CREATE 权限。本轮不连接生产库、不修改服务器配置。
- 新增 backend/migrations/001_admin_schema.sql 与 apply_dev.sql，单事务创建十张业务表、相关主键/外键/检查/索引，另建 schema_migrations 记录版本。实际迁移版本 001_admin_schema，SQL SHA-256 为 b47c9141e0b42926660dc7002230910a1b7254e76a516f824f9650c4672b6d1c，记录时间为 2026-10-23 23:22:43（上海时间）。详情块和截图的位置唯一约束可延迟，默认立即检查。
- 先运行断言确认缺表失败；随后试建并回滚成功，确认仍为零表；正式建表后再运行 migrations/tests/verify_dev.sql，通过单管理员/资料、令牌摘要长度与过期、文件大小及引用保护、不完整草稿、项目状态、块字段互斥、位置唯一及延迟交换、截图重复、JSON 数组、工具位置、每日/跨日人数去重及级联约束检查。测试使用显式项目/块/截图 ID，不消耗其身份序列；所有测试记录回滚。最终只读核对恰有十张空业务表和一张版本表、一个版本记录。
- 相同版本及校验和重复执行成功跳过；错误、缺失、非法校验和均拒绝，退出码 3。验证时发现 psql 17 忽略 \quit 的退出码参数，已改为 ON_ERROR_STOP 下抛出 SQL 异常并复验。初次文件删除验证因 PostgreSQL RESTRICT 使用独立错误类别而中断，事务自动回滚；补充该错误类别后通过。断言片段增加执行入口检查，避免单独误运行提交测试记录。
- 现有后端 26 项 unittest 全部通过；首次在沙箱中因回环端口绑定限制导致 test_stop_process_cleans_worker_after_parent_already_exited 报 PermissionError，放开该环境限制后全套通过。SQL 变更未触及应用、前端或部署入口，本轮未重复前端构建、真实浏览器或生产验收。
- 迁移、README 用法、后台计划与工作区 INDEX 已同步。凭据仅由既有配置读取，临时 0600 密码文件自动删除，SSH 会话已停止；未创建真实管理员或初始化网站内容。应用驱动/连接、业务接口、生产配置、反向账号隔离、独立测试实例与备份恢复仍未完成。未提交、推送或发布。


## 2026-10-24：阶段 A Git 基线整理

- fetch origin 后，本地准备分支与 origin/main 在整理前均为 bbca380，无新增远程提交。已有准备成果保存为本地提交 04c2796；main 未移动。阶段 A 集成及任务分支安排见后台计划，分支和工作目录状态以 git branch / git worktree list 为准。
- 本轮 bash scripts/check.sh 全部通过：15 项离线部署保护、26 项后端、12 项前端测试，Gunicorn 配置检查及前端构建。未复验 Python 3.14、真实浏览器、云端数据库或生产；已有建表证据沿用上一条记录。
- git diff --check 通过；本地 backend/.env 被 Git 忽略，两份模板密码为空。未将真实本地配置纳入提交。仅本地提交及建分支，未创建工作目录、派发开发、推送、合并 main 或发布。


## 2026-10-24：生产启动与数据库隔离只读核验

- 用户授权检查生产启动与账号隔离。通过既有 SSH 身份及严格主机核验执行只读检查，数据库查询使用 BEGIN READ ONLY / ROLLBACK；未输出密码，未修改服务器或数据库，未重启、提交或推送。
- systemd 服务 active/running，使用 ubuntu 和 Gunicorn，不运行 app.dev/dev.sh 或 reload，无 drop-in。主进程及两个 worker 均在 release bbca380109a96111e57fc8cfacee791492302cd4 下运行，健康接口返回 200。
- /etc/personal-web/app.env 不存在；三个运行进程均未设置 APP_ENV、DEBUG、DB_HOST/PORT/NAME/USER 或 DB_PASSWORD。当前 release 无 settings.py，main.py 不读取 get_settings，且无 backend/.env。新的生产配置尚未接入；旧版健康不能替代新版配置验收。后续按 README 首次接入步骤操作，本轮未实施。
- PostgreSQL 18.6，listen_addresses=localhost，port=5432；HBA TCP 规则仅回环地址，使用 scram-sha-256，无解析错误；本轮未核验云防火墙。
- 两个同名账号分别拥有开发库和生产库。各自对本库 CONNECT/CREATE/TEMP 为 true，对另一库均为 false；均非超级用户，无建库、建角色、复制或绕过行级安全权限，无角色成员关系。双向账号连接权限已隔离。
- public schema 的 CREATE 仅本库账号具有；另一账号有 PUBLIC 授予的 USAGE，但没有数据库 CONNECT，不能据此进入另一库。本轮通过管理员只读查询有效权限，未读取生产密码或使用两组密码实际登录，未验证应用数据库连接、独立测试环境或备份恢复。


## 2026-10-24：合并前检查

本轮重新执行 bash scripts/check.sh 全部通过：15 项部署保护、26 项后端、12 项前端测试、Gunicorn 配置检查与前端构建。远程 main 仍为 bbca380；服务器环境配置由用户在合并后手动完成，尚未验收。合并与发布状态另凭实际结果更新。


## 2026-10-24：准备基线合并与自动部署完成

- 独立合并前审查未发现阻塞问题，确认默认环境下导入应用不会启动 SSH 或访问数据库。PR #9：https://github.com/SSpiderLily/personal-web/pull/9；head e259435199e790fff1442e16fe42b07bccdf87ea，Python 3.13/3.14 的分支及 PR 检查均成功后，通过 merge 合并为 f01d1fe704f92dde35431041f89f67be6703c8aa。
- main 运行 https://github.com/SSpiderLily/personal-web/actions/runs/39989960782 的 Python 3.13/3.14 检查及 deploy 均成功。本地 main 已快进同步。原本地任务分支保留；启动阶段 A 前在各独立目录合入最新 main，不丢弃已有工作。
- SSH 只读核对 current/REVISION 为上述合并 SHA，systemd active，127.0.0.1:8000/api/health 正常。公网 /__release.txt 匹配 SHA；首页、/api/health、页面引用 JS/CSS 和 /trip/ 均 200，未执行真实旅行规划或浏览器交互验收。
- 最初以 localhost Host 请求 Nginx /__release.txt 得到 404，改用实际站点地址后返回 200；探测 /trip/api/health 返回 404，该路径未确认为有效健康路由，不据此判断旅行助手服务异常，也不声称旅行助手 API 健康验收通过。
- 用户选择合并后自行接入生产环境配置；本轮仅自动发布代码及只读检查，助手未创建 app.env、修改 systemd 或数据库权限。生产配置接入与应用数据库连接仍未验收。本节为部署后本地证据记录，不再次推送触发发布。


## 2026-10-24：用户填写配置后的生产复验

- 用户要求复验；通过 SSH 仅只读查询，未修改配置、重启或操作数据库数据。app.env 已存在，root 所有、0600；文件中 APP_ENV=production、DEBUG=false、127.0.0.1:5432、库/账号 personal_web_prod，密码非空。密码未输出或传回本机。
- systemd active/running，但 DropInPaths 为空；主进程 990268 与两个 worker 的 APP_ENV、DEBUG、DB 参数及密码均未设置。使用运行进程环境执行当前 release 的 get_settings() 得到 development、15432、personal_web_dev、debug=false。生产配置文件尚未加载进服务；未将健康接口正常误报为配置验收通过。
- 将配置文件中的密码仅通过服务器子进程环境传给 psql，强制 default_transaction_read_only=on。实际 TCP 登录成功，返回 personal_web_prod 库及同名账号、127.0.0.1:5432、read_only=on；该账号对开发库 CONNECT=false。此结果证明文件凭据及数据库连接可用，不代表运行应用已接入数据库。
- 服务版本仍为 f01d1fe，健康接口正常。下一步由用户添加 systemd EnvironmentFile、daemon-reload 并重启服务后复验。本轮只同步本地计划及本记录，未提交或推送。


## 2026-10-24：生产配置加载复验通过

- 用户完成 systemd 配置并重启后，助手再次通过 SSH 只读复验。服务 active/running，DropInPaths 指向 /etc/systemd/system/fastapi-personal-web.service.d/override.conf，EnvironmentFiles 为 /etc/personal-web/app.env (ignore_errors=no)。文件 root 所有、0600。
- 主进程 991733 及两个 worker 991738/991739 均实际加载 APP_ENV=production、DEBUG=false、DB_HOST=127.0.0.1、DB_PORT=5432、DB_NAME/DB_USER=personal_web_prod，密码已设置且三者一致。密码未输出。使用主进程环境运行当前版本的 Settings/应用导入验证，确认 app_env=production、Settings.debug=false、FastAPI.debug=false。
- 用实际运行进程中的数据库参数与凭据执行 psql 强制只读查询，连接成功；返回 personal_web_prod 库及账号、127.0.0.1:5432、read_only=on；生产库 CONNECT=true，开发库 CONNECT=false。此项为真实进程配置驱动的独立数据库登录，不代表尚未实现的应用数据库驱动已接入。
- 运行版本仍为 f01d1fe704f92dde35431041f89f67be6703c8aa，健康接口正常。生产配置文件到 systemd、运行进程及配置模块的加载链路验收通过；应用统一连接/事务和隔离测试环境仍待实现。本轮未修改服务器、数据库或重启服务；只更新本地文档，未提交或推送。


## 2026-10-24：阶段 A 三线并行实现与本地集成

- 用户授权同步任务分支、建立独立目录并并行执行 1、2A、8A。三条线从 66380d1 出发，分别位于 .worktrees/admin-a-db、admin-a-shell、admin-a-ops；依赖独立安装。基线统一检查通过（15 部署、26 后端、12 前端及构建）。原目录 backend/.env.example 的外部改动保留未提交，未纳入本轮成果。
- 数据库线 ad0d151 + 44dd5a4：psycopg 3.3.6 连接/原子事务、串行版本迁移及独立 PG 测试入口；初始 001 SQL 和原校验和未变，psql 初始入口保持兼容。没有业务种子、启动连接或自动迁移。production 迁移在连接前拒绝。
- 独立审查发现 PGHOSTADDR 隐式连接覆盖及逗号多主机测试目标两项 P2，均先复现再修复并复审通过；连接前拒绝受支持的非空 libpq 环境覆盖，不改全局环境。专项临时 PG17.11 仅独立 Unix socket，污染环境测试和目录清理核对通过，不清空共享开发库。
- 页面线 01d340b：/admin 独立组件和样式；仅 Vite DEV 可进入内存模拟会话，不接收/保存真实密码、不调用管理API。生产禁用模拟入口，URL参数与人工submit不能启用。真实登录、生产Nginx/HTTPS未因此完成。独立规格及质量审查通过。
- 页面浏览器证据：1440px桌面及390px窄屏登录/导航/退出/刷新无溢出；生产预览禁止模拟会话；公开详情焦点恢复和骰子点数4回归。公开资料和点数由本地浏览器拦截固定响应，未声称真实业务API或真实GPU性能验收；截图已查看，证据在本计划忽略工作区，工具输出未进入产品提交，QA服务已停止。
- 部署线 c96b49a + 89d7ced：仅在现有计划内提出持久化、HTTPS、成套备份恢复和迁移回退方案。审查发现备份/发布互斥及真实恢复停写顺序两项P2，修正后限定复审通过。建议与真实验收明确区分；未修改CI、部署脚本或服务器。
- root 使用新 connection() 经临时独占SSH隧道只读连接云端开发 PostgreSQL18.6，身份为 personal_web_dev，read_only=on，生产库CONNECT=false；001版本/校验和一致。只查询身份和迁移元数据，未执行迁移或写入；隧道已关闭，未启动服务。PG17专项与PG18只读冒烟范围分别记录，不推断生产应用已部署新驱动。
- 三线按数据库、页面、部署方案顺序普通merge到本地集成分支，无冲突。集成后 bash scripts/check.sh 通过：15项部署保护、后端40项中33通过/7明确跳过、前端15项通过、Gunicorn检查及生产构建通过；另跑 bash scripts/test-db.sh，14/14通过，包含被默认跳过的7项真实PG用例。不得将7项跳过计为默认检查已执行。当前验证Python3.13；本轮未推送CI或验证Python3.14，未部署/生产业务验收。

- 最终跨模块独立审查通过，未发现 P0/P1/P2 阻塞；发现 README 与计划两处字面换行影响标题显示（P3），已精确改为真实换行并检查标题、文档链接及差异。此后未改功能代码，不重复已通过的全套测试。三线本地交付及技术验证完成；8A建议参数待接受，真实登录2B与8B实施未开始。


## 2026-10-24：阶段 B 真实登录与后台框架

- 阶段 A 页面效果由用户接受后，阶段 B 在独立 `codex/admin-phase-b` 本地实现：终端初始化、Argon2密码哈希、数据库会话、登录/退出、会话恢复、受保护概览和后台导航。原公开接口契约保留，业务模块仍待接入。
- 最终代码运行 `bash scripts/check.sh`：部署保护15/15；后端共60项，其中44通过、16项数据库专项按预期跳过；前端25/25；Gunicorn配置与生产前端构建通过。随后 `bash scripts/test-db.sh` 在自建 PostgreSQL 17.11 临时集群完成数据库14/14、管理20/20，含真实PTY交互输入、不回显密码、账号入库及登录验证。临时集群只用私有Unix socket，运行后清理，未对共享开发库运行破坏性测试。
- 独立审查和联合验收发现并修复：匿名页面恢复焦点清空密码（P2）、初始化允许登录接口不接受的字符（P2）、真实终端 `r+` 打开方式要求可seek而导致初始化失败（P1）。覆盖测试均先复现失败再转绿；限定复查确认三项已解决，无新增阻塞问题。初始001迁移SHA-256仍为 `b47c9141e0b42926660dc7002230910a1b7254e76a516f824f9650c4672b6d1c`。
- 浏览器对临时本地测试库验证错误密码提示及密码清空、正确登录、刷新恢复会话、模块切换、退出后管理接口401、数据库会话过期后返回登录页、网络失败提示及恢复重试、焦点恢复保留匿名输入。1280px桌面及390px窄屏无横向溢出，布局截图核对通过。Cookie为HttpOnly、SameSite=Strict、Path=/api/admin；本地HTTP不设Secure，production的Secure/HTTPS由专项测试验证。localStorage/sessionStorage均为空，脚本不能读取会话Cookie。
- 浏览器回归公开首页、项目详情开关及真实骰子请求，后端记录 `/api/profile` 和 `/api/dice/roll` 均200。预期错误请求产生401/网络错误控制台项；另有既有favicon.ico 404，未据此误报控制台零错误。
- 验收临时库已清理。5182预览切换到阶段 B，8010后端经既有隧道运行；只读事务确认 `personal_web_dev` 数据库/同名账号、001迁移存在、管理员表为空。随后代理健康及匿名会话接口均200。未创建云端管理员、未提交真实凭据；真实开发账号由用户在终端初始化后另行验收。
- README、唯一后台计划和工作区INDEX导航已同步。代码及文档仅本地提交，未推送、未合并main、未部署或检查生产反向代理。真实生产HTTPS、双worker登录专项与生产账号初始化留给8B；本地测试不代表生产开放完成。
