# 验证记录

## 2026-10-13：初版框架

- 环境：macOS，Python 3.13.7，Node.js 22.22.1，npm 10.9.4。
- `uv sync --python /Library/Frameworks/Python.framework/Versions/3.13/bin/python3` 成功，生成项目虚拟环境和 uv.lock。
- `npm install` 成功，生成 package-lock.json；安装时审计报告为 0 个漏洞。
- `npm run build` 通过，Vue 页面成功编译。
- `uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8010` 与 `npm run dev` 均成功启动。
- HTTP 检查：8010 的 `/api/health`、`/api/profile`，5180 的 `/`、`/api/profile` 全部返回 200；已断言健康状态及默认姓名、项目数量，确认代理联通。
- 本机旧 Python 3.7 不可执行，首次安装使用显式 Python 3.13 路径。常用端口存在占用，项目采用 8010 和 5180。
- 浏览器工具报告会话关联错误，实际渲染、移动端视觉效果及失败重试交互未验证。已实现加载、错误及重试状态。
- 人工接受未确认；未部署；未初始化 Git、未提交或推送。验证服务收尾时停止，可按 README 重启。

## 2026-10-13：后端骰子小游戏

- 用户确认由后端生成 1～6 点，不实现留言板，不持久化数据。
- `npm run build` 通过。
- 独立启动后端至临时端口 18010，100 次 POST 全部返回 200 和 1～6 的整数；实际覆盖六种点数。此检查不证明随机分布均匀。
- GET 掷骰子接口返回 405；原个人信息接口正常。验证进程已停止。
- 前端已实现请求中动画、防重复点击、8 秒超时、失败重试提示和结果范围校验；浏览器点击与动画效果未验证。
- 人工接受未确认；未部署、未提交或推送。

## 2026-10-20：首页旅行助手展示

- 个人介绍、旅行助手精选卡片、其他项目、小实验分区；保留米白与绿色风格。行程示意明确标记，体验按钮暂时禁用，预留 `/trip/`。
- 前端生产构建通过；本机生产预览桌面浏览器显示首页、精选卡片、其他项目和小游戏，未发现遮挡。骰子点击完成并显示 2 点，个人信息代理正常。
- 添加 650px 和 850px 布局断点；移动端实机、个人信息失败交互未专项验证。
- 未部署服务器，未提交或推送；人工接受未确认。临时验证服务完成后停止。

## 2026-10-20：项目列表与侧边娱乐初版

- 用户确认本轮方向：项目展示采用列表板块，骰子移至侧边娱乐板块；Trip Planner 由另一任务部署，本轮仅调整个人网站布局。
- 桌面左侧为横向项目卡片列表（旅行助手优先），右侧为独立娱乐角。卡片展示布局示意、名称、简介、技术标签和链接；未启用标签筛选、分页或详情跳转。
- 使用原有后端骰子接口；侧栏不遮挡项目列表，移动端通过820px/540px断点转为上下排列。
- 生产构建和 git diff --check 通过；桌面浏览器确认项目列表及侧栏，骰子点击成功。移动端实机和个人信息失败交互未专项验证。
- 使用说明和现行计划已同步；本轮未部署、提交或推送，人工接受未确认。

## 2026-10-20：作品卡片与完整详情

- 按用户要求移除个人网站自身的作品卡片。公开项目从前端配置维护，当前只有旅行助手；侧边功能名为“小工具”。
- 旅行助手卡片展示名称、简介、技术标签和SVG预览示意图；整卡原生按钮可点击或按回车打开原生dialog，展示完整说明、功能和GitHub链接。演示地址预留 `/trip/`，等待另一任务部署确认后启用。
- 详情支持Esc、关闭按钮和遮罩关闭；锁定背景滚动、关闭恢复焦点，重新打开回到顶部。顶部关闭按钮在弹窗内滚动时固定。
- 生产构建及差异格式检查通过；浏览器约493px窄屏验证详情打开、滚动到底查看入口、Esc关闭和焦点返回；预览图为示意，并非真实行程截图。未验证演示目标服务，未部署、提交或推送。

## 2026-10-20：使用旅行助手实际页面截图

- 按用户要求替换示意图，截取 `http://127.0.0.1:5173/` 实际运行的旅行需求填写页，原始截图1280×720，未调用模型或提交规划。服务器 `/trip/` 的HTTP检查为200，但浏览器读取超时，因此未使用服务器截图。
- 卡片和详情统一使用 `frontend/src/assets/trip-preview.png`，按原比例完整展示，未使用生成图或模拟页面。说明和图片替代文本同步更新。
- 生产构建和差异格式检查通过；浏览器确认卡片图片替代文本及详情中的实际首页截图正确，图片按完整比例显示。未部署、提交或推送。

## 2026-10-20：启用旅行助手演示入口

- 用户确认旅行助手已完成部署，启用详情中的 `/trip/` 在线演示链接；保留新标签页打开。卡片状态改为可在线体验。
- 本机Vite开发与生产预览将 `/trip` 原路径转发到 `http://124.223.69.7`，避免本地测试落入个人网站首页；生产构建链接仍是相对路径 `/trip/`。
- 本轮仅修改个人网站入口和本机代理，真实行程功能等待用户测试；个人网站尚未部署、提交或推送。
- 验证补充：生产构建和差异格式检查通过；本地代理与公网 `/trip/` 均HTTP 200，但页面标题为“我的个人网站”，加载个人网站原资源 `index-BRZAw1lQ.js`。因此该200不是旅行助手部署成功证据，已告知用户检查服务器路径映射。

## 2026-10-20：暂缓演示接入并交付展示页面

- 用户要求撤销演示接入并推送合并：在线演示恢复禁用，保留准备中提示和后续配置；移除本机 `/trip` 服务器代理。上述启用及路径检查记录保留为历史。
- 本轮交付包含旅行助手项目列表、实际页面截图、详情弹窗、GitHub链接和侧边“小工具”骰子。用户已明确授权提交、推送及合并；交付提交与合并结果以Git历史为准。
- 生产构建及差异格式检查通过；已有浏览器验证覆盖卡片/详情、键盘关闭与焦点恢复、真实截图显示和骰子请求。个人网站未部署，线上演示未验收。

## 2026-10-21：启用已部署的旅行助手入口

- 用户授权启用 `/trip/` 演示、验证后推送合并；详情按钮恢复可点击，卡片显示“可在线体验”，相对路径保持 `/trip/`。本机开发/预览代理至 `http://124.223.69.7`，生产环境仍由Nginx提供路径。
- 生产构建与 git diff --check 通过；公网及本机代理的HTML标题均为旅行助手，JS/CSS资源使用 `/trip/` 前缀并返回200，`/trip/health` 返回健康状态。
- 浏览器验证详情的演示链接指向 `http://127.0.0.1:5180/trip/`、按钮可点击并保留新标签页属性；内置浏览器未列出新标签页，因此目标页面通过上述HTTP检查确认，不将其计为浏览器跳转验收。
- 数据库由另一任务确认，未提交规划请求、未验证持久化；本轮未部署个人网站服务器。代码交付以Git提交和PR记录为准。

## 2026-10-21：本地检查与 CI

- 基于远端main `2e63c12` 创建 `codex/local-checks-ci`；开始时工作区干净。服务器只读复核：main为 `fb6fc8f`，额外提交仅新增deploy.sh；个人网站Python为3.14.4、Gunicorn26.2.0、FastAPI0.143.0、Uvicorn0.54.0。未修改线上文件或重启服务。
- 依赖补齐Gunicorn26.2.0，测试组增加当前Starlette使用的httpx2并更新uv.lock；现有FastAPI/Uvicorn等运行依赖未升级。明确Python支持3.13/3.14，本地默认3.13，Node版本文件固定22.22.1。
- 原目录Python3.13.7、Node22.22.1、uv0.12.3执行 `bash scripts/check.sh` 成功：锁定依赖安装、5项HTTP契约测试、现有Gunicorn双worker配置检查及Vite生产构建通过。
- 在不含.venv、node_modules、dist的临时副本中，以Python3.14.7重复完整检查成功，证明该macOS环境可以从锁文件重新安装。并非线上Python3.14.4或GitHub Linux实测。
- 临时副本将健康接口响应改为错误值，检查脚本返回1、test_health失败，前端安装/构建未执行；临时文件随后恢复。原仓库业务代码未注入故障。
- bash语法、Workflow YAML解析及Python矩阵、git diff --check通过。CI配置在分支push、main PR及手动触发时执行同一脚本，无SSH/部署步骤，权限仅contents:read。尚未提交或推送，因此GitHub Actions运行及main规则未验证/配置；不能称为已启用合并门禁。
- 未新增浏览器验收；页面布局、演示跳转、线上回退仍不属于本轮通过范围。Gunicorn --check-config不等于真实多进程HTTP启动测试。
- README、当前计划及工作区INDEX导航已同步；服务器独有提交、默认Node版本和原地构建问题保留为部署阶段待办。

## 2026-10-21：本地联调整理

- 移除生产/trip代理，开发模式默认演示地址为本机5173，生产构建为/trip/；新增build:local、preview:local输出到dist-local，开发环境示例及忽略规则。
- check.sh通过：5项HTTP测试、Gunicorn配置、锁定依赖安装与生产构建；本地构建通过。产物确认生产包不含本机5173，本地包包含5173且不含生产IP。
- 临时5199开发/4199预览通过HTTP访问实际本机8010健康接口；确认不存在生产/trip代理。首次测试在服务器创建后替换代理未生效，模拟响应断言失败，改用真实本地后端后通过。关闭测试开发服务产生预构建取消提示，不计为功能失败。
- 未调用生产服务或生成行程，未验证完整浏览器交互或GitHub运行。README、计划、INDEX同步；未提交、推送或修改线上。

## 2026-10-21：GitHub CI首次验证

- 用户授权提交、推送和创建PR，不合并、不部署。功能提交6375eaf已推送至codex/local-checks-ci，PR：https://github.com/SSpiderLily/personal-web/pull/3 。
- PR触发运行：https://github.com/SSpiderLily/personal-web/actions/runs/39548296023 。Ubuntu 24.04上Python 3.13和3.14两项检查全部成功，包含环境准备、锁定依赖安装、5项接口测试、Gunicorn配置检查和生产构建。无须修复CI。
- 本条记录针对6375eaf；文档同步提交的状态另以PR最新检查为准。主分支保护、合并、部署和旅行助手完整交互不在本次验证范围。

## 2026-10-21：main 合并后自动部署只读核查

- GitHub main 为 6729e9f，push CI 运行 39548672670 成功：https://github.com/SSpiderLily/personal-web/actions/runs/39548672670 。远程 .github/workflows 仅 ci.yml，只有 check 作业，没有部署。
- SSH 只读检查：服务器仍为 fb6fc8f，父提交为 2e63c12；工作区无未提交改动。未在服务器执行 fetch/pull。服务器 origin/main 是旧的本地跟踪引用，不能用 ahead 1 判断与当前 GitHub 的完整差距。
- deploy.sh 仅 git pull origin main、npm run build、sudo systemctl restart；没有依赖同步、健康检查、回退和发布锁。Node 为 20.20.2，不满足 frontend engines >=22.12；非交互 PATH 未找到 uv。
- fastapi-personal-web active，127.0.0.1:8000/api/health 返回 status=ok。systemd 直接引用 /opt/personal-web/backend/.venv；nginx -T 确认个人网站 root 为 /opt/personal-web/frontend/dist，/trip 独立指向 trip-planner 目录和8001端口。
- ubuntu 无 crontab，root crontab 仅看到云厂商维护任务；systemd timers、cron及服务名筛查未发现个人网站自动部署入口。未读取 GitHub Secrets/Webhooks 或云安全组，因此不声称它们不存在。
- ubuntu 具有 NOPASSWD: ALL，自动部署方案需另设受限权限。不读取或输出私钥、令牌。未修改线上配置、未构建、未重启、未触发 Actions。仅更新本地说明和计划，未提交或推送。

## 2026-10-21：部署草稿本地验证

- 新增 scripts/deploy.py、ops/ci-deploy.yml.draft、配置/服务/Nginx/sudoers 示例及 tests/test_deploy.py；保留原 .github/workflows/ci.yml 不变。工作流不在扫描目录中；脚本默认不执行，配置 enabled 默认 false。
- 15项离线测试通过：成功切换、构建失败不切换、健康/重启失败回退、中断回退、回退失败不报成功、过期SHA拒绝、构建期间main前进不切换、重复发布、文件锁、初始化缺失、双重执行开关、非法SHA、API/静态版本/资源检查、锁文件安装及发布目录权限。服务、网络和构建命令为模拟；链接切换和文件锁使用真实本地临时目录。
- 首轮测试因 macOS /var 与 /private/var 的路径别名断言失败，规范化测试临时目录后通过；复核补齐 release 目录0755权限，防止Nginx无法遍历，再次运行15项通过。
- bash scripts/check.sh 完整通过：部署离线测试、5项后端HTTP契约测试、Gunicorn配置检查、npm ci及Vite生产构建。新权限调整后重跑受影响的部署测试通过。
- Ruby YAML解析、部署作业needs/cancel配置断言、内嵌bash -n及git diff --check通过。未安装actionlint，未在GitHub实际运行草稿；不将语法检查描述为GitHub兼容性或真实部署验收。
- 未连接生产服务器、未修改线上、未触发Actions；未提交或推送。本地README、计划及工作区INDEX导航已同步。服务器初始化、专用账号/SSH、工具路径、GitHub Environment/变量/Secrets、首次发布与回退验收仍待单独授权。

## 2026-10-21：部署草稿提交与 PR CI

- 用户授权创建分支、提交推送与创建PR，不合并、不修改线上；分支 codex/deploy-drafts，功能提交56a2b6436f9c13401a84a08d66c71bc899ba0197，PR https://github.com/SSpiderLily/personal-web/pull/4 。
- PR CI运行39550185995的Python3.13/3.14两个作业均success：https://github.com/SSpiderLily/personal-web/actions/runs/39550185995 。包含离线部署保护测试、接口测试、Gunicorn配置检查和前端构建；不代表真实部署验收。
- 现行.github/workflows/ci.yml未更改；草稿仍位于ops/ci-deploy.yml.draft，配置enabled=false；未连接生产服务器、未开启部署。本记录同步产生的后续提交应以PR最新检查结果为准。

## 2026-10-21：PR #4 合并与分支清理

- 浏览器核实最终提交 ba2f2ed 的4项检查全部通过、无冲突，然后合并 PR #4，合并提交86924b65eec9978fdb8c90f93c7d39d5b7e26367。GitHub自动删除远程codex/deploy-drafts。
- 本地fetch --prune，确认分支是origin/main祖先后快进更新main并安全删除本地分支；远程分支列表仅main。本次未连接生产服务器或执行部署。
- 现行CI和部署配置相对PR最终提交无差异，仍只有check作业、enabled=false。合并后main的CI结果本轮未核实。
- 合并记录通过后续文档 PR 同步；该文档 PR 的提交、CI及合并结果以 GitHub 历史为准，避免为记录文档自身的合并反复产生新提交。

## 2026-10-21：首次部署配置只读核查

- SSH只读核查账号、指定目录、工具版本、systemd和Nginx配置、磁盘内存与健康接口。服务器仍为fb6fc8f，未fetch/pull；新账号与部署目录/配置/脚本不存在，Node20.20.2，Python3.14.4，未找到PATH内uv；服务健康。
- 浏览器核实GitHub没有Environment、Secrets、Variables；经典分支保护页未列规则，Rulesets API返回[]。腾讯云当前实例124.223.69.7防火墙允许全部IPv4访问TCP22/80/443/14647及ICMP；未编辑规则。主机UFW inactive。
- 服务器到GitHub返回301、npm/PyPI返回200，仅证明这些HTTP入口可达，不证明完整安装成功或runner SSH可用。通过现有SSH读取主机公钥指纹，未读取私钥。待操作顺序已同步计划，未提交推送或改动线上配置。

## 2026-10-21：首次手动部署完成（简化方案）

- 用户明确同意复用现有账号完成手动部署，暂不启用自动部署。发布SHA936d8b26ad0f95f6bd49e9e61d029bc92a6d65ba；GitHub main CI成功，本机ls-remote确认相同SHA。
- 原站点fb6fc8f及其虚拟环境/dist保留；旧Git bundle和systemd/Nginx配置保存于/opt/personal-web-deploy/backups/first-deploy-20261021。项目工具独立安装Node22.22.1和uv0.12.3，Node官方SHA256校验通过。
- 服务器GitHub fetch失败：GnuTLS recv error (-110)，改为传送本机main Git bundle并核对SHA。uv默认下载阻塞后，导出锁定requirements，使用腾讯HTTPS镜像和--require-hashes安装15个生产包。Gunicorn配置、npm ci/build及临时127.0.0.1:18010健康检查通过，临时进程已退出。
- 最终release为/opt/personal-web-deploy/releases/936d8b26ad0f-797kf948，运行Python3.14.4。仅替换个人网站systemd路径和Nginx root，用户仍ubuntu；nginx -t通过后重启个人网站并重载Nginx。
- 脚本健康验证通过；本机公网GET /、/api/health、/__release.txt、JS/CSS、/trip/、/trip/health均200，版本标记匹配完整SHA；旅行助手index哈希不变。不推断完整旅行规划业务已验收。
- GitHub自动部署未启用，服务器配置enabled=false；未修改GitHub设置。旧版本恢复脚本已保存并bash -n通过，未执行真实回退。初始化脚本为一次性程序，通用部署草稿未解决此次网络问题。
- 本地README、执行计划和本记录更新，未提交或推送。

## 2026-10-21：服务器通过 SSH 拉取 GitHub

- 用户明确指定复用服务器已有SSH密钥。以ubuntu执行BatchMode、StrictHostKeyChecking=yes的git ls-remote及真实git fetch均成功，main为936d8b26ad0f95f6bd49e9e61d029bc92a6d65ba；未读取私钥。
- /etc/personal-web/deploy.json的repository改为git@github.com:SSpiderLily/personal-web.git，enabled仍false。仅更新代码缓存，未切换current、构建、重启或重新部署。
- 本地配置示例、README及计划同步；未提交推送。此连接为服务器到GitHub，不等同于GitHub Actions到服务器的登录配置。

## 2026-10-21：自动部署接入准备

- 用户授权完成余下自动部署步骤。脚本改为uv export --locked导出生产依赖，再通过配置镜像使用uv pip sync --require-hashes安装；SSH fetch启用非交互、严格主机核对和连接超时。
- 现行CI新增needs:check部署作业，仅main push且开关true或显式手动deploy输入才运行；草稿已迁入正式工作流，不保留副本。并发不取消正在发布的任务。
- 本地15项部署测试、5项HTTP测试、Gunicorn检查与Vite构建通过；YAML解析和内嵌bash语法检查通过。
- production环境仅main，配置专用Actions登录密钥（加密保存在环境Secret）、核实的主机公钥和仓库变量。已从本机用此密钥登录ubuntu成功；并非runner验收。自动开关暂false，后续真实发布结果继续记录。

## 2026-10-21：Actions真实发布验收及自动部署开启

- PR #6合并提交8bccaba03c819338bee4712081993a912f5e42c9。手动workflow_dispatch运行 https://github.com/SSpiderLily/personal-web/actions/runs/39553907949 的Python3.13/3.14及deploy三个作业均success。
- 实际由GitHub runner使用production环境密钥登录ubuntu，服务器通过自身GitHub SSH密钥fetch，执行锁定依赖镜像安装、前端构建、切换和重启。服务器current/REVISION及公网/__release.txt均为8bccaba完整SHA。
- 公网首页、/api/health、版本标记、JS/CSS、/trip/和/trip/health均200。此前离线回退测试通过，但未对线上故意注入故障，不能声称真实回退已演练。
- 验收后通过API将仓库DEPLOY_ENABLED设为true并读回确认；服务器enabled=true。production分支策略仅main；变量DEPLOY_HOST/DEPLOY_USER已设，环境Secrets包含DEPLOY_SSH_KEY和DEPLOY_KNOWN_HOSTS。
- 本次验收文档PR合并会触发首次push main自动发布；其最终CI、部署、分支清理证据以GitHub历史及任务交付结果为准，不循环追加文档提交。用户后续自行验证可见页面改动。
