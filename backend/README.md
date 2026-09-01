# 后端开发与运行

后端当前以 Python 3.13 为开发目标。

## 本地开发

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pytest -W error
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8100 --reload
```

配置从仓库根目录 `.env` 读取。`.env` 已被 Git 忽略。生产服务器应使用独立系统用户和权限 `0640` 的环境文件，完整步骤见 `deploy/README.md`。

## 首次建库

生产数据库为空时，由管理员手动执行：

```text
deploy/mysql/create.sql
```

`create.sql` 已同时写入 `alembic_version=0001_initial`，无需也不应再次执行 `alembic stamp`。初始化后应核对：

```sql
SELECT version_num FROM yuepai_example.alembic_version;
```

不要在已有数据的数据库重复执行初始 SQL。后续结构升级统一使用 `alembic upgrade head`，迁移必须保持向后兼容。

## 创建管理员

```bash
python -m app.cli.create_admin
```

密码通过终端交互输入，不存放在 `.env`。新管理员默认不启用 TOTP；登录后台后可在“账户安全”页面生成二维码并使用验证器扫码启用。
