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


## 2026-10-24：阶段 B 用户验收与收尾复核

- 用户确认已在终端初始化真实开发管理员，且可在后台正常登录。这是用户对个人凭据登录的验收，补足上一条记录的待办；助手未索取或读取密码。
- 本轮沿用开发隧道强制只读查询：环境development，数据库和账号均为personal_web_dev，管理员数量1、未撤销且未到期会话数量1；开发账号对personal_web_prod的CONNECT权限仍为false。001迁移及SHA-256与既有记录一致。未读取账号名称、密码哈希、会话令牌，未写开发库、未访问生产。
- 再跑 `bash scripts/test-db.sh`：临时独立PG数据库14/14、管理20/20通过；`npm --prefix frontend test`：25/25通过。已有代码自上次统一检查、构建及审查后未变，本次不重复构建或宣称新增生产测试。实际5182代理健康200；不带Cookie的管理概览401。
- 复核范围覆盖初始化不可覆盖、会话轮换/撤销/过期与独立应用实例读取、同源/CSRF及生产默认关闭、前端恢复/退出/故障状态。阶段B范围内未发现阻塞遗漏，生产HTTPS、首次生产账号及双worker真实部署验收仍归8B。
- 文档收尾修正两处过期状态：登录有效期/初始化仍标待定、隔离测试实例仍标未落实；任务2更新为已验收，整体完成数2/8。现有计划补入阶段C三线分工、拟用文件、共用入口归属和参数/接口前置条件。发现上传multipart与现有JSON写保护、公开统计请求与会话Cookie路径两项下游交接点，作为阶段C/7B开工前契约处理，不冒充已实现。
- Git准备仅本地：阶段B验收记录提交后，以该提交建立阶段C集成与三条任务分支；独立工作目录、依赖安装和业务代码留到正式执行。main/origin-main的本地引用仍为f01d1fe，未fetch、未推送或部署；原目录 `.env.example` 外部改动保留。


## 2026-10-24：阶段 C 三线并行实现与本地技术验收

- 用户授权固定接口/参数、建立三线独立目录并并行实施。集成目录 `.worktrees/admin-phase-c`，三线为admin-c-uploads/tools/stats；均从冻结合同ddd57e1出发，依赖与临时测试数据独立，没有复制开发凭据给各线。原目录 `.env.example` 外部改动保持，未纳入成果。共用入口/文档由集成方串行修改。
- 工具线6d636bf+0f16602：完整10项工具注册表、原子保存、公开读取、管理表单和稳定key图标；002仅补缺失默认记录，旧001及psql兼容验证保留。上传线9d1022c+aa52a39：有界multipart、静态PNG/JPEG/WebP/10MiB/4000万像素校验、安全私有目录/UUID文件、事务元数据/失败清理、受控读取与共用组件。统计线30bfaef：一年匿名标识、北京时间自然日、并发幂等记录、区间独立去重、受保护查询和服务端管理员排除，未挂接前台事件。
- 三线独立审查发现并修复上传的双斜杠生产目录绕过、临时存储OS错误未转安全503两项P2；增加故障/清理测试并限定复查13项通过。整分支审查再发现焦点会话复核网络/503错误及其重试会卸载工具草稿（P2）；b01619c以真实父子组件测试先复现两段失败再修复，限定复查16项通过，无剩余P0/P1/P2阻塞。
- 集成完整检查：15项部署保护通过；后端128项中86通过、42项真实PG按预期跳过，Gunicorn配置与前端构建通过。当时前端43项通过；最后补丁仅前端，最终重新运行50/50及生产构建通过。未重复无变化的后端全套，不能将跳过项计为已在默认检查执行。数据库专项另完整运行四组：数据库14、认证/上传61、工具7、统计17，共99项全部通过，独立PostgreSQL17.11、私有Unix socket。首轮专项遇无匹配文件的空分组中止，按真实命名去掉空组后四组完整通过。
- 隔离数据库/临时目录上的真实浏览器5184→8012验收：临时账号登录、工具显示与顺序保存、公共页8项/全隐藏空态、隐藏骰子不挂载、网络失败及恢复不展示默认工具、正常焦点和网络故障/重试保留同一编辑器及未保存草稿；恢复显示后真实骰子1点、项目详情打开与Esc关闭，退出后管理工具401。1280px桌面、390px窄屏无横向溢出，截图已查看。常规favicon404、故障注入和预期400/401均产生控制台项，不宣称控制台零错误。
- 浏览器原生文件选择器驱动共用组件和真实FormData上传48×32 PNG，受控预览加载；损坏PNG返回安全错误且保留原模型/预览，匿名读取401。另在8013实际启动/停止两个独立API进程，复用同一数据库会话读取同一已上传图片均200，验证会话和图片跨进程重启持久化。未在真实开发库写测试图片。
- 独立匿名浏览器两次网站记录均接受，受保护查询401、伪造preview标记400；管理员查询区间人数为1，管理员记录返回false，验证区间去重与Cookie路径的真实浏览器链路。这里仅调用临时测试入口，真实前台流量记录与统计UI仍待7B；没有向开发库注入测试访客。
- 接真实开发库前发现原15432隧道/8010进程已退出，首次连接失败，未发生迁移写入。确认配置目标及端口状态后通过既有dev.sh恢复阶段C隧道/后端。目标核对为personal_web_dev库/同名账号后，串行应用002_tool_defaults：管理员/会话/工具数量从(1,1,0)至(1,1,10)，前两项保持，开发账号对personal_web_prod的CONNECT仍false，版本历史为001+002。该开发库迁移不是生产迁移或备份恢复验收。
- 用户5182预览切换到阶段C；实际代理健康200，公开工具读取10项。持久UPLOAD_DIR位于worktree/release外，通过忽略的0600开发配置注入，首次合法上传才创建目录；生产目录未创建。临时验收HTML和浏览器工件已移除/移至tmp，8012/8013/5184临时服务和自建数据库/图片随后清理；5182/8010开发预览保留。
- README、唯一计划、INDEX已同步，进度分别记录技术完成和待用户验收。3A/7A不代表3B/7B完成，工具设置待用户页面接受后计入完整任务。代码与文档仅本地提交，未推送、合并main、部署或访问生产服务；未运行GitHub CI/Python3.14/实际双worker生产专项。


## 2026-10-24：阶段 C 用户验收与阶段 D 准备复核

- 用户明确确认小工具管理测试无问题，任务6更新为技术及用户验收完成，完整任务计数3/8（1、2、6）。3A/7A维持基础交付状态，3B/7B和8B分别属于后续范围，未冒充完成。
- 本轮代码自01759fb未变。重新执行隔离PG专项14+61+7+17=99项全部通过，前端50/50通过；不重复无代码变化的构建、浏览器故障演练或生产测试。复核现有路由、上传私有读取、工具事务/无默认回退、统计管理员排除与区间去重，阶段C范围未发现阻塞遗漏。
- 实际开发库强制只读复核：数据库及账号personal_web_dev，管理员1、工具10、项目0、资料0；001+002版本历史及对应本地文件SHA-256匹配，开发账号对personal_web_prod的CONNECT仍false。5182公开工具响应与数据库逐项相同，没有重置用户验收后的显示/排序。UPLOAD_DIR已配置，未创建或写入新图片，未读取密码/会话令牌或访问生产。
- 修正当前计划中图片格式/大小仍写待定的旧描述，更新用户验收状态。阶段D准备列明两条业务线与3B联合验收，补充真实内容初始化、展示字段与表结构兼容、4KiB正文限制、数字项目id、演示地址隔离、profile.projects单一来源及公开图片引用/缓存边界；新增参数仍标助手草案，未开始产品实现。
- 本次验收记录提交作为D共同基线，预备集成与项目/资料/公开图片四个本地分支；独立工作目录和依赖留正式执行。保留5182/8010阶段C预览和三线目录，未执行内容迁移/初始化、fetch、push、main合并或部署；原目录.env.example外部改动保留。INDEX导航已同步，完整后台计划未完成，不归档。

## 2026-10-24：阶段 D 三线并行与本地技术交付

- 用户授权按准备建议固定接口/参数、建立三线独立目录并并行执行。四分支从e36bd1d起步，固定合同65b57af；目录分别为admin-phase-d、admin-d-projects、admin-d-profile、admin-d-public-files，均在既有忽略的.worktrees下。集成方独占入口、迁移003、初始化和文档；未新增运行依赖，未使用真实库做自动化fixture。
- 项目线b2cfcd0、8c58a28、b49e947：草稿、图文/截图/封面、预览、发布、每次保存完整校验、下架、原子排序和公开查询；资料线59e4a9e、d0b3cfe：七字段资料、逐行技能、头像与安全联系方式；图片线afc7b00：当前已发布项目/当前头像授权，匿名统一404、共享引用与安全存储。三线分别通过独立规格/质量审查，修复技能回车丢失、空图片元数据、Unicode长度与前后端URL往返不一致后限定复查通过。本地普通merge保留各线历史，不改main。
- 共用7e5cd37、5fe7156、0ec96cf、48ecd3c：新内容262144字节JSON解析、003追加category/features/cover_alt/初始化标记、同连接图片元数据读取、开发显式一次性初始化、主入口和共用请求接线、后台切换/会话故障保留草稿、公开项目/资料真实读取。首次初始化测试发现遗留trip-preview.png字节实际JPEG，0ec96cf按真实JPEG声明存储并保留原图字节；未放宽上传格式校验。迁移测试旧001/002数量断言已更新为003历史；联合测试最初误设创建返回201，按现有固定200合同修正，非业务失败被掩盖。
- 整分支48ecd3c独立审查发现资料HTTP链接可保存但被公开组件过滤；d9e2768复用项目HTTP校验，保留前端过滤与mailto/tel规则。最终限定复查规格/质量PASS，无遗留重要或次要发现；44个真实Python→Vue用例独立复核通过（16合法显示、28非法后端拒绝）。修复普通merge至39b3f8d。内容参数来自用户授权建议；取舍是保守安全URL合同和原截图JPEG真实声明，参数不合适时可后续调整合同，不篡改历史图片字节。
- 最终check.sh通过：部署保护15项；后端170项中99通过、71项真实PG专项明确跳过；前端73/73；Gunicorn配置与生产构建通过。另跑一次性本机PostgreSQL17.11：14数据库+103管理/上传/内容/公开图片+7工具+17统计=141/141通过，含发布失败回滚、并发初始化、原内容幂等，以及真实项目/资料保存与匿名图片权限联合矩阵。普通测试跳过不冒充真实数据库验证，未运行GitHubCI或Python3.14实机。
- Playwright CLI使用独立临时PostgreSQL、临时账号和图片，5184/8013验收：新增/上传封面/草稿/内存预览/发布/保存更新/下架/全部下架空态/重新发布；真实技能逐行输入、资料/头像保存及匿名头像；切换模块、会话焦点503与重试保留草稿；匿名详情打开事件、开发演示5173链接、Esc与滚动恢复；桌面及390px窄屏无横向溢出。最初故障注入恰逢overview忙碌被正常跳过，等待空闲后验证成功；临时Vite配置入口与fixture导入路径错误已修正，均非产品缺陷。移动端初次立即resize截图拼接异常，以新窄屏浏览器上下文重拍并目视复核；最终前后台截图保留在/private/tmp/pw-d-*，不加入构建。
- 实际接线前发现旧8010/15432进程已退出，5182前端仍属阶段C。复制既有忽略0600开发配置到D（不读取/打印密码），核对development、127.0.0.1:15432、personal_web_dev库/同名账号后用原dev.sh恢复隧道/后端。开发库串行应用003，显式初始化并重复验证无变化：管理员/会话由(1,1)保持(1,1)，项目/资料/图片由(0,0,0)变(1,1,1)，工具设置逐项保持，开发账号对personal_web_prod的CONNECT仍false。未连接生产库，未迁入临时验收账号/项目/头像。
- 只停止已核对cwd的阶段C Vite进程，在5182启动D前端；8010为D后端。真实代理健康、项目列表/详情、资料兼容projects、公开JPEG内容/原字节/no-store/nosniff、管理项目/资料/私有图片匿名401均通过；001/002/003文件SHA256与实际历史匹配。用户可继续使用原真实账号验收，未读取或重置账号/密码/会话令牌。阶段D技术交付不等于用户接受，完整任务仍3/8，任务3/4/5待人工验收。
- README、唯一计划、INDEX同步。保留D预览和三线工作目录；临时浏览器及自建数据库/图片服务随后清理。未fetch/push/main合并/部署或修改生产配置，原根目录backend/.env.example外部改动保持。7B统计UI与真实事件接线、8B生产HTTPS/迁移发布/备份恢复仍未实施，整体计划未完成，不归档。

## 2026-10-24：阶段 D 用户验收与阶段 E 准备复核

- 用户明确确认阶段D测试无问题，任务3（3A+3B）、4、5更新为技术及用户验收完成，完整任务6/8（任务1—6）；7B与8B仍未实施。复核范围含项目发布/保存/下架、资料、公开图片引用及跨模块草稿，不把未接真实入口的统计称为已完成。
- 本轮产品代码自98ceff4未变；重新执行隔离PostgreSQL14+103+7+17=141/141、前端73/73均通过。已有最终独立审查通过记录复核，无遗留阻塞项；无代码变更，不重复构建/浏览器故障演练/生产测试。Git集成目录开始时干净，原根目录backend/.env.example外部改动保留；本轮未fetch，main与本地origin/main引用均仍f01d1fe，不能据此推断远端或服务器新状态。
- 实际开发库采用REPEATABLE READ READ ONLY复核：身份personal_web_dev库/同名账号，001/002/003迁移SHA256匹配，管理员1、项目1、资料1、图片2；公开项目主体、profile全部七字段/已发布项目兼容映射及工具设置均与数据库一致。图片数量为用户验收后现状，不恢复为初始化时的1张；没有重置用户设置。开发账号对personal_web_prod的CONNECT仍false。网站/项目访客表均0，符合当前前台尚未记录；未POST采集、未读会话令牌/密码/个人资料具体值到日志、未访问生产。
- 阶段E准备沿用7A现有采集/统计合同和D成功打开事件，拆为访问记录与统计界面两线，集成方统一入口和联合验收。准备建议明确Cookie首访串行及多标签协调待固定、5秒非阻断采集/无自动重放、10秒受保护查询、7/30响应竞态、区间独立去重、下架历史和管理员排除；新增前端方案不冒充已实现或用户已确认。
- 本次验收/准备提交作为E共同基线，建立集成及两条实现线的本地预备分支；独立目录/依赖留正式执行。当前5182/8010阶段D预览保留。唯一计划和INDEX同步；README现行用法无需变更。未执行E业务、内容初始化/迁移/清理、push、main合并或部署；后台整体计划未完成，不归档。

## 2026-10-24：阶段 E 两线并行与本地技术交付

- 用户授权固定E接口/参数、建立访问记录与统计界面两线并行执行。三独立目录admin-phase-e/admin-e-visits/admin-e-statistics从3625b53起步，固定合同345d062；集成方独占共用入口/API/会话/后端与文档。Web Locks同源exclusive协调、5秒收集预算/无自动重试、缺失能力仅单页串行的精度边界已固定；不创建JS持久访客id，不新增运行依赖、SQL版本或内容初始化。
- 访问线7f68b61：精确同源POST/JSON/头、服务端管理员Cookie路径、布尔结果、每实例首页一次、项目重复真实打开可再次记录、FIFO/锁等待/网络/JSON总超时和dispose；23项模块测试通过。界面线a5bb46a：6字段严格统计解析（准备文字误写7字段，按已列清单和实际API纠正）、真实零值/空态/历史项目、服务端北京时间区间、7/30请求代次、401/403/503重试和卸载；54项通过。两线分别独立规格/质量审查PASS，普通merge保留历史。非合作注入依赖不响应AbortSignal时可能继续占用锁，但公开调用仍按预算返回；未冒充原生fetch行为或降低授权规则。
- 集成c1b421e接App唯一首页/成功项目事件、AdminApp懒加载保持真实统计组件、共用受保护GET和overview全ready。真实App测试验证资料/项目读取失败仍发首页、失败/关闭后的旧详情及非首页不记项目；真实父子组件验证503重试、零值、兄弟草稿和401。整分支审查发现统计401后旧焦点会话成功响应可恢复旧UI身份（P2，服务端授权仍有效，不是越权绕过），及README现行说明/降级边界遗漏（P3）。7f073d1用认证generation保护session/login/logout/overview及其catch/finally，并清除身份时释放busy；10项真实父子回归先红后绿，独立限定复查10项通过，两项ADDRESSED、规格/质量PASS；普通merge至df66596，无遗留重要/次要发现。
- 统一check.sh通过：部署保护15项；后端170项中99通过、71项真实PG明确跳过；当时前端155/155、Gunicorn配置和生产构建通过。隔离PostgreSQL17.11四组14+103+7+17=141/141通过，含跨日/7与30天独立去重及管理员排除。最终修复仅前端/README，重新执行最终165/165和生产构建通过；不重复无变更的后端/SQL，不能把跳过项当作已运行。Node MockTimers有实验性提示，非失败；未运行远端CI/Python3.14实机/生产双worker专项。
- Playwright CLI在临时库、临时账号/图片和5184→8013上验收：真实统计初始0及近7/30日期；同一全新匿名上下文的双标签同时首页/项目打开，分别仅1人、Cookie标识跨刷新保持且HttpOnly/Strict/Path正确；卡片展示不计项目，独立匿名上下文增加第2人；管理员同Cookie前台返回recorded:false、后台预览不发记录；下架后旧卡片详情404不发项目记录，历史人数保留。首脚本最后刷新前页面回到默认项目模块导致按钮查找超时，重新选择统计并核对前述计数断言，未据此前置状态问题判断产品缺陷。
- 临时浏览器故障/操作验证：采集503不阻断内容和详情、未写入计数；无Web Locks且首个网站响应延迟时，项目记录先排队，释放后同页复用首Cookie；旧7天响应(999测试值)不能覆盖已加载30天，统计503不显示假0，显式重试恢复；键盘Enter切7天成功，桌面/390px无横向溢出并目视复核截图。最终代码真实注入统计401+较早会话成功响应，保持登录页、不再请求旧overview，随后恢复原真实测试会话；这是临时故障注入，不修改真实开发会话。故障401/503和favicon404产生预期控制台项，不声称零错误。跨日口径由前述隔离SQL和重复事件测试验证，不冒充浏览器穿越自然日。
- 真实开发切换前后只读摘要验证：personal_web_dev库/同名账号，管理员/会话各1、项目1、资料1、图片2、工具10；项目/块/截图/资料/图片元数据/工具的SHA256摘要完全一致，001—003迁移历史文件校验匹配，开发账号对personal_web_prod的CONNECT仍false。复用既有忽略0600配置，核对并只停止D自有dev监督进程和Vite，让其清理自有隧道后按原dev.sh启动E；5182/8010均为E。未执行迁移/初始化或读取密码/会话令牌。
- 实际代理健康、新统计/认证generation组件编译及受保护7/30查询匿名401通过；使用服务端只读函数核对实际7/30网站人数均0、项目行1。真实访客表仍0，未把临时验收3名网站/2名项目访客导入开发库，后续只由自然开发访问积累；未冒充生产真实流量。原用户账号和内容无需重置，用户页面验收待进行，任务7不提前计入完成，整体6/8。
- README、唯一计划、INDEX同步。保留E预览及两线目录；关闭本轮浏览器并由临时监督脚本清理自有PostgreSQL/图片及5184/8013，工件在/private/tmp/pw-e-*不入构建。本轮未fetch/push/main合并/生产部署或改生产配置，原根目录backend/.env.example外部改动保持。8B生产HTTPS、首次初始化、迁移发布和数据库/图片备份恢复仍未实施，整体计划未完成，不归档。


## 2026-10-24：阶段 E 用户验收收尾与阶段 F 准备

用户确认阶段E测试无问题。本轮逐项复核E入口、去重/管理员排除、统计界面、会话竞态修复和既有独立审查记录，未发现阻塞E收尾的遗漏。任务7计入完成，完整任务7/8；8B仅完成准备，不视为生产交付。

本轮新跑：前端165/165；隔离PostgreSQL17.11临时集群数据库14、后台103、工具7、统计17，共141/141；部署保护15/15。日志为`/private/tmp/pw-e-close-front.log`、`pw-e-close-db.log`、`pw-e-close-deploy.log`。未修改业务代码，沿用上一轮构建及浏览器证据，本轮未重跑构建或浏览器。隔离实例自动停止并清理，不使用共享开发/生产数据。

真实开发只读复核：库/账号均personal_web_dev，开发账号CONNECT生产库为false；管理员1、会话1、项目1、资料1、图片2、工具设置10；两类访问日记录均0。7/30天函数真实查询成功，各返回网站0、项目1行且项目人数0；没有发送POST记录或导入测试数据。5182/admin与8010/api/health返回200，匿名statistics查询401。第一次只读盘点误用admin_users表名而报UndefinedTable，事务回滚；按迁移定义改为admin_accounts后完整重跑成功，未改动数据库。没有读取密码、令牌或个人内容输出；该检查不代表双向生产权限本轮重验或生产可用。

静态复核确认F缺口：生产迁移/账号初始化仍被CLI拒绝；部署脚本没有数据库就绪、成套备份、迁移及数据恢复；现有Nginx模板不含完整TLS/后台刷新。已在唯一计划补充两线建议、共享文件责任、执行顺序及故障/恢复验收。8A生产参数仍为建议，真实生产配置/域名/备份目标待F执行时核实。

本轮只更新文档与本地预备分支，不创建F工作目录或实现F工具；E真实开发预览和内容保留。未fetch/push、未合并main、未访问或修改生产，原项目backend/.env.example外部改动不纳入本轮提交。INDEX仅更新导航描述，整份计划仍有任务8待办，不归档。


## 2026-10-24：阶段 F 两线并行、本地交付与隔离演练

用户授权固定F合同、建立两线独立目录并执行。本轮集成目录admin-phase-f、迁移/初始化admin-f-release、备份恢复admin-f-recovery均从80417eb开始，独立依赖与临时资源，不复制开发.env。两线成果及限定修复已普通merge并保留工作目录；本地实现/审查完成，任务8仍待生产配置、用户接受和真实服务专项，整体7/8。合同和进度以唯一计划为准。

最终本地验证（修复及双worker专项合入后）：

- `bash scripts/check.sh`退出0：后端发现194项，实际103项通过、91项按规则等待隔离实例；根部署/恢复54项全部通过（其中27项真实恢复）；前端165项全部通过；Gunicorn配置检查和Vite生产构建通过。日志`/private/tmp/pw-f-final-check.log`。
- `backend/.venv/bin/python scripts/test_database.py`退出0：临时PostgreSQL17.11数据库28、后台113、工具7、统计17，共165项全部通过，未跳过。日志`/private/tmp/pw-f-final-db.log`。此项与普通发现有重叠，不能相加当作互不重复用例数。
- 实际CLI交接演练先验证旧空schema并备份，再执行生产迁移入口、只读schema检查和图片/业务表就绪。演练中的personal_web_prod库/同名角色只创建在runner拥有的本地临时Unix socket集群，使用专用端口和合成凭据，finally清理；不是服务器生产库，也未通过默认5432/15432连接真实数据。公网TLS传输在该演练中模拟，不能视为真实证书验收。
- 真实两worker用临时wrapper响应PID，证明同一会话和合法/非法CSRF均命中两个进程；停启后PID更换，会话、私图、公开图片引用、项目和工具保留；管理员两类访问recorded:false且统计表未增加。临时端口和自有进程组finally清理，PID头不进入应用。
- 真实dump/restore覆盖数据/序列、schema前缀、图片摘要/元数据、迁移前空库、故障回滚、继承锁、私有PGPASSFILE、非法归档/路径、混组和已有目标拒绝，保留旧有效备份。第二路径只证明副本字节一致，不证明异机/加密。

独立审查与修复证据：迁移/初始化线规格与质量通过，独立重跑159项SQL。恢复线审查重现函数对象污染仍报告成功的P2；411a263补充函数/类型/过程/domain/cast/defaultACL等空库检查，RED先重现、GREEN修复后27项真实恢复通过，独立限定复审也27项通过。整分支审查发现两个P1：只读迁移检查误带执行锁参数导致总回退，以及旧代码health通过就解维护却未查数据。aa20930移除只读锁参数并加实际CLI交接和回退数据探针；回退检查失败保持维护，限定复审27项部署测试通过，两个P1均关闭。无剩余已确认阻断发现。

运行边界：本机Python3.13、PostgreSQL17.11；未推送，新增CI的Ubuntu/PostgreSQL安装和Python3.14矩阵未在远端执行。本机未安装Nginx，模板仅静态核对，真实Nginx/HTTPS/systemd、权限/密钥读取、异机加密与生产恢复时间仍未验证。模板和启用开关默认拒绝真实发布；没有新默认密码、自动生产种子、生产restore或备份删除/定时安装。

E开发预览收尾：初次GET收尾出现代理502，直连确认8010与15432已无监听，原后端和隧道进程已停止；原因未确认。按原E目录/配置重新运行scripts/dev.sh，未改变F或服务器生产服务。恢复后直连5182/admin和8010/api/health均200，匿名statistics为401；只读确认personal_web_dev库/账号、管理员1、会话1、项目1、资料1、图片2、工具10、两统计表0，开发账号CONNECT生产为false。未发送访问记录或导入fixture。新dev监督exec会话17453（reload20127、worker20131），前端原进程71172保留；此PID仅是本轮时点记录。

没有fetch/push、main合并或访问/修改生产，未填写真实域名/凭据。原根目录backend/.env.example外部差异SHA256保持0564b4ac99f5a422b0245ea40ed3c28ed8dc3def153e7eef4111977839f985cf，未纳入成果。README现行用法、唯一计划和INDEX导航已同步；任务8未完，不归档整个计划。


## 2026-10-25：生产实际配置只读检查与IP上线前命令

范围：用户要求检查实际生产配置并提供手动步骤。通过StrictHostKeyChecking/BatchMode SSH连接ubuntu@124.223.69.7，只执行只读查询；不创建服务器文件/目录、不安装软件、不重启/重载、不迁移、不创建账号、不修改发布开关。读取受控配置及/proc时仅输出白名单字段，密码仅报告已设置；真实数据库密码只在只读psql子进程环境内使用，不输出、不写参数/文件。数据库查询显式BEGIN READ ONLY/ROLLBACK。

实查事实：

- current指向`/opt/personal-web-deploy/releases/f01d1fe704f9-xkr6hoam`，REVISION完整为f01d1fe704f92dde35431041f89f67be6703c8aa。服务active，User=ubuntu，WorkingDirectory为current/backend，Gunicorn监听127.0.0.1:8000、2worker；mainPID991733，worker991738/991739为检查时点。EnvironmentFiles确为/etc/personal-web/app.env，进程实际APP_ENV=production、DEBUG=false、DB_HOST127.0.0.1、PORT5432、DB_NAME/USER均personal_web_prod，密码已设置；UPLOAD_DIR、ADMIN_ALLOWED_ORIGINS和ADMIN_SESSION_HOURS未设置。
- 用该运行进程的真实连接参数连接成功，current_database/current_user均personal_web_prod。PostgreSQL18.6、18/main在线，数据目录/var/lib/postgresql/18/main，5432仅127.0.0.1/::1监听。两个账号均LOGIN，均非SUPERUSER/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS；dev→prod、prod→dev、PUBLIC→prod CONNECT全部false，两个库分别由同名角色拥有，无需重建账号或改密码。HBA本机TCP为scram-sha-256，无解析错误。
- 生产public业务表列表为空；开发库已有001—003对应12张表。没有查询个人内容、密码哈希、会话令牌或访客明细。
- 当前Nginx实际配置为/etc/nginx/conf.d/personal-web.conf，仅HTTP80、server_name124.223.69.7；root指current/frontend/dist，已有SPA回退，但没有独立assets缺失404、TLS、维护响应和8081探针。/trip/静态及8001代理与诊断保护实际存在。旧配置nginx -t成功；个人网站health和trip/health均正常。443无监听；UFW inactive，云安全组未能从本机配置确认。系统Ubuntu26.04、Python3.14.4、pg_dump18.6。
- app.env为root:root0600，服务可通过EnvironmentFile读取，但ubuntu部署进程直接读取将失败。deploy.json为root:root0644、enabled=true、health_url=http://127.0.0.1、health_host为IP，没有data_safety；服务器deploy_runtime.py不存在，deploy.py为旧入口。发布锁ubuntu:ubuntu0664，新版需收敛为0600。服务UMask0022、KillModecontrol-group，尚未应用F模板。
- /var/lib/personal-web、uploads、/var/backups/personal-web、/etc/letsencrypt/live均不存在。现有备份仅first-deploy-20261021，不含本次schema/图片成套恢复证据。未发现专用异机挂载或应用备份/证书定时任务。系统盘约59G，余48G；容量不替代异机备份。
- Certbot未在PATH，APT候选4.0.0-4；snap存在。依据Let's Encrypt官方2026-03-11文档，webroot IP证书要求Certbot>=5.4，shortlived约160小时且需自动续期，故手动方案采用Snap新版，不安装APT4.0或使用域名专用nginx插件命令。用户确认继续用IP，没有提供异机备份目的地。
- 本机gh不存在，未读取GitHub DEPLOY_ENABLED或远端main；服务器开关实查为true，不能据此断言仓库开关开启/关闭。也未执行fetch/push/main合并。

交接更新：README集中列出9步手动命令和停止点；本地ops/nginx-ip.conf.example按实查保留原trip路由，补HTTPS/ACME/维护/私有探针；发布JSON例子使用固定IP，replica_root留空，全部发布和前提开关仍为false。唯一计划及INDEX同步。新配置仅做本地静态检查，未上传/执行或用生产nginx -t验证；旧配置通过不代表新配置已验收。生产迁移/首次账号/内容/备份恢复与新代码发布仍未实施，本轮不重跑业务测试、不把整个阶段F计为完成。

参考：[Let's Encrypt IP证书和Certbot步骤](https://letsencrypt.org/2026/03/11/shorter-certs-certbot)、[Certbot安装](https://eff-certbot.readthedocs.io/en/stable/install.html)、[续期](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates)、[systemd-run](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html)。


## 2026-10-25：授权执行非HTTPS生产准备与当前空库基线恢复

授权：用户确认HTTPS以外可代做。本轮不再只读，实际执行服务器配套；没有操作证书、Nginx或443，没有部署新应用、迁移业务表、创建管理员或修改开发数据。

执行及证据：

- 先核对current仍f01d1fe，服务ubuntu/双worker；原app.env与运行进程的APP_ENV/DEBUG/DB_*逐项比对（密码仅内存比较、从不输出）一致。持有同一deploy.lock时，将原app.env/deploy.json/deploy.py/override.conf复制到root0700目录`/etc/personal-web/nonhttps-prep-20261024T164402Z`。目录名为UTC时间，对应北京时间2026-10-25。发布配置原仓库/镜像/工具参数保留，服务器enabled=false，新data_safety.enabled=false、replica_root为空、前提项全部false；health_url保留原http://127.0.0.1，未指向尚不存在的8081。
- 建立ubuntu:ubuntu的/var/lib/personal-web0755、其uploads0700及/var/backups/personal-web0700；发布锁ubuntu:ubuntu0600。app.env改为root:personal-web-ops0640，仅将ubuntu加入专用组。新SSH会话以实际ubuntu用户通过deploy_runtime.private_environment读取/解析成功，未打印密码。配置只增加UPLOAD_DIR和ADMIN_SESSION_HOURS=8；ADMIN_ALLOWED_ORIGINS仍未设置；原数据库参数/密码不变。
- 安装root拥有0644的deploy.py和deploy_runtime.py，服务器摘要分别79f42455f90d405de7018b26ddc8e93af0edaaeb148eb5265134d05bb2f57c33和4fcd58e869261290589e1f7ad3921a5a697e508003b3670e68e93419a3b17937，与本地已审查代码一致。实际调用data_config确认因关闭的data_safety拒绝部署，未调用--execute。
- 安装zz-production-safety.conf，位于旧override.conf之后；Gunicorn --check-config通过，daemon-reload及旧版本重启成功。实际进程确认UMask0077、KillModecontrol-group、ExecStart含--forwarded-allow-ips=127.0.0.1，UPLOAD_DIR与8小时会话配置已加载；最终主进程1317649、两个worker1317650/1317651为该时点。restart刚返回时一次curl连接尚未就绪，重试后200；不把短暂启动连接失败视为最终健康。
- 创建`/var/backups/personal-web/baseline-20261024T164646Z`0700，内有database.dump、uploads.tar、baseline-manifest.json，各0600。持锁短暂停止现有worker，确认inactive、无其他生产会话、public业务表0及图片0；用现有生产角色PG18.6只读dump，PGPASSFILE私有且finally删除，finally恢复原服务并探测健康。数据库dump SHA256为c358287d85ba70aea1e656dcd5f14436cd5f1b91499770b467a405c0729328bd，空上传归档为84ff92691f909a05b224e1c56abb4864f01b4f8e3c854e4bb4c7baf1d3f6d652。
- 同机另建PG18.6临时集群/var/tmp/pw-restore-*，仅Unix socket、端口25434、listen_addresses为空；恢复到personal_web_test_restore、账号personal_web_test，pg_restore单事务成功，身份及业务表0符合基线，耗时1.111秒。finally停止临时集群并删除该自有目录；生产/开发库未被恢复或清空。基线manifest标注restore_tested=true、offsite_copy=false，未将此旧空库恢复等同新后台有数据的恢复验收。
- 最终原REVISION保持f01d1fe704f92dde35431041f89f67be6703c8aa；Nginx侧/api/health、/trip/health及/__release.txt均200，仍无443监听。全过程没有Nginx命令变更/重载或HTTPS配置。新服务实际环境的生产身份/密码与受控原备份再次比较一致。

未完成及审核边界：计划把基线复制到用户Mac并使用hdiutil生成AES256映像和独立解密材料；两次自动权限审核均超时拒绝创建进程，操作未执行。中间一次仅重试了尚未生成的临时脚本，返回文件不存在，无备份动作；临时脚本补齐后仍审核超时，停止进一步重试。本地没有生成加密副本/密钥，也不能声称已有异机备份。这是审核超时，不是对操作安全性的否定。现仅有服务器同机、当前无业务表的基线与已验证恢复；自动异机备份、生产迁移、HTTPS及新代码发布仍待完成。

README已标记可跳过的已执行步骤及health_url保留理由，唯一计划/INDEX同步；本轮不重跑未变动业务代码测试，采用真实服务/权限/摘要/恢复验证。未fetch/push/main合并，原根目录.env.example外部差异保持0564b4ac99f5a422b0245ea40ed3c28ed8dc3def153e7eef4111977839f985cf，不纳入提交。


## 2026-10-25：再次授权后 Mac 加密备份及端到端恢复验证

用户明确授权将加密备份保存到Mac并检查可用性，本轮执行获准成功，替代上轮“审核超时未生成”的当前状态。先重新只读核对服务器baseline-20261024T164646Z的原dump/空上传归档SHA256及restore_tested=true，再通过现有主机指纹校验SSH/SCP下载到0700临时目录，没有读取或输出生产密码/会话内容。

保存结果：Git外`production/.personal-web-data/production/backups/baseline-20261024T164646Z.dmg`，141312字节，hdiutil AES-256加密；独立随机口令文件位于同级production/keys/baseline-20261024T164646Z.key，口令通过stdin提供给hdiutil，未输出、未放环境变量/命令参数/映像或Git。验证回执为同一backups目录中的baseline-20261024T164646Z-receipt.json。持久目录均0700，映像、口令和回执均0600且由当前用户拥有。映像SHA256：3b3a2404fd22fcf8a471df3db28f8beffd47d0adb54c91a58f804fa1046794d8。

可用性验证：

- hdiutil verify通过，isencrypted确认encrypted:YES；只读挂载解密，database.dump与uploads.tar摘要逐项匹配服务器原manifest，manifest内容一致。
- 从Mac映像的实际解密挂载中复制3个备份文件回服务器私有临时目录/var/tmp/pw-mac-restore-*；在独立新PG18.6集群（Unix socket、端口25435、listen_addresses为空）中以personal_web_test恢复到personal_web_test_mac_restore，pg_restore单事务成功；实际数据库/账号符合测试目标，业务表0和图片0符合该旧基线，耗时1.017秒。不是复用服务器原始dump作恢复测试，也未覆盖生产/开发库。
- finally停止并清理临时集群及回传明文；最终服务器该前缀临时目录0，Mac临时明文目录已删除、映像已卸载；映像/口令/回执保留。最终再核对映像摘要及0600权限均正确。
- 生产服务active、原REVISION仍f01d1fe704f92dde35431041f89f67be6703c8aa，health为ok。本轮未修改生产schema、HTTPS、账号、配置或发布开关。

验证仅覆盖当前无业务表/图片的基线，一次性Mac异机副本已可用；未配置持续异机复制或自动备份，不能据此将服务器replica挂载/TLS/完整恢复前提改true。README读取方式、唯一计划当前状态及INDEX同步；没有业务代码变更，不重跑不相关业务测试；未push/main合并，整体仍7/8。


## 2026-10-25：独立执行生产001—003迁移并验证迁移后恢复点

授权：用户确认备份通过，要求继续HTTPS以外生产准备，先迁移生产数据库，暂不合并发布。本轮只执行数据库表结构准备及必要备份/演练；旧站f01d1fe保持，未创建管理员、项目、个人资料或统计，也未操作HTTPS/证书/Nginx/远端Git。

来源与环境：使用本地已审查ad51bab提交的Git archive，tar SHA256为a7ea5df346e573d06c759349c283a46904bbbedf8ca54b9453a04edf78b7846d，服务器上传后摘要一致；解压于/home/ubuntu/personal-web-migrations/ad51bab私有目录，未覆盖current。独立Python3.14.4、uv0.12.3环境依据锁文件导出完整依赖并按哈希安装。默认源下载停滞，核对PID/CWD后仅终止此次暂存uv进程，改用既有腾讯镜像及现有发布同款uv export/pip sync --require-hashes流程。依赖未装完时曾过早启动测试，缺少模块而失败，无生产访问；齐备后隔离专项又因SSH默认umask0002令测试锁组可写而被正确拒绝。确认根因后按已生效的生产UMask0077重跑，未放宽锁保护、未改业务代码或SQL。

迁移前验证：服务器临时PG18.6集群/专用Unix socket、Python3.14.4，数据库28、后台113、工具7、统计17，共165项全部通过；日志/home/ubuntu/personal-web-migrations/ad51bab-pg18-tests-0077.log。独立测试中的同名生产角色/库只存在于该自建集群，非系统5432生产实例。使用受控app.env及实际ubuntu身份只读预检生产，applied=[]、pending001/002/003，public业务表0、上传0、双向CONNECT false，服务器两个发布开关false。

迁移流程：持有/opt/personal-web-deploy/deploy.lock，短暂停止原worker并确认inactive及无其他生产会话。先获取最新标准备份，再恢复旧服务完成Mac传输/恢复；正式执行时重新持锁停worker，核对生产真实库/账号、备份schema及内容摘要和上传清单一致，使用app.production_migrate --execute --expect-database personal_web_prod --expect-user personal_web_prod --lock-file ... --lock-fd N。001—003及schema_migrations同事务提交；finally启动旧应用并检查健康，不自动down/恢复数据。SQL未修改，SHA256分别为：

- 001_admin_schema：b47c9141e0b42926660dc7002230910a1b7254e76a516f824f9650c4672b6d1c。
- 002_tool_defaults：270d6d609a3b71f44ee151afaa0762a1d59d6553dba768787437b715e8247753。
- 003_content_fields：9e5d42c9952f5ff12e6ff161871d2bd0c0caee8109f0e209606b6bb6e7c6d03a。

结果：只读复核applied3/pending空，12表均归personal_web_prod。schema_migrations3行、tool_settings10行；admin_accounts/admin_sessions/projects/project_blocks/project_screenshots/site_profile/uploaded_files/site_daily_visitors/project_daily_visitors/content_bootstraps均0。开发/生产CONNECT双向false，开发角色对生产业务表无SELECT/INSERT/UPDATE/DELETE权限。production_readiness实际数据库、存储和7/30统计读取通过，admin_initialized=false、images0。迁移结果与回执保存于私有暂存目录migration-result.json、premigration/postmigration-receipt.json；没有导入开发数据。

备份与端到端恢复：

- 最新迁移前标准备份：`/var/backups/personal-web/2026-10-25T072259377030Z-f01d1fe704f9-2f25deca8742`；Mac映像`/Users/rewind/rewind_Workspace/workwork/production/.personal-web-data/production/backups/premigration-2026-10-25T072259377030Z-f01d1fe704f9-2f25deca8742.dmg`，SHA256 4cebe5aa2eab740091fec4d11f5b1e1b09199702c26ca2ab8c8bba5d1c577dfd。从映像实际解密文件经标准restore-test在独立PG18.6恢复，0业务表/0工具，耗时1.584秒。
- 迁移后标准备份：`/var/backups/personal-web/2026-10-25T072524267894Z-f01d1fe704f9-7f29ea1195d3`；Mac映像`/Users/rewind/rewind_Workspace/workwork/production/.personal-web-data/production/backups/postmigration-2026-10-25T072524267894Z-f01d1fe704f9-7f29ea1195d3.dmg`，SHA256 a4fdb751f5cfd2965eeb8300c2143f5e5e938d86e18ba1dd647c42b94a3d38e5。从映像实际解密文件经标准restore-test恢复，12张表/10项工具、全部3项schema及校验和正确，耗时1.416秒。
- 每组含manifest.json/database.dump/uploads.tar，先完整校验服务器同机传输缓存，再Mac AES256加密、hdiutil verify/只读解密、逐文件摘要核对，最后回传解密文件到/var/tmp/pw-canonical-restore-*独立测试集群（Unix socket、端口25436、listen_addresses为空）实际恢复；不以原服务器dump替代。每个口令独立保存在Git外production/keys目录，均0600，映像/回执亦0600、父目录0700。临时实例、回传明文、Mac明文和挂载均清理，现有基线映像保留。

发布边界：最终生产服务active，个人网站及旅行助手health正常；REVISION仍f01d1fe704f92dde35431041f89f67be6703c8aa，服务器enabled=false、data_safety.enabled=false、全部发布前提false、无443监听。旧应用不读新业务表，保持当前前台；没有合并/推送/发布。迁移后SQL具备初始工具行，但不等同生产账号、真实内容、HTTPS或自动异机备份已完成，整体任务仍7/8。README/唯一计划/INDEX已同步当前迁移状态与最新恢复点，原.env.example外部改动未纳入提交。


## 2026-10-25：完整部署授权及发布前验证（进行中）

用户授权完成依赖和生产代码部署，替代前轮不合并发布限制。工作区production/AGENTS.md及父工作区入口已读；原项目无AGENTS.md。实际目录admin-phase-f、分支codex/admin-phase-f，fetch确认origin/main仍f01d1fe。

本轮bash scripts/check.sh退出0：后端194项（91项需隔离实例，其余通过），部署/真实恢复54项通过，前端165项通过，Gunicorn及生产构建通过。bash scripts/test-db.sh退出0：隔离临时PG17.11数据库28、后台113、工具7、统计17共165项通过。日志/private/tmp/pw-release-check-20261025.log及pw-release-db-20261025.log。依赖声明已完整包含psycopg[binary]、pwdlib[argon2]、Pillow和python-multipart，无额外依赖修改。

服务器ad51bab私有暂存目录使用既有Node22.22.1安装前端锁文件并执行165项测试/生产构建成功，后端独立Python3.14.4依赖沿用本日迁移准备中按哈希安装的环境；不复用旧current。只读复核无IP证书、无443/8081监听，仍旧Nginx HTTP配置及current f01d1fe；发布/data_safety/前提全部false，replica_root为空。生产表此前已迁移，无需重复建表。

一次本地文档更新+commit+push组合命令在执行前被自动审批整体拒绝，故该命令未修改文档、未提交或推送。理由为部署记录含运维路径/状态，公开远端信息授权不够明确；随后已说明仓库SSpiderLily/personal-web为公开仓库并向用户请求明确选择。未通过其他工具绕过拒绝。HTTPS是否纳入本轮也已异步询问，未答前未操作证书。


用户随后明确同意将代码和现有部署记录推送至公开仓库SSpiderLily/personal-web，自动审批所缺的具体远端及数据范围授权已补齐；同时确认继续排除HTTPS，先完成其他部署准备。GitHub变量接口未由现有连接器提供；浏览器设置页面加载超时，未修改仓库变量。服务器部署开关保持false，保证main合并不能绕过TLS保护。

服务器补测：后端第一次从仓库根启动导致app导入失败；按scripts/check.sh规定改到backend后194项发现通过（91项待隔离实例，本日已另跑165项PG18专项）。恢复专项首次在Ubuntu重现FileNotFoundError：两处TemporaryDirectory写死/private/tmp，27项普通部署测试运行、恢复测试类无法启动。最小改/tmp后Ubuntu54项通过，但Mac因/tmp为符号链接触发现有安全校验，20项失败。最终统一为Path('/tmp').resolve()，不修改业务代码/备份安全校验；Mac54项全部通过，最终Ubuntu54项复验通过。暂存目录只上传了该测试文件进行补测，迁移SQL及运行代码未改；原ad51bab.tar摘要仍只指原始Git archive，不能用来代表补测后的整个暂存目录。


## 2026-10-25：PR10合并、服务器候选与中断竞态修复

PR10：https://github.com/SSpiderLily/personal-web/pull/10，head4784cf04338d59df4709e7d8c3b0e9df1c10ae4b；PR CI40173954117的Python3.13/3.14全部success，deploy skipped。独立差异审查无Critical/Important。显式校验head后merge为d3bc249ca417e38480d20fd7d17a81139ce12a5f，本地F已快进。用户已明确允许运维记录公开，原自动审批阻碍解除；无密码/密钥/备份内容提交。

GitHub连接器不提供Actions变量管理；浏览器设置页加载超时且未修改，随后用git credential helper的正常现有认证直接访问该仓库Actions变量API，仅输出DEPLOY_ENABLED从true变false的回读结果，认证信息未打印/保存/放入命令参数。正式切换仍禁用，不更改HTTPS。

持同一0600发布锁，调用安装版fetch/prepare，仅准备准确main d3bc249到/opt/personal-web-deploy/releases/d3bc249ca417-ve9908eb。Node22.22.1/uv0.12.3/Python3.14.4，26项生产依赖按锁文件及哈希安装，npm ci及生产构建通过，Gunicorn配置通过，无backend/.env。真实生产配置只读迁移pending空、readiness.ready=true/admin_initialized=false/images0；旧current f01d1fe、旧站健康、两个发布开关false。回执/home/ubuntu/personal-web-migrations/prepared-release-d3bc249ca417.json。

该候选临时双worker仅监听随机本机端口，以实际production环境读取真实生产库：health/profile/projects/tools200，骰子范围1—6，admin/session503符合缺少来源/TLS时关闭预期；Nginx用户可读前端index。项目仍空，未制造内容/账号/会话/统计；临时进程组已停止，未操作systemd/current/Nginx。回执prepared-release-smoke.json，日志prepared-release-smoke.log均私有。

main CI40174116758：Python3.13成功，Python3.14在test_interrupt_cleans_incomplete_staging_and_pgpass失败，断言子进程PID应不存在却仍存在；不是依赖下载问题，未只做重试。新test_data_backup_process确定性在Popen已生成自有sleep子进程、尚未返回句柄时发送SIGINT，原实现稳定失败（child仍运行），新实现通过。pg_run用pthread_sigmask在Popen赋值期间延迟SIGINT，在恢复原掩码后的中断/超时/异常中kill+wait，再退出PGPASSFILE上下文，保持600秒超时和输出隐藏。Mac55项通过；Ubuntu55项完整复验通过。独立限定复审无Critical/Important。候选d3bc249尚不含此修复，最终准备版本须另行记录。


## 2026-10-25：最终候选与本轮收尾核验

中断修复PR11 https://github.com/SSpiderLily/personal-web/pull/11 的head67c2b56fd426c3ef671ee55c4d65364290d5b435：PR CI40174591460 Python3.13/3.14均success、deploy skipped；显式核对head后合并543a1d700b6973d049a7954f8516efb4110c8807。main CI40174727738两项检查也全部success、deploy skipped，原main中断失败已由代码修复闭环，未仅重跑掩盖。

使用同一安装版fetch/prepare及发布锁，从准确main重新安装最终候选`/opt/personal-web-deploy/releases/543a1d700b69-s4tz5kgz`，26项生产依赖按哈希锁定，前端npm ci/build与Gunicorn配置检查通过；没有本地.env，没有触碰current或重启正式服务。回执`/home/ubuntu/personal-web-migrations/prepared-release-543a1d700b69.json`，本机日志/private/tmp/pw-prepared-final-release.log。暂存补测目录ad51bab本轮另上传了修复脚本/测试，仅供测试；候选从Git main归档重新构建，未从已修改的暂存目录复制运行代码。

最终候选以实际生产配置启动仅本机临时双worker：health/profile/projects/tools200，骰子200且值1—6；admin/session503符合未开放来源/TLS的保护。Nginx用户可读index，临时进程组结束清理。prepared-release-smoke.json已更新指向最终543a1d7，运行日志同名.log私有保存。正式服务active，个人网站和旅行助手健康，REVISION仍f01d1fe704f92dde35431041f89f67be6703c8aa；未修改Nginx/证书/443或新建账号内容。

最终新release解释器只读复核：001/002/003均应用、pending=[]，12张表全部归personal_web_prod，工具10；管理员/会话/项目/资料/图片及网站/项目统计均0。开发/生产CONNECT双向false，开发角色无生产表读写权限。现有schema、内容/序列摘要和上传清单与迁移后已验证Mac副本对应manifest一致；初次比较遗漏备份规定的UTC会话导致时间字段序列化摘要不等，按同一SET LOCAL timezone=UTC重查一致，不存在数据变更或恢复操作。

GitHub DEPLOY_ENABLED=false、服务器enabled=false/data_safety.enabled=false，异机挂载路径仍空；没有把单次Mac加密副本冒充持续复制。用户排除HTTPS的条件下，本轮完成代码合并、依赖安装及候选准备，不等同生产新站发布。后续须补HTTPS、发布可用异机备份和生产管理员/内容，再执行最新main的受保护发布。README/计划及INDEX入口已同步。根目录.env.example原有差异摘要仍0564b4ac99f5a422b0245ea40ed3c28ed8dc3def153e7eef4111977839f985cf；本轮未覆盖或提交。


## 2026-10-25：临时HTTP前台／同机备份／SSH后台实现与发布前验证

用户明确批准原IP HTTP前台、同机备份、SSH隧道后台及真实内容先录入再切换；本轮取代HTTPS/异机作为上线前提的限制，不伪填旧模式证据。实现合同与执行状态维护在唯一计划，现行用法已补README。分工为后端边界、部署适配器/模板、生产内容入口；只修改各自文件后集成，没有复制开发数据。

先失败测试后实现：HTTP+SSH配置/来源/Peer/Cookie/访问统计9项，部署显式模式及来源/前提15项，生产内容入口缺失测试。后端额外拒绝组播/IPv6/私网公源；保持默认HTTPS要求不变。生产内容复用事务/图片写入逻辑，但开发入口仍拒绝生产，生产入口要求真实身份、同一锁和完整schema，默认只读、幂等不覆盖。最初新测试fixture只填site_profile.name违反title/introduction非空限制，补齐测试数据后通过；未更改生产约束。

本轮统一检查scripts/check.sh退出0：后端发现208项（95项需SQL专项，其余通过），65项部署/真实备份恢复通过，前端165项及生产构建通过。日志/private/tmp/pw-http-ssh-check.log。随后补充真实隔离HTTP+SSH登录/会话/CSRF保存/注销、访问去重及管理员排除联合用例，完整SQL专项数据库28、后台120、工具7、统计17，共172项通过；日志/private/tmp/pw-http-ssh-db-joint.log。它只使用自建PG17.11 Unix socket实例和合成账号，不访问共享数据库。

独立审查检查tracked和untracked全部改动，无Critical/Important；审查方独立15项部署适配器与9项HTTP/SSH测试通过，git diff --check正常。真实Nginx/公网/SSH/生产数据库与账号验收尚未执行，不能从本地结果推断。新代码和文档准备提交CI，GitHub自动发布仍false。旧站只读检查health正常、current f01d1fe、nginx -t正常；旧profileAPI仍为“你的名字/个人网站”默认占位，不作为真实生产内容来源，按此前确认保留tracked真实旅行助手并移除这些占位。


## 2026-10-25：临时HTTP／SSH方案真实上线与验收（管理员待用户设置）

PR13 head0c17e423abcd87b7e2576fb59872fafc57ea6d9c，PR CI40186885743 Python3.13/3.14均success；合并9ccdc94bb8c665c3046ec761eb5e2114a173646b，main CI40187075525 success，deploy skipped（GitHub自动发布false）。临时模式实现和原HTTPS模式均通过检查后才进行真实发布。

配置准备：修改前持同一发布锁，将app.env/deploy.json/Nginx及部署双文件备份至root私有`/etc/personal-web/http-ssh-before-20261025T110008Z`。安装时逐文件核对本地摘要，备份父目录0700，app.env仍root:personal-web-ops0640，密码行不变；只增加PRODUCTION_MODE/PUBLIC_ORIGIN及精确loopback管理来源。旧f01代码无这些新字段，实际导入验证仍可启动。建立ubuntu0700同机mirror，安装模板后nginx -t通过才reload，失败分支会还原配置。Nginx18880及18881均只监听127.0.0.1；HTTP80保留，未配置TLS/443或修改数据库公网监听。

Mac通过真实公网请求验证health200、/admin及/api/admin/session404，经StrictHostKeyChecking/BatchMode SSH -L访问127.0.0.1:18880/__release.txt返回旧版，私有配置错误Host拒绝。SSH监督会话65665保持；私有后台需要该隧道运行，不把远程本机监听当作已验证公网隔离。

内容准备候选为`/opt/personal-web-deploy/releases/9ccdc94bb8c6-ggd_k6n8`，由main归档/锁定依赖重新构建。首次操作脚本误用系统Python，在任何停服/写入前因缺psycopg退出；改用该候选虚拟环境后执行成功。持锁维护、停worker并核对无其他生产连接，录入前备份`/var/backups/personal-web/2026-10-25T110623524381Z-f01d1fe704f9-fb03489b13d3`。独立生产入口核对目标/schema并录入真实旅行助手及封面，返回project_id1；开发bootstrap没有用于生产。录入后备份`/var/backups/personal-web/2026-10-25T110625519288Z-f01d1fe704f9-c8d77a92ccb5`，在自建PG18.6临时集群、Unix socket25436中经标准restore-test恢复，12表/项目1/图片1/账号0通过，约1.5秒，随后清理自有实例/目录。finally恢复并验证旧站后解除维护。回执`/home/ubuntu/personal-web-http-ssh/content-preparation-receipt.json`。

根据实际SSH、公网拒绝、同机恢复、停写与旧兼容证据启用http_ssh的六项前提，未伪填TLS/异机字段。服务器发布开关只在本轮受保护执行窗口设true；调用安装版deploy.py --execute 9ccdc94...，经历main/HEAD两次fetch、同一锁、生产依赖安装和前端构建、维护/停写、备份、幂等迁移、切换及健康/数据库/图片就绪检查。正式current为`/opt/personal-web-deploy/releases/9ccdc94bb8c6-1kp61ujk`。finally发布开关恢复false，data_safety.enabled=true/mode=http_ssh，GitHub自动发布仍false，维护标记已删除。旧release保留，没有手工ln绕过保护。deployment.log及deployment-receipt.json位于同一私有准备目录。

正式发布前最后备份`/var/backups/personal-web/2026-10-25T110814641695Z-f01d1fe704f9-c88abccbdf8d`，镜像副本为同名`/var/backups/personal-web-mirror/`目录，逐字节一致；目录0700、文件0600。其内容及图片摘要与已实际恢复的录入后快照一致。manifest旧应用版本f01d1fe表示备份发生在切换之前，不代表备份没有新录入的内容。本轮没有将新数据复制到Mac或将同机副本称为异机；原Mac迁移后快照早于内容录入，README已明确它不是当前最新恢复点。

外部验收：公网版本9ccdc94、health/profile/projects/tools及trip/health均200；唯一真实旅行助手已published、3段说明、封面字节SHA256为5bdd0cce92e3e82df3f9913df75b42f4ad69318f961379d3ccddf024d515ba51，Content-Type image/jpeg，与受版本控制源图一致。/admin、/admin/login、管理session/projects、编码路径/api/%61dmin/session、/api/admin%2fsession、重复斜杠及伪造Host/Forwarded头均404；公开统计错误Origin403，私有端口错误Host404。SSH匿名session200/authenticated=false；私有/trip跳转公网后200。没有发送有效凭据或伪造业务fixture来验收生产。

应用内浏览器连接超时，改用Playwright受控headed浏览器：1440×1000桌面、390×844手机、项目详情/真实封面、骰子动画结束显示6点、SSH后台登录表单均通过；手机horizontalOverflow=false、图片均loaded。正常页面浏览产生实际匿名统计，最新只读时网站记录2/项目记录1（不是导入开发记录）；后续随访问变化。截图与快照移到Git外私有`/Users/rewind/rewind_Workspace/workwork/production/.personal-web-data/production/verification/http-ssh-20261025`，无账号密码录屏或存储快照。

正式进程核验：systemd active，master1592537及两个worker1592539/1592540为当时时点；/proc白名单确认APP_ENV=production、DEBUG=false、PRODUCTION_MODE=http_ssh、PUBLIC_ORIGIN为公网IP、ADMIN_ALLOWED_ORIGINS仅127.0.0.1:18880、DB_NAME/USER=personal_web_prod、持久UPLOAD_DIR正确。只读实际库12表、001—003无待项、项目1/说明3/资料1/图片1/工具10，开发/生产CONNECT双向false。当前管理员/会话0，已给用户真实TTY命令并异步等待初始化结果，未代设密码或复制开发账号；初始化后还需真实登录确认及补充含账号状态备份，所以任务8与整计划不标完成、不归档。后续HTTPS/异机为用户延期选择，不是本轮上线阻碍。README中过时空库/旧候选描述已纠正，旧HTTPS独有步骤迁移到既有归档并标为历史，INDEX已同步。
