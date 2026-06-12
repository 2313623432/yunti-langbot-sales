# 云梯 AI 销售系统 Railway 部署说明

## 方案

Railway 上使用一个应用服务承载：

- LangBot 主后端
- 已构建进镜像的 `web/dist` 前端
- Plugin Runtime
- `/app/data` 持久化目录

数据库使用 Railway 托管 PostgreSQL。这样前端、后端、数据库都在同一个 Railway Project 内。

## 创建 Railway Project

1. 登录 Railway。
2. 创建一个 Empty Project。
3. 添加 PostgreSQL 数据库服务。
4. 从 GitHub 添加本仓库作为应用服务。

Railway 会读取仓库根目录的 `railway.json`，用根目录 `Dockerfile` 构建镜像，并执行：

```bash
sh scripts/railway/start.sh
```

## 应用服务设置

在应用服务的 Settings 中：

- 生成 Public Domain。
- 添加 Volume，Mount Path 设置为：

```text
/app/data
```

Volume 用来保存 `data/config.yaml`、插件数据、本地上传文件等运行期数据。

## 环境变量

应用服务至少需要：

```text
TZ=Asia/Shanghai
PYTHONUTF8=1
PYTHONIOENCODING=utf-8
```

如果应用服务已经能读取 Railway PostgreSQL 提供的 `DATABASE_URL`，启动脚本会自动切换到 PostgreSQL。

如果没有自动注入 `DATABASE_URL`，在应用服务 Variables 中手动设置：

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

其中 `Postgres` 是 Railway 中 PostgreSQL 服务的名称；如果你的数据库服务名称不同，按 Railway 变量引用提示选择对应变量。

启动脚本还会自动设置：

```text
API__PORT=$PORT
PLUGIN__RUNTIME_WS_URL=ws://127.0.0.1:5400/control/ws
API__WEBHOOK_PREFIX=https://$RAILWAY_PUBLIC_DOMAIN
```

如果你绑定自定义域名，建议手动覆盖：

```text
API__WEBHOOK_PREFIX=https://你的域名
```

## 验证

部署成功后打开：

```text
https://你的 Railway 域名/healthz
```

返回下面内容表示后端可用：

```json
{"code":0,"msg":"ok"}
```

然后访问 Railway 域名根路径，确认前端页面可打开。

## 注意事项

- 不要把本地 `data/`、`.env`、数据库文件、客户资料提交到 GitHub。
- Railway 的 Volume 只在运行时可用，不参与 Docker build。
- 第一次启动会在 `/app/data` 下生成 `config.yaml` 和实例文件。
- 如果后续需要迁移数据，先备份 Railway Volume 和 PostgreSQL。
