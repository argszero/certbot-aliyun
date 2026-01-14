# certbot-aliyun 快速开始指南

## 5分钟快速开始

### 前提条件
#### 使用 Docker（推荐）
- Docker 和 Docker Compose
- 阿里云账号和访问密钥
- 阿里云域名管理权限

#### 不使用 Docker（不推荐）
- Python 3.8+
- certbot（需手动安装，参考：https://certbot.eff.org）
- 阿里云账号和访问密钥
- 阿里云域名管理权限

### 步骤 1: 克隆项目
```bash
git clone https://github.com/argszero/certbot-aliyun.git
cd certbot-aliyun
```

### 步骤 2: 配置环境变量
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件
nano .env
```

配置示例：
```bash
# 阿里云凭证
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou

# 证书配置
CERT_DOMAINS=example.com,*.example.com
CERT_EMAIL=admin@example.com
CERT_STAGING=true  # 测试时设为 true
CERT_VALIDATION_METHOD=alidns  # 阿里云 DNS 自动验证

# SLB/ALB 配置 (可选)
SLB_INSTANCE_ID=alb-xxxxxx
SLB_LISTENER_ID=lsr-yyyyyy
```

### 步骤 3: 使用 Docker 申请证书
```bash
# 构建 Docker 镜像
docker build -t certbot-aliyun:dev .

# 申请证书
docker run --rm \
  -v $(pwd)/.env:/app/.env:ro \
  -v $(pwd)/certs:/app/certs \
  -v $(pwd)/certbot-config:/app/certbot-config \
  certbot-aliyun:dev apply-cert
```

### 步骤 5: 使用 Docker Compose (推荐)
```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 申请证书
docker-compose exec certbot-aliyun apply-cert

# 更新 SLB 证书
docker-compose exec certbot-aliyun update-slb-cert
```

## 验证方法选择

### 1. 阿里云 DNS 自动验证 (推荐)
```bash
CERT_VALIDATION_METHOD=alidns
```
- 支持通配符证书
- 完全自动化
- 需要阿里云 DNS 权限

### 2. 手动 DNS 验证
```bash
CERT_VALIDATION_METHOD=manual
```
- 支持通配符证书
- 需要手动添加 TXT 记录
- 适合测试环境

### 3. HTTP 验证
```bash
CERT_VALIDATION_METHOD=standalone
```
- 自动验证
- 不支持通配符证书
- 需要开放 80/443 端口

## 生产环境部署

### Docker Swarm 部署
```bash
# 初始化 Swarm
docker swarm init

# 创建 Docker secrets
echo "your_access_key_id" | docker secret create alibaba_cloud_access_key_id -
echo "your_access_key_secret" | docker secret create alibaba_cloud_access_key_secret -
echo "admin@example.com" | docker secret create cert_email -

# 部署服务
docker stack deploy -c docker-swarm.yml certbot-aliyun
```

### 定时任务配置
```bash
# 使用 cron 模式自动续订和更新SLB证书（默认每12小时）
docker run -d --name certbot-aliyun \
  -e ALIBABA_CLOUD_ACCESS_KEY_ID=xxx \
  -e ALIBABA_CLOUD_ACCESS_KEY_SECRET=yyy \
  -e CERT_DOMAINS="example.com,*.example.com" \
  -e CERT_EMAIL="admin@example.com" \
  -e CERT_VALIDATION_METHOD=alidns \
  -e CRON_INTERVAL_HOURS=12 \  # 可选：配置执行间隔（小时）
  -v $(pwd)/certs:/app/certs \
  -v $(pwd)/certbot-config:/app/certbot-config \
  certbot-aliyun:dev cron

# 或者使用Docker Compose（推荐）
# 在.env文件中添加 CRON_INTERVAL_HOURS=24 可调整执行间隔
docker-compose up -d
```

## 证书管理

### 查看证书信息
```bash
# 查看证书文件
ls -la certs/

# 查看证书详情
cat certs/certificate_info.json
```

### 手动续订证书
```bash
docker-compose exec certbot-aliyun renew-cert
```

### 更新 SLB 证书
```bash
docker-compose exec certbot-aliyun update-slb-cert
```

## 故障排除

### 常见问题

1. **证书申请失败**
   ```bash
   # 查看详细日志
   docker-compose logs certbot-aliyun

   # 检查 DNS 配置
   dig TXT _acme-challenge.example.com
   ```

2. **阿里云 API 错误**
   ```bash
   # 检查访问密钥
   echo $ALIBABA_CLOUD_ACCESS_KEY_ID

   # 检查区域配置
   echo $ALIBABA_CLOUD_REGION_ID
   ```

3. **Docker 权限问题**
   ```bash
   # 修复目录权限
   sudo chown -R 1000:1000 certs certbot-config
   ```

### 调试模式
```bash
# 启用调试日志
export LOG_LEVEL=DEBUG

# 重新启动服务
docker-compose up -d
```

## 下一步

### 学习更多
- [配置参考](docs/configuration.md) - 所有配置选项
- [部署指南](docs/deployment.md) - 生产环境部署
- [API 文档](docs/api.md) - 开发接口说明

### 扩展功能
- 多域名证书管理
- 监控和告警
- 备份和恢复
- Kubernetes 部署

### 获取帮助
- [GitHub Issues](https://github.com/argszero/certbot-aliyun/issues) - 报告问题
- [Discussions](https://github.com/argszero/certbot-aliyun/discussions) - 技术讨论
- [文档](https://argszero.github.io/certbot-aliyun) - 完整文档