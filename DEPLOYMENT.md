# 云服务器部署说明

## 当前状态

项目已经部署到阿里云服务器，并配置为后台常驻运行。

- 服务器公网 IP：`59.110.160.165`
- 服务器用户：`admin`
- 项目目录：`/home/admin/ai-infra-intel`
- systemd 服务名：`ai-infra-intel`
- Web 访问地址：`http://59.110.160.165:8000/`
- 健康检查：`http://59.110.160.165:8000/api/health`

## 每日自动流程

服务器会一直运行项目，不依赖本地电脑。

每天北京时间：

- `08:00` 自动采集 AI 新闻
- `08:10` 自动抓取正文并分析
- `09:00` 自动生成日报，并推送飞书机器人卡片

定时配置来自 `.env`：

```env
COLLECT_CRON_HOUR=8
COLLECT_CRON_MINUTE=0
REPORT_CRON_HOUR=9
REPORT_CRON_MINUTE=0
TIMEZONE=Asia/Shanghai
```

## 常用服务器命令

查看服务是否运行：

```bash
sudo systemctl status ai-infra-intel --no-pager
```

重启服务：

```bash
sudo systemctl restart ai-infra-intel
```

停止服务：

```bash
sudo systemctl stop ai-infra-intel
```

查看实时日志：

```bash
journalctl -u ai-infra-intel -f
```

测试健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

手动推送最新日报到飞书：

```bash
curl -X POST http://127.0.0.1:8000/api/reports/push-feishu
```

如果开启了网页登录密码：

```bash
curl -u 用户名:密码 -X POST http://127.0.0.1:8000/api/reports/push-feishu
```

## 通过 GitHub 更新服务器代码

项目已经接入 GitHub。后续本地代码推送到 GitHub 后，服务器不需要再上传压缩包。

服务器上执行：

```bash
cd /home/admin/ai-infra-intel
git pull
sudo systemctl restart ai-infra-intel
```

检查服务：

```bash
sudo systemctl status ai-infra-intel --no-pager
curl http://127.0.0.1:8000/api/health
```

如果服务器目录还没有接入 GitHub，先执行一次：

```bash
cd /home/admin/ai-infra-intel
git init
git remote remove origin 2>/dev/null || true
git remote add origin https://github.com/wuziyang233/AI-Infra.git
git fetch origin main
git reset --hard origin/main
sudo systemctl restart ai-infra-intel
```

注意：`.env`、数据库、向量库、日报文件都在 `.gitignore` 中，不会被 GitHub 覆盖。

## 已完成的部署工作

1. 上传本地项目到云服务器 `/home/admin/ai-infra-intel`。
2. 安装 Python 3.11 和项目依赖。
3. 处理服务器 SQLite 版本过低问题，使用 `pysqlite3-binary` 兼容 ChromaDB。
4. 配置飞书机器人 webhook 和签名密钥。
5. 配置 `systemd` 服务，让项目后台常驻并开机自启。
6. 放行服务器 `8000` 端口，用于网页访问。

## 安全提醒

当前 `8000` 端口如果对 `0.0.0.0/0` 开放，任何人都能访问网页。项目目前没有登录鉴权，长期使用建议后续加 Nginx 和访问密码，或把安全组来源 IP 限制为自己的公网 IP。

## Web 登录密码

项目支持通过 `.env` 开启网页登录保护：

```env
WEB_AUTH_USERNAME=admin
WEB_AUTH_PASSWORD=your-strong-password
```

设置后访问网页会进入登录页，API 也会被保护。命令行仍可使用 `curl -u 用户名:密码`。修改 `.env` 后需要重启服务：

```bash
sudo systemctl restart ai-infra-intel
```

## 关闭或恢复定时任务

### 方式 1：临时停掉整个项目

```bash
sudo systemctl stop ai-infra-intel
```

效果：网页打不开，定时任务也不会跑。

恢复：

```bash
sudo systemctl start ai-infra-intel
```

### 方式 2：永久取消开机自启

```bash
sudo systemctl disable ai-infra-intel
sudo systemctl stop ai-infra-intel
```

效果：服务器重启后项目不会自动启动，定时任务也不会跑。

恢复开机自启：

```bash
sudo systemctl enable ai-infra-intel
sudo systemctl start ai-infra-intel
```

### 方式 3：只停定时任务，保留网页

修改服务器上的文件：

```bash
cd /home/admin/ai-infra-intel
vi app/main.py
```

把：

```python
start_scheduler()
```

改成：

```python
# start_scheduler()
```

然后重启：

```bash
sudo systemctl restart ai-infra-intel
```

效果：网页还能访问，手动采集、手动生成日报、手动推送飞书都能用，但每天自动任务不会跑。

如果只是暂时不用，优先用方式 1。如果还想保留网页但不想自动发飞书，用方式 3。
