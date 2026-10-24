# 阶段 C 3A 上传线交付报告

日期：2026-10-24。分支：`codex/admin-c-uploads`。共同基线：`ddd57e1`。
实现提交：`9d1022c697a707f882a607d462c894130dbd62b5`。

## 范围与接口

- 新增 `app.admin_uploads.router`：`POST /api/admin/files` 与 `GET /api/admin/files/{uuid}`。主入口未改，集成方需要显式挂载此 router。
- `require_admin_upload` 在任何 body 读取之前验证精确可信 Origin、`X-Admin-Request=1`、真实会话、绑定 CSRF 和 multipart 类型。原 JSON 写保护保持原行为。
- 先接收并限制整个请求至 10 MiB + 64 KiB，再解析 multipart；仅接收一个名为 `file` 的文件。无 Content-Length 的增量 ASGI 接收同样有界。强制 multipart 完整终止，关闭未完成的临时文件。
- 原文件限制为 1—10,485,760 字节、最多 40,000,000 像素。仅静态 PNG/JPEG/WebP；验证实际格式与扩展名、MIME 一致，拒绝多帧、截断和损坏图；执行 verify 后重新完整 decode。补充 PNG IEND 完整性和 CRC 检查，因为 Pillow 单独 verify/load 会接受少量尾部截断。
- UUID 同时作为记录 ID 和存储键；原文件名只作元数据。安全文件完成写入、flush/fsync 后才启动元数据事务。事务失败回滚并删除本次文件。读接口只读取已存在的元数据，孤文件无法访问。
- `UPLOAD_DIR` 可选，配置为空时上传/读取返回 503，不影响应用导入和公开 API。配置必须为绝对路径且无父级跳转/空字符；production 在请求时拒绝当前 release 内目录。
- 目录逐组件使用 `O_NOFOLLOW` 与目录文件描述符打开。最终目录要求当前用户所有、0700；文件独占创建为 0600。读取拒绝符号链接、非普通文件、硬链接、所有者/权限/大小异常及越界存储键。返回 `nosniff` 与 `no-store`；未挂载静态目录。
- `ImageUpload.vue` 接受 `api.upload(file)`、`modelValue`；成功发 `update:modelValue`，失败保留旧值，401 发 `unauthenticated`。组件不持有 CSRF 或会话凭据，也不包含业务保存表单。
- 新增并锁定 Pillow 12.3.0、python-multipart 0.0.32；依赖安装仅在本 worktree 的 `.venv` / `node_modules`。

## Red / Green 证据

所有写入、安装、正式测试和 Git 提交均在分配目录内执行；数据库只使用本次自建 Unix socket 临时 PostgreSQL 17.11。没有开发隧道、云访问、共享开发数据库或真实凭据。

| 命令/范围 | 实际结果 |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests -p test_admin_uploads.py -v`（backend cwd，初始红灯） | 12 个失败，原因均为上传模块未实现 |
| `.venv/bin/python /tmp/uploads-db-runner.py`（初始红灯） | 18 个上传测试失败，包含 6 个真实库用例，原因均为上传模块未实现 |
| `node --test tests/image-upload.test.js`（frontend cwd，初始红灯） | 5 个失败，原因均为组件未实现 |
| 新增未终止 multipart 回归后同一后端模块命令 | 1 个预期失败：错误地到达存储阶段并返回 503；补终止检查后通过 |
| 新增空字符目录配置回归后同一模块命令 | 1 个预期失败；配置校验修复后通过 |
| 新增 PNG IEND 尾部截断/损坏回归后同一模块命令 | 1 个预期失败：Pillow 放行后到达存储阶段；补 PNG 终止块检查后通过 |
| `APP_ENV=test DEBUG=false .venv/bin/python -m unittest discover -s tests -v`（最终普通后端） | 89 项，64 通过，25 项真实库测试按约定跳过，无失败 |
| `.venv/bin/python /tmp/uploads-db-runner.py`（最终隔离库） | 29 个不同上传测试全部通过（20 安全 + 9 真实 SQL）；临时 runner 的两个 discover 均执行同一组，不能累计为 58 个不同用例 |
| `npm test`（frontend cwd） | 30 项通过，含新增组件 5 项 |
| `npm run build`（frontend cwd） | 生产构建成功 |
| `@vue/compiler-sfc` 单独编译 ImageUpload 的 script/template/scoped CSS | 全部成功；组件尚未由入口挂载，故另做此检查 |
| `uv sync --locked` | 32 个包解析、29 个包检查通过，锁文件一致 |
| `APP_ENV=test DEBUG=false .venv/bin/gunicorn --check-config app.main:app -w 2 -k uvicorn.workers.UvicornWorker` | 退出码 0，未启动服务 |
| `git diff --check` | 通过 |

临时 PG runner 仅位于 `/tmp/uploads-db-runner.py`，由现有 `scripts/test_database.py` 复制并更换 backend 绝对路径和模块 pattern；未提交。其每次创建并清理独立集群、数据库和 socket，仅监听 Unix socket；数据库名称/角色遵守项目测试目标保护。

真实 SQL 覆盖：三种格式上传/读取/元数据和权限；10 MiB 精确上限；绑定 CSRF/撤销会话；提交阶段失败后的事务回滚及文件清理；8 个并发上传互不覆盖；UUID 碰撞保留旧文件与记录；孤文件/未知 ID；篡改存储键、符号链接、硬链接和不安全文件权限拒绝。

## 集成提示与验证边界

- 集成方负责 main 路由挂载、adminApi `uploadFile`、AdminApp 模块入口、统一 runner 与权威文档；本线均未修改。
- `UPLOAD_DIR` 必须注入当前 worktree 外的专用持久目录。严格拒绝任何路径组件的符号链接；macOS 的 `/tmp`、`/var` 是链接，注入时应使用实际的 `/private/tmp`、`/private/var` 路径或对目标执行 realpath。只有合法图片通过校验后才首次建立目录。
- 后端用独立 FastAPI 测试应用挂载上传 router，测试真实登录 Cookie 和真实临时库。没有启动 HTTP 服务端口。
- 浏览器真实 FormData 上传、主入口集成、桌面/窄屏显示、真实反向代理、生产目录和部署尚未验证，交由集成阶段验收。
- 未承诺文件系统与数据库在进程崩溃时原子提交；孤文件不能通过读取接口公开。清理失败的底层存储故障不可能由应用保证物理删除。
- 没有再次委派子 agent；独立审查按共同合同由集成方执行。
- production 规则和原项目 README 已读取；原项目与 worktree 根均不存在项目级 `AGENTS.md`。遵守已提供的用户规则及 production 目录规则；本线只写交付报告，权威文档由集成方独占同步。
