# certbot-aliyun 🚀

**阿里云 Let's Encrypt 自动化证书工具**

基于 Docker 的 Let's Encrypt 证书自动化管理解决方案，支持通配符证书和阿里云 SLB/ALB 自动部署。

## ✨ 功能特性

- **🚀 自动化证书管理**: 完整的 Let's Encrypt 证书生命周期管理
- **🔐 通配符证书支持**: 支持 `*.example.com` 通配符证书
- **☁️ 阿里云深度集成**: 原生支持阿里云 DNS、SLB、ALB
- **🐳 Docker 优先设计**: 专为 Docker、Docker Compose 和 Docker Swarm 设计
- **⏰ 定时自动续订**: 可配置的证书自动续订计划
- **🔧 多种验证方式**: DNS-01（阿里云 DNS）、HTTP-01、手动验证
- **📦 生产就绪**: 非 root 用户运行、健康检查、完善日志

## 📦 快速开始

查看 [QUICKSTART.md](QUICKSTART.md) 获取 5 分钟快速入门指南。

### 使用 Docker
```bash
# 构建镜像
docker build -t certbot-aliyun:dev .

# 申请证书
docker run --rm \
  -e ALIBABA_CLOUD_ACCESS_KEY_ID=你的AccessKey \
  -e ALIBABA_CLOUD_ACCESS_KEY_SECRET=你的AccessSecret \
  -e CERT_DOMAINS="example.com,*.example.com" \
  -e CERT_EMAIL="admin@example.com" \
  -e CERT_VALIDATION_METHOD=alidns \
  -v $(pwd)/certs:/app/certs \
  -v $(pwd)/certbot-config:/app/certbot-config \
  certbot-aliyun:dev apply-cert
```

### 使用 Docker Compose
```bash
# 启动服务
docker-compose up -d

# 申请证书
docker-compose exec certbot-aliyun apply-cert
```

## 🔧 配置说明

### 环境变量
基于 `.env.example` 创建 `.env` 文件：

```bash
# 阿里云凭证
ALIBABA_CLOUD_ACCESS_KEY_ID=你的AccessKeyID
ALIBABA_CLOUD_ACCESS_KEY_SECRET=你的AccessKeySecret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou

# 证书配置
CERT_DOMAINS=example.com,*.example.com
CERT_EMAIL=admin@example.com
CERT_STAGING=false
CERT_VALIDATION_METHOD=alidns  # manual, dns-route53, alidns, standalone

# SLB/ALB 配置（可选）
SLB_INSTANCE_ID=alb-xxxxxx
SLB_LISTENER_ID=lsr-yyyyyy
SLB_LISTENER_PROTOCOL=https
```

### 验证方式对比
| 方式 | 说明 | 通配符支持 | 自动化程度 |
|------|------|------------|------------|
| `alidns` | 阿里云 DNS 自动验证 | ✅ 支持 | ✅ 全自动 |
| `manual` | 手动 DNS 验证（显示 TXT 记录） | ✅ 支持 | ❌ 需手动操作 |
| `standalone` | HTTP 验证（80 端口） | ❌ 不支持 | ✅ 全自动 |

## 🐳 Docker 使用

### 可用命令
```bash
# 显示帮助
docker run certbot-aliyun:dev help

# 显示版本
docker run certbot-aliyun:dev version

# 申请证书
docker run certbot-aliyun:dev apply-cert

# 续订证书
docker run certbot-aliyun:dev renew-cert

# 更新 SLB/ALB 证书
docker run certbot-aliyun:dev update-slb-cert

# 定时任务模式（自动续订和更新SLB证书）
docker run certbot-aliyun:dev cron

# 可以通过环境变量配置执行间隔（小时）
docker run -e CRON_INTERVAL_HOURS=24 certbot-aliyun:dev cron
```

### Docker Compose 配置
```yaml
# 完整配置见 docker-compose.yml
version: '3.8'
services:
  certbot-aliyun:
    build: .
    environment:
      - ALIBABA_CLOUD_ACCESS_KEY_ID=${ALIBABA_CLOUD_ACCESS_KEY_ID}
      - ALIBABA_CLOUD_ACCESS_KEY_SECRET=${ALIBABA_CLOUD_ACCESS_KEY_SECRET}
      - CERT_DOMAINS=${CERT_DOMAINS}
      - CERT_EMAIL=${CERT_EMAIL}
    volumes:
      - ./certs:/app/certs
      - ./certbot-config:/app/certbot-config
    command: help
```

## 📚 文档

- [快速开始指南](QUICKSTART.md) - 5 分钟快速入门

## 🏗️ 项目结构

```
certbot-aliyun/
├── auto_cert/                 # Python 核心代码
│   ├── config.py             # 配置管理
│   ├── apply_cert.py         # 证书申请
│   ├── renew_cert.py         # 证书续订
│   ├── update_slb_cert.py    # SLB/ALB 证书更新
│   └── dns_alidns.py         # 阿里云 DNS 插件
├── Dockerfile                # Docker 镜像定义（多阶段构建）
├── docker-entrypoint.sh      # Docker 容器入口点
├── docker-compose.yml        # Docker Compose 开发配置
├── .env.example              # 环境变量配置模板
├── .dockerignore            # Docker 构建忽略文件
├── .gitignore               # Git 忽略文件
├── .gitattributes           # Git 文件属性配置
├── pyproject.toml           # Python 项目配置
├── uv.lock                  # Python 依赖锁文件
├── README.md                # 项目说明文档
└── QUICKSTART.md            # 快速开始指南

# 注意：以下目录不应提交到版本控制
# certs/                    # 证书存储目录（本地）
# certbot-config/           # Certbot 配置目录（本地）
# .env                      # 环境变量文件（包含敏感信息）
```

## 🔄 开发指南

### 本地开发环境（不使用 Docker）
```bash
# 克隆仓库
git clone https://github.com/argszero/certbot-aliyun.git
cd certbot-aliyun

# 安装 certbot（如果需要）
./setup-certbot.sh

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -e .
```

### 运行测试
```bash
# 安装测试依赖
pip install -e .[dev]

# 运行测试
pytest
```

### 构建 Docker 镜像
```bash
# 构建开发镜像
docker build -t certbot-aliyun:dev .

# 测试镜像
docker run --rm certbot-aliyun:dev version
```

## 📝 文件说明

### 核心文件
- **`Dockerfile`** - Docker 镜像定义，多阶段构建优化大小
- **`docker-entrypoint.sh`** - 容器入口点，支持多种运行模式
- **`auto_cert/`** - Python 核心代码，包含证书管理逻辑
- **`pyproject.toml`** - Python 项目配置和依赖定义

### 配置文件
- **`.env.example`** - 环境变量模板，复制为 `.env` 后配置
- **`.dockerignore`** - Docker 构建忽略文件，优化构建过程
- **`.gitignore`** - Git 忽略文件，防止提交敏感数据

### 辅助脚本
- **`docker-compose.yml`** - Docker Compose 开发环境配置

### 文档
- **`README.md`** - 项目详细说明（本文档）
- **`QUICKSTART.md`** - 5分钟快速开始指南

## 🤝 贡献指南

欢迎贡献！

1. Fork 项目仓库
2. 创建功能分支
3. 提交你的修改
4. 添加测试用例
5. 提交 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详情请见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- [Let's Encrypt](https://letsencrypt.org/) - 提供免费的 SSL/TLS 证书
- [Certbot](https://certbot.eff.org/) - ACME 客户端
- [阿里云](https://www.alibabacloud.com/) - 云服务支持

## 📞 支持

- 📖 [快速开始指南](QUICKSTART.md)
- 🐛 [问题跟踪](https://github.com/argszero/certbot-aliyun/issues)
- 💬 [讨论区](https://github.com/argszero/certbot-aliyun/discussions)

---

**为阿里云社区精心打造 ❤️**

如果觉得这个项目有用，请在 GitHub 上给它一个 ⭐！