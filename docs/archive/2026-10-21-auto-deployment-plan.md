# 自动部署接入阶段记录（已归档）

归档日期：2026-10-23。自动部署实现已交付，按用户要求从当前计划转为阶段归档；归档不表示所有验收通过。后台需求与进度见[当前后台计划](../admin-management-plan.md)。

状态（2026-10-23 文档核对）：既有记录证明 2026-10-21 的真实 Actions 手动发布及自动发布开关启用；本轮未连接 GitHub 或服务器，不据此推断当前线上版本、开关或后续自动发布结果。证据集中在[验证记录](../validation-log.md)，日常用法见 [README](../../README.md)。

## 遗留与未确认事项

| 事项 | 已记录的状态与下一步 |
|---|---|
| 合并后自动发布与页面变化 | 首次 push main 发布结果及用户自行验证页面变化，现有文档没有完整确认；核对对应 Actions、版本标记和人工接受。 |
| 真实故障回退 | 离线回退测试通过，真实故障回退和旧站点恢复脚本尚未演练；不能记为真实验收通过。 |
| 合并保护与失败通知 | 主分支必须通过 CI 的保护规则及部署失败通知未核实；CI 成功不等于保护已配置。 |
| 权限细分 | 用户此前接受复用 ubuntu，专用部署账号与权限细分暂缓，不自动纳入本次后台范围。 |
| Git 收尾 | 本地 Git 已包含 PR #7（部署验收文档）与 PR #8（骰子/九宫格）的合并；对应 CI/发布结果和远程分支状态本轮未核对。 |

历史初版、CI 与部署准备步骤已被后续实现替代，必要过程与结果保留在验证记录；原历史授权不当作本轮发布授权。

本文件只保留阶段结论和上述遗留状态；后续若继续处理遗留事项，须明确本次范围与验收并同步索引。不得将归档状态解释为遗留事项已完成。


## 2026-10-25：旧HTTPS操作参考（已被临时上线方案替代）

以下保留此前HTTPS方案的完整操作原文，避免丢失独有步骤。它不是当前生产配置或本轮上线前提，其中版本、current、开关与空库描述只代表当时；将来切回HTTPS前必须根据当时实际环境重新核对，不能整段照抄。现行HTTP前台、同机备份及SSH后台用法见[README](../../README.md)。

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
