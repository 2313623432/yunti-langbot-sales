# 云梯 AI 销售系统正式上线说明

## 适用场景

本项目需要常驻后端、插件运行时、数据库文件和企微/飞书长连接，正式上线建议使用云服务器或支持 Docker Compose 的容器平台。

## 服务器要求

- Linux 服务器，建议 2C4G 起步
- 已安装 Docker 和 Docker Compose
- 安全组开放 `5300`，如需反向连接平台则开放 `2280-2285`
- 域名可选，生产建议用 Nginx/Caddy 做 HTTPS 反向代理

## 部署命令

```bash
git clone <your-repo-url> LangBot
cd LangBot/docker
docker compose -f docker-compose.prod.yaml up -d --build
```

访问：

```text
http://服务器IP:5300
```

## 数据持久化

业务数据挂载在仓库根目录的 `data/`：

- `data/config.yaml`
- `data/database.db`
- `data/plugins/`

更新代码前建议备份 `data/`。

## 更新发布

```bash
cd LangBot
git pull
cd docker
docker compose -f docker-compose.prod.yaml up -d --build
```

## 备注

不要使用 `docker/docker-compose.yaml` 做云梯版本上线；它会拉取官方 `rockchin/langbot:latest` 镜像，无法包含本仓库里的 AI 销售系统改动。
