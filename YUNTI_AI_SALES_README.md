# 云梯 AI 销售系统

本仓库基于 LangBot 二次开发，面向云梯科技的 AI 销售场景，提供产品库、客户记忆、意图理解、自动推销、转人工、定时推送和多平台接入能力。

## 在线地址

固定访问地址：

```text
https://yunti-ai-sales-online.vercel.app
```

说明：该地址由 Vercel 代理到本机 Cloudflare 隧道，真正的服务运行在本机 `5300` 端口。电脑关机、断网或休眠时，线上地址会不可用。

## 主要能力

- AI 销售工作台
- 产品库管理
- 客户记忆和会话状态
- 客户意图理解
- 根据产品卖点自动推荐和推销
- 用户说“转人工”后创建人工接入会话
- 人工销售可从后台回复客户
- 支持定时推送产品信息链接
- 支持飞书、企微等平台接入
- 自动登录后台，无需付费登录
- DeepSeek 深度思考内容过滤
- 云梯科技品牌元素

## 本机常驻运行

启动：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\start-yunti-online.ps1
```

停止：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\stop-yunti-online.ps1
```

安装开机自启：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\install-yunti-startup.ps1
```

启动脚本会：

- 检测后端是否已在 `5300` 运行，避免重复启动
- 启动 Cloudflare 临时隧道
- 后台更新 Vercel 固定地址代理
- 保持 `https://yunti-ai-sales-online.vercel.app` 作为外部固定入口

## 生产 Docker 部署

生产 Docker Compose 文件：

```text
docker/docker-compose.prod.yaml
```

部署：

```bash
cd docker
docker compose -f docker-compose.prod.yaml up -d --build
```

注意：不要使用官方默认 `docker/docker-compose.yaml` 上线，因为它会拉取官方镜像，无法包含本仓库的 AI 销售改动。

## 关键目录

```text
src/langbot/pkg/api/http/controller/groups/sales.py
src/langbot/pkg/api/http/service/sales.py
src/langbot/pkg/entity/persistence/sales.py
web/src/app/home/sales/page.tsx
scripts/windows/
deploy/vercel-proxy/
docs/
```

## 安全说明

以下内容不应提交到仓库：

- `.env`
- `data/`
- `temp/`
- `logs/`
- `.vercel/`
- `node_modules/`
- API Key、GitHub Token、平台密钥

如果密钥曾经出现在聊天、日志或命令历史中，建议立即吊销并重新生成。
