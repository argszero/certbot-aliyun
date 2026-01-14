# certbot-aliyun 🚀

**阿里云 Let's Encrypt 自动化证书工具**

基于 Python 的 Let's Encrypt 证书自动化管理解决方案，支持通配符证书和阿里云 SLB/ALB 自动部署。

## ✨ 功能特性

- **🚀 自动化证书管理**: 完整的 Let's Encrypt 证书生命周期管理
- **🔐 通配符证书支持**: 支持 `*.example.com` 通配符证书
- **☁️ 阿里云深度集成**: 原生支持阿里云 DNS、SLB、ALB
- **⏰ 定时自动续订**: 可配置的证书自动续订计划
- **🐍 Python 原生**: 基于 Python 和 uv 包管理器
- **📦 易于部署**: 简单的命令行工具，支持脚本化部署

## 📦 快速开始

### 1. 安装依赖

首先安装必要的工具：

```bash
# 安装 uv (Python 包管理器)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 certbot (Let's Encrypt 客户端)
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install certbot

# CentOS/RHEL
sudo yum install certbot

# macOS (使用 Homebrew)
brew install certbot
```

### 2. 克隆项目并安装 Python 依赖

```bash
# 克隆项目
git clone https://github.com/argszero/certbot-aliyun.git
cd certbot-aliyun

# 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate  # Linux/macOS
# Windows: .venv\Scripts\activate

# 安装项目依赖
uv pip install -e .
```

### 3. 配置环境变量

基于 `.env.example` 创建 `.env` 文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置你的阿里云凭证和证书信息：

```bash
# 阿里云凭证
ALIBABA_CLOUD_ACCESS_KEY_ID=你的AccessKeyID
ALIBABA_CLOUD_ACCESS_KEY_SECRET=你的AccessKeySecret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou

# 证书配置
CERT_DOMAINS=example.com,*.example.com
CERT_EMAIL=admin@example.com
CERT_STAGING=false  # 测试时设为 true，生产环境设为 false
CERT_VALIDATION_METHOD=alidns  # manual, dns-route53, alidns, standalone
```

### 4. 申请证书

```bash
# 使用阿里云 DNS 自动验证（推荐）
uv run python -m auto_cert.apply_cert

# 或者使用手动 DNS 验证
CERT_VALIDATION_METHOD=manual uv run python -m auto_cert.apply_cert
```

### 5. 续订证书

```bash
# 手动续订证书
uv run python -m auto_cert.renew_cert

# 或者配置定时任务自动续订
uv run python -m auto_cert.cron
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
├── .env.example              # 环境变量配置模板
├── .dockerignore            # Docker 构建忽略文件（可选）
├── Dockerfile                # Docker 镜像定义（多阶段构建，可选）
├── docker-entrypoint.sh      # Docker 容器入口点（可选）
├── docker-compose.yml        # Docker Compose 开发配置（可选）
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

### 本地开发环境
```bash
# 克隆仓库
git clone https://github.com/argszero/certbot-aliyun.git
cd certbot-aliyun

# 安装 uv (如果尚未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate  # Linux/macOS
# Windows: .venv\Scripts\activate

# 安装项目依赖
uv pip install -e .
```

### 运行测试
```bash
# 安装测试依赖
uv pip install -e .[dev]

# 运行测试
uv run pytest
```

### 运行开发命令
```bash
# 申请证书（开发测试）
uv run python -m auto_cert.apply_cert

# 续订证书
uv run python -m auto_cert.renew_cert

# 更新 SLB 证书
uv run python -m auto_cert.update_slb_cert
```

## 📝 文件说明

### 核心文件
- **`auto_cert/`** - Python 核心代码，包含证书管理逻辑
- **`pyproject.toml`** - Python 项目配置和依赖定义
- **`uv.lock`** - Python 依赖锁文件，确保环境一致性

### 配置文件
- **`.env.example`** - 环境变量模板，复制为 `.env` 后配置
- **`.gitignore`** - Git 忽略文件，防止提交敏感数据

### Docker 相关文件（可选）
- **`Dockerfile`** - Docker 镜像定义（多阶段构建）
- **`docker-entrypoint.sh`** - 容器入口点
- **`docker-compose.yml`** - Docker Compose 开发环境配置
- **`.dockerignore`** - Docker 构建忽略文件

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