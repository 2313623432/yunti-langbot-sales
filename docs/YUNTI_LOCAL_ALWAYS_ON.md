# 云梯 AI 销售系统本机常驻上线

## 适用场景

用当前 Windows 电脑作为服务器，电脑保持开机和联网，通过免费 Cloudflare 临时隧道把 `5300` 服务暴露到公网。

固定对外地址：

```text
https://yunti-ai-sales-online.vercel.app
```

启动脚本会在 Cloudflare 临时隧道变化后，后台自动更新 Vercel 代理，让对外地址保持不变。

## 启动

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\start-yunti-online.ps1
```

如果需要重建公网临时地址：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\start-yunti-online.ps1 -RestartTunnel
```

如果只启动本机隧道，不更新 Vercel：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\start-yunti-online.ps1 -SkipVercelUpdate
```

## 停止

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\stop-yunti-online.ps1
```

## 开机自启

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\install-yunti-startup.ps1
```

## 重要说明

- 免费临时隧道的 `trycloudflare.com` 地址在重启隧道后可能变化，但 Vercel 固定地址会自动更新转发目标。
- 为了加快开机上线速度，Vercel 代理更新在后台执行；电脑刚登录后的几十秒内，固定地址可能还在切换中。
- 企业微信、飞书等平台的回调地址优先填写固定 Vercel 地址。
- 如果要固定公网地址，需要绑定自己的域名并创建 Cloudflare Named Tunnel。
- 电脑休眠、关机、断网后，线上系统会不可用。
