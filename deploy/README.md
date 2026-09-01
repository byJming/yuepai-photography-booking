# 悦拍生产部署手册

本目录提供部署到自有服务器的示例。所有示例均不包含真实密码、密钥、AppID 或 TOTP Secret。

## 1. 当前部署约定

- API、小程序媒体和管理后台共用域名 `your-domain.example`。
- 管理后台地址为 `https://your-domain.example/admin/`。
- API 仅监听服务器本地 `127.0.0.1:8100`，由 Nginx 反向代理。
- MySQL 监听本地 `127.0.0.1:3306`，数据库和运行账号均为 `yuepai_example`。
- Redis 使用本地 `127.0.0.1:6379` 的 DB 2，无密码；必须保持 Protected Mode 并禁止公网监听。
- 媒体文件位于 `/srv/example-app/media/public`，临时文件位于 `/srv/example-app/media/tmp`。
- 生产配置位于 `/etc/example-app`，不得加入 Git 或发布包。
- 品牌名可先使用“摄影预约”；正式品牌名可在后台修改。正式 AppID 和 AppSecret 必须在发布小程序前替换。

## 2. 生产前置条件

建议使用仍受支持的 Linux 发行版、Python 3.11、Nginx 1.25.1+（启用 HTTP/2 模块）、MySQL 5.7+、Redis、`rsync`、`curl`、`openssl` 和 `tar`。生产环境应选择仍在安全支持期内的具体版本。CentOS 7.9 与 MySQL 5.7 已结束常规支持，只能作为过渡环境，并需要额外系统加固和异地备份。

确认服务器时区：

```bash
timedatectl set-timezone Asia/Shanghai
timedatectl status
```

确认 MySQL 和 Redis 仅监听本地或受控私网地址：

```bash
ss -lntp | grep -E ':(3306|6379)\b'
redis-cli -n 2 ping
```

## 3. 开发机质量检查与构建

在项目根目录执行：

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/python -m ruff check app tests
.venv/bin/python -m mypy app
cd ../admin-web
npm ci
npm test
npm run lint
npm run build
```

Windows 开发机使用对应的 `.venv\Scripts\python.exe`。发布源目录必须至少包含：

```text
backend/
admin-web/dist/
deploy/
```

不要上传本地 `.env`、管理员凭据、测试媒体、`node_modules` 或开发 Virtualenv。

## 4. 域名与 TLS

1. 将 `your-domain.example` 替换为自己的域名并解析到服务器公网 IP。
2. 安全组只开放受控 SSH、80 和 443。
3. 在安装完整 Nginx 配置前，通过 Certbot standalone 或临时 HTTP 配置签发证书。
4. 最终证书路径应与 `deploy/nginx/yuepai.conf` 一致：

```text
/etc/letsencrypt/live/your-domain.example/fullchain.pem
/etc/letsencrypt/live/your-domain.example/privkey.pem
```

启用 HSTS 前必须确认 HTTPS 已稳定可用；配置中的 HSTS 会影响该子域名一年。

## 5. 系统用户与目录

```bash
useradd --system --home-dir /opt/example-app --shell /sbin/nologin example-app || true
install -d -m 0755 /opt/example-app /opt/example-app/releases
install -d -o example-app -g example-app -m 0750 /opt/example-app/shared /opt/example-app/shared/logs /opt/example-app/shared/tmp
install -d -o example-app -g example-app -m 0750 /srv/example-app/media/public /srv/example-app/media/tmp /srv/example-app/backups
install -d -o root -g example-app -m 0750 /etc/example-app
```

## 6. 生产环境变量

复制模板：

```bash
install -o root -g example-app -m 0640 deploy/env/yuepai.env.example /etc/example-app/yuepai.env
install -o root -g example-app -m 0640 deploy/env/backup.env.example /etc/example-app/backup.env
install -o root -g example-app -m 0640 deploy/env/mysql-backup.cnf.example /etc/example-app/mysql-backup.cnf
```

生成独立随机值，不要复用任何管理员密码或数据库密码：

```bash
openssl rand -base64 32   # FIELD_ENCRYPTION_KEY_V1
openssl rand -hex 32      # OPENID_HMAC_KEY
openssl rand -hex 32      # SESSION_TOKEN_PEPPER
openssl rand -hex 32      # ADMIN_SESSION_TOKEN_PEPPER
umask 077
openssl rand -base64 32 > /etc/example-app/backup.key
chown root:example-app /etc/example-app/backup.key
chmod 0640 /etc/example-app/backup.key
```

编辑 `/etc/example-app/yuepai.env`：

- 将 MySQL 密码 URL encode 后填入 `MYSQL_DSN`。可用以下命令安全转换：

```bash
python3 -c 'import getpass; from urllib.parse import quote; print(quote(getpass.getpass("Database password: "), safe=""))'
```

- 正式小程序发布前填入 `WECHAT_APP_ID` 与 `WECHAT_APP_SECRET`。
- `FIELD_ENCRYPTION_KEY_V1` 上线后必须长期安全保存；遗失后无法解密既有敏感数据。
- 四个安全密钥必须彼此独立。
- 保持 `APP_ENV=production`、`REDIS_URL=redis://127.0.0.1:6379/2` 和 `REDIS_KEY_PREFIX=yuepai:prod`。

编辑 `/etc/example-app/mysql-backup.cnf`，填入数据库账号与密码。该文件只用于本机备份和恢复，不出现在命令行参数中。

## 7. 初始化空数据库

`deploy/mysql/create.sql` 已包含：

- 全部表、索引和外键。
- 默认预约选项和暂定品牌设置。
- `policy_content` 等公开政策内容。
- `alembic_version=0001_initial`，保证后续 `alembic upgrade head` 不会重复创建初始表。
- `USE yuepai_example`，执行前仍需再次确认目标实例和空库状态。

手动执行：

```bash
mysql --defaults-extra-file=/etc/example-app/mysql-backup.cnf < deploy/mysql/create.sql
mysql --defaults-extra-file=/etc/example-app/mysql-backup.cnf -e \
  "SELECT version_num FROM yuepai_example.alembic_version; SHOW TABLES FROM yuepai_example;"
```

不要在已有数据的数据库重复执行初始 SQL。后续结构升级统一使用 Alembic。

## 8. 安装 systemd、Nginx 和日志轮转

先在目标服务器验证脚本和 systemd 单元，再安装配置：

```bash
bash -n deploy/scripts/*.sh
systemd-analyze verify deploy/systemd/*.service deploy/systemd/*.timer
```

安装并验证：

```bash
install -o root -g root -m 0644 deploy/systemd/*.service /etc/systemd/system/
install -o root -g root -m 0644 deploy/systemd/*.timer /etc/systemd/system/
install -o root -g root -m 0644 deploy/nginx/yuepai.conf /etc/nginx/conf.d/example-app.conf
install -o root -g root -m 0644 deploy/logrotate/yuepai-nginx /etc/logrotate.d/yuepai-nginx
systemctl daemon-reload
nginx -t
```

若 Nginx 运行用户不是 `nginx`，调整 `deploy/logrotate/yuepai-nginx` 的 `create` 用户和组。

## 9. 首次发布

发布脚本会创建独立 Release、安装 Hash Lock 依赖、运行配置自检、执行 Alembic、原子切换 `current`、启动 API 并执行健康检查。

```bash
bash deploy/scripts/release.sh /path/to/extracted-yuepai-release
systemctl enable yuepai-api.service
systemctl status yuepai-api.service
curl --fail https://your-domain.example/health/live
curl --fail https://your-domain.example/health/ready
```

如果服务器 Python 命令不是 `python3.11`：

```bash
PYTHON_BIN=/custom/path/python3.11 bash deploy/scripts/release.sh /path/to/release
```

当前宝塔 CentOS 7 服务器必须使用兼容 `glibc 2.17` 的专用 Hash Lock：

```bash
/www/server/pyporject_evn/yuepai/bin/python -m pip install \
  --require-hashes \
  -r backend/requirements.centos7.lock
```

生产机应优先安装预构建 Wheel；不要在流量高峰临时编译大型依赖。

## 10. 创建首个管理员

首次发布和建表完成后，在受控 root Shell 中加载环境变量后再切换用户：

```bash
set -a
source /etc/example-app/yuepai.env
set +a
sudo -E -u example-app /opt/example-app/current/.venv/bin/yuepai-create-admin
```

新管理员默认只使用用户名和密码登录。创建后访问后台，在“账户安全”页面生成二维码并使用验证器扫码；启用成功后，登录和修改密码都会强制验证 TOTP：

```text
https://your-domain.example/admin/
```

## 11. 启用定时任务

```bash
systemctl enable --now yuepai-retention.timer
systemctl enable --now yuepai-backup.timer
systemctl enable --now yuepai-healthcheck.timer
systemctl list-timers 'yuepai-*'
```

首次手动验证：

```bash
systemctl start yuepai-retention.service
systemctl start yuepai-backup.service
journalctl -u yuepai-retention.service -n 100 --no-pager
journalctl -u yuepai-backup.service -n 100 --no-pager
```

备份使用 AES-256-GCM 认证加密，保存在 `/srv/example-app/backups/daily`，默认保留 7 天；每周日建立周备份快照，默认保留 35 天。必须再将加密备份复制到服务器之外。

## 12. 恢复演练

先校验摘要：

```bash
cd /srv/example-app/backups/daily/<timestamp>
sha256sum -c SHA256SUMS
```

恢复 MySQL 时必须使用独立测试库，不要直接覆盖生产库：

```bash
export MYSQL_DEFAULTS_FILE=/etc/example-app/mysql-backup.cnf
export BACKUP_ENCRYPTION_KEY_FILE=/etc/example-app/backup.key
RESTORE_CONFIRM=yuepai_example_restore \
  /opt/example-app/current/deploy/scripts/restore-mysql.sh \
  /srv/example-app/backups/daily/<timestamp>/mysql-yuepai_example-<timestamp>.sql.gz.enc \
  yuepai_example_restore
```

恢复媒体到独立空目录：

```bash
export BACKUP_ENCRYPTION_KEY_FILE=/etc/example-app/backup.key
RESTORE_CONFIRM=media \
  /opt/example-app/current/deploy/scripts/restore-media.sh \
  /srv/example-app/backups/daily/<timestamp>/media-public-<timestamp>.tar.gz.enc \
  /srv/example-app/restore-test
```

验证数据库行数、关键预约、媒体 SHA-256 和页面显示后，再制定正式切换方案。每月至少做一次恢复演练。

## 13. 后续发布与回滚

每次发布前先完成三端测试和管理端构建，然后执行：

```bash
bash deploy/scripts/release.sh /path/to/new-release
journalctl -u yuepai-api.service --since '10 minutes ago' --no-pager
```

脚本会在已有版本时先运行一次备份。代码健康检查失败会自动切回旧 Release。人工回滚：

```bash
bash /opt/example-app/current/deploy/scripts/rollback.sh
```

回滚脚本只切换代码，不执行数据库 downgrade。所有数据库迁移应保持向后兼容；禁止在未验证时直接执行破坏性降级。

## 14. 微信公众平台配置

正式 AppID、主体和品牌确认后：

1. 更新 `/etc/example-app/yuepai.env` 的 `WECHAT_APP_ID` 和 `WECHAT_APP_SECRET`，重启 API。
2. 在微信公众平台配置 `request` 合法域名：使用你自己的 HTTPS 域名。
3. 配置媒体下载所需的合法域名：使用你自己的 HTTPS 域名。
4. 上传前将小程序项目 AppID 替换为正式 AppID。
5. 更新隐私保护指引、服务类目、用户协议和隐私政策版本。
6. 使用体验版完成登录、作品列表、预约提交、预约修改/取消和数据删除申请验收。

在正式 AppID 和 AppSecret 未确认前，服务端、小程序页面和后台可以继续开发与部署测试，但真实微信登录和正式提审不能视为完成。

## 15. 上线验收清单

- `nginx -t` 通过，HTTP 自动跳转 HTTPS。
- `/health/live` 与 `/health/ready` 返回 200。
- MySQL、Redis 和 Uvicorn 均未监听公网接口。
- 管理后台密码登录、后台扫码启用 TOTP、启用后强制验证、CSRF、修改密码和退出登录均正常。
- 管理后台可配置作品、选项、未来十二个月档期并完成预约全流程。
- 完整手机号只在预约详情按需显示，敏感查看进入审计日志。
- 小程序使用正式 AppID 后可登录、浏览作品、提交和查询预约。
- 媒体上传后 EXIF 已移除，公开 URL 可访问，临时目录无残留。
- 数据保留、备份和健康检查 Timer 已启用并有成功记录。
- 已完成至少一次 MySQL 和媒体恢复演练。
- 日志不包含 Token、完整手机号、请求 Body 或解密后的备注/地点。
- 服务器外存在可读取的加密备份副本，备份密钥另行保存。
