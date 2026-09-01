# 摄影预约微信小程序

微信原生 TypeScript 客户端，通过 `https://your-domain.example/api/v1` 访问后端。使用时请替换为自己的 API 地址。

## 已实现

- 服务端 Bootstrap 品牌和政策配置。
- 作品列表、分类、分页和作品详情。
- 微信静默登录及自有 Session Token。
- 动态预约选项、公开档期和三步预约表单。
- 表单草稿、政策版本校验和幂等创建。
- 我的预约、预约详情、修改和取消。
- 个人数据删除申请。
- Loading、Empty、Error 和网络重试状态。

## 开发与发布

1. 使用仓库根目录导入微信开发者工具。
2. 开发阶段可使用当前测试 AppID；联调和提审前替换为最终 AppID。
3. 微信公众平台必须配置你自己的 HTTPS 域名为合法 request 和 downloadFile 域名。
4. 共享 `project.config.json` 已固定基础库 `3.17.0`、开启合法域名校验和上传压缩；本地 private 配置可在开发期关闭校验。
5. 正式上传前将 `project.private.config.json` 中的 `setting.urlCheck` 改为 `true` 或删除该覆盖。
6. 运行 `scripts/check-miniprogram.ps1` 检查结构、公开文案和生产配置。
7. 正式上传前执行真机弱网、会话过期和重复提交回归。

小程序不包含管理入口、管理员认证或管理 API 代码。品牌名称由管理后台维护，客户端仅保留“摄影预约”中性回退。
