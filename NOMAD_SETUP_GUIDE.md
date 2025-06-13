# OpenHands Nomad Runtime 完整配置和操作手册

本手册将指导您完成OpenHands与Nomad runtime的完整配置和部署，包括环境准备、配置设置、启动任务等所有步骤。

## 目录

1. [环境准备](#环境准备)
2. [Nomad集群部署](#nomad集群部署)
3. [OpenHands配置](#openhands配置)
4. [GPU支持配置](#gpu支持配置)
5. [启动和运行](#启动和运行)
6. [故障排除](#故障排除)
7. [高级配置](#高级配置)

## 环境准备

### 系统要求

- **操作系统**: Linux (推荐 Ubuntu 20.04+, CentOS 8+)
- **内存**: 最少 4GB，推荐 8GB+
- **CPU**: 最少 2核，推荐 4核+
- **存储**: 最少 20GB 可用空间
- **网络**: 稳定的网络连接

### 必需软件安装

#### 1. Docker 安装

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release

# 添加Docker官方GPG密钥
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 设置稳定版仓库
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# 启动Docker服务
sudo systemctl start docker
sudo systemctl enable docker

# 将当前用户添加到docker组
sudo usermod -aG docker $USER
```

#### 2. Python 环境

```bash
# 安装Python 3.12+
sudo apt-get install -y python3.12 python3.12-pip python3.12-venv

# 或使用pyenv安装
curl https://pyenv.run | bash
pyenv install 3.12.0
pyenv global 3.12.0
```

#### 3. Node.js (如需前端)

```bash
# 安装Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

## Nomad集群部署

### 单节点Nomad部署 (开发/测试)

#### 1. 安装Nomad

```bash
# 下载Nomad
NOMAD_VERSION="1.7.2"
wget https://releases.hashicorp.com/nomad/${NOMAD_VERSION}/nomad_${NOMAD_VERSION}_linux_amd64.zip

# 解压并安装
unzip nomad_${NOMAD_VERSION}_linux_amd64.zip
sudo mv nomad /usr/local/bin/
sudo chmod +x /usr/local/bin/nomad

# 验证安装
nomad version
```

#### 2. 创建Nomad配置

```bash
# 创建配置目录
sudo mkdir -p /etc/nomad.d
sudo mkdir -p /opt/nomad/data

# 创建基本配置文件
sudo tee /etc/nomad.d/nomad.hcl > /dev/null <<EOF
datacenter = "dc1"
data_dir = "/opt/nomad/data"
log_level = "INFO"
server_join_retry_max = 3

server {
  enabled = true
  bootstrap_expect = 1
}

client {
  enabled = true
  
  # 允许Docker驱动
  options {
    "driver.allowlist" = "docker"
  }
}

# Docker驱动配置
plugin "docker" {
  config {
    allow_privileged = true
    volumes {
      enabled = true
    }
  }
}

# GPU支持 (如果有GPU)
plugin "nvidia-gpu" {
  config {
    enabled = true
    ignore_topology = false
  }
}

# UI配置
ui_config {
  enabled = true
}

# 网络配置
bind_addr = "0.0.0.0"
ports {
  http = 4646
  rpc  = 4647
  serf = 4648
}
EOF
```

#### 3. 配置Docker for GPU (可选)

如果您需要GPU支持，需要配置NVIDIA Docker运行时：

```bash
# 安装NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 配置Docker daemon
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  },
  "default-runtime": "runc"
}
EOF

# 重启Docker
sudo systemctl restart docker
```

#### 4. 启动Nomad

```bash
# 创建systemd服务文件
sudo tee /etc/systemd/system/nomad.service > /dev/null <<EOF
[Unit]
Description=Nomad
Documentation=https://www.nomadproject.io/
Requires=network-online.target
After=network-online.target
ConditionFileNotEmpty=/etc/nomad.d/nomad.hcl

[Service]
Type=notify
User=root
Group=root
ExecStart=/usr/local/bin/nomad agent -config=/etc/nomad.d/nomad.hcl
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=process
Restart=on-failure
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

# 启动Nomad服务
sudo systemctl daemon-reload
sudo systemctl enable nomad
sudo systemctl start nomad

# 检查状态
sudo systemctl status nomad
nomad node status
```

### 多节点Nomad集群部署

#### Server节点配置

```bash
# Server节点配置 (/etc/nomad.d/server.hcl)
sudo tee /etc/nomad.d/server.hcl > /dev/null <<EOF
datacenter = "dc1"
data_dir = "/opt/nomad/data"
log_level = "INFO"

server {
  enabled = true
  bootstrap_expect = 3  # 服务器节点数量
  
  # 集群加密
  encrypt = "your-encryption-key-here"
}

# 绑定地址
bind_addr = "{{ GetInterfaceIP \"eth0\" }}"

# ACL配置 (生产环境推荐)
acl {
  enabled = true
}

ui_config {
  enabled = true
}
EOF
```

#### Client节点配置

```bash
# Client节点配置 (/etc/nomad.d/client.hcl)
sudo tee /etc/nomad.d/client.hcl > /dev/null <<EOF
datacenter = "dc1"
data_dir = "/opt/nomad/data"
log_level = "INFO"

client {
  enabled = true
  
  # 服务器地址
  servers = ["server1:4647", "server2:4647", "server3:4647"]
  
  options {
    "driver.allowlist" = "docker"
  }
  
  # 节点元数据
  meta {
    "node_type" = "worker"
    "gpu_enabled" = "true"  # 如果支持GPU
  }
}

plugin "docker" {
  config {
    allow_privileged = true
    volumes {
      enabled = true
    }
  }
}

# GPU支持
plugin "nvidia-gpu" {
  config {
    enabled = true
    ignore_topology = false
  }
}

bind_addr = "{{ GetInterfaceIP \"eth0\" }}"
EOF
```

## OpenHands配置

### 1. 安装OpenHands

```bash
# 克隆仓库
git clone https://github.com/Ycpljl/OpenHands.git
cd OpenHands

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -e .

# 或使用Poetry
curl -sSL https://install.python-poetry.org | python3 -
poetry install
```

### 2. 基础配置文件

创建配置文件 `config.toml`:

```toml
[core]
# 使用Nomad运行时
runtime = "nomad"

[sandbox]
# Nomad集群配置
nomad_address = "http://localhost:4646"  # Nomad API地址
# nomad_token = "your-nomad-token"       # ACL token (如果启用了ACL)
# nomad_namespace = "openhands"          # Nomad命名空间
# nomad_datacenter = "dc1"               # 数据中心

# 资源分配
nomad_cpu = 2000      # CPU (MHz)
nomad_memory = 4096   # 内存 (MB)

# 容器镜像
runtime_container_image = "ghcr.io/all-hands-ai/runtime:latest"

# GPU支持 (可选)
enable_gpu = false
# nomad_gpu_count = 1
# nomad_gpu_type = "nvidia/gpu"

# 环境变量
[sandbox.runtime_startup_env_vars]
# 自定义环境变量
# CUSTOM_VAR = "value"

[llm]
# LLM配置
model = "gpt-4"
api_key = "your-openai-api-key"
# base_url = "https://api.openai.com/v1"

[agent]
# Agent配置
name = "CodeActAgent"
# memory_enabled = true
```

### 3. GPU配置文件 (可选)

如果需要GPU支持，创建 `config-gpu.toml`:

```toml
[core]
runtime = "nomad"

[sandbox]
# Nomad配置
nomad_address = "http://localhost:4646"
nomad_cpu = 4000      # GPU工作负载需要更多CPU
nomad_memory = 8192   # GPU工作负载需要更多内存

# GPU配置
enable_gpu = true
nomad_gpu_count = 1                    # GPU数量
nomad_gpu_type = "nvidia/tesla-v100"   # 特定GPU类型

# GPU优化的容器镜像
runtime_container_image = "tensorflow/tensorflow:latest-gpu"

[sandbox.runtime_startup_env_vars]
# GPU环境变量
CUDA_VISIBLE_DEVICES = "all"
TF_FORCE_GPU_ALLOW_GROWTH = "true"

[llm]
model = "gpt-4"
api_key = "your-openai-api-key"

[agent]
name = "CodeActAgent"
```

### 4. 环境变量配置

创建 `.env` 文件:

```bash
# OpenAI配置
OPENAI_API_KEY=your-openai-api-key

# Nomad配置
NOMAD_ADDR=http://localhost:4646
NOMAD_TOKEN=your-nomad-token  # 如果启用了ACL

# 其他配置
WORKSPACE_BASE=/tmp/openhands_workspace
```

## GPU支持配置

### 1. 验证GPU环境

```bash
# 检查NVIDIA驱动
nvidia-smi

# 检查Docker GPU支持
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# 检查Nomad GPU检测
nomad node status -verbose
```

### 2. GPU节点配置

确保Nomad客户端节点正确配置了GPU支持：

```bash
# 检查Nomad节点GPU资源
nomad node status -verbose | grep -A 10 "Device Group"

# 应该看到类似输出：
# Device Group: "nvidia/gpu"
#   Vendor:    nvidia
#   Type:      gpu
#   Name:      NVIDIA GeForce RTX 3080
```

### 3. GPU作业测试

创建测试作业 `gpu-test.nomad`:

```hcl
job "gpu-test" {
  datacenters = ["dc1"]
  type = "batch"

  group "gpu-group" {
    count = 1

    task "gpu-task" {
      driver = "docker"

      config {
        image = "nvidia/cuda:11.0-base"
        command = "nvidia-smi"
        runtime = "nvidia"
      }

      resources {
        cpu    = 500
        memory = 1024

        device "nvidia/gpu" {
          count = 1
        }
      }
    }
  }
}
```

运行测试：

```bash
nomad job run gpu-test.nomad
nomad job status gpu-test
nomad alloc logs <allocation-id>
```

## 启动和运行

### 1. 验证环境

```bash
# 检查Nomad状态
nomad node status
nomad server members

# 检查Docker
docker ps
docker images

# 检查OpenHands
python -c "import openhands; print('OpenHands installed successfully')"
```

### 2. 启动OpenHands

#### 命令行方式

```bash
# 基础启动
python -m openhands.cli.main \
  --config-file config.toml \
  --task "创建一个简单的Python脚本来计算斐波那契数列"

# GPU启动
python -m openhands.cli.main \
  --config-file config-gpu.toml \
  --task "使用TensorFlow创建一个简单的神经网络"

# 指定工作目录
python -m openhands.cli.main \
  --config-file config.toml \
  --workspace-dir /path/to/workspace \
  --task "分析这个项目的代码结构"
```

#### Web界面方式

```bash
# 启动Web服务器
python -m openhands.server.main \
  --config-file config.toml \
  --port 3000

# 访问 http://localhost:3000
```

#### Docker方式

```bash
# 构建OpenHands镜像
docker build -t openhands:latest .

# 运行OpenHands
docker run -it --rm \
  -v $(pwd)/config.toml:/app/config.toml \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e NOMAD_ADDR=http://host.docker.internal:4646 \
  openhands:latest \
  python -m openhands.cli.main \
  --config-file /app/config.toml \
  --task "你的任务描述"
```

### 3. 监控和日志

#### Nomad监控

```bash
# 查看作业状态
nomad job status

# 查看节点状态
nomad node status

# 查看分配状态
nomad alloc status <allocation-id>

# 查看日志
nomad alloc logs <allocation-id>

# 实时日志
nomad alloc logs -f <allocation-id>
```

#### OpenHands日志

```bash
# 查看OpenHands日志
tail -f ~/.openhands/logs/openhands.log

# 或在代码中启用调试日志
import logging
logging.getLogger('openhands.runtime.impl.nomad').setLevel(logging.DEBUG)
```

### 4. 示例任务

#### 基础编程任务

```bash
python -m openhands.cli.main \
  --config-file config.toml \
  --task "创建一个Python脚本，实现以下功能：
1. 读取CSV文件
2. 进行数据清洗
3. 生成统计报告
4. 保存结果到新文件"
```

#### 机器学习任务 (GPU)

```bash
python -m openhands.cli.main \
  --config-file config-gpu.toml \
  --task "使用PyTorch创建一个图像分类模型：
1. 加载CIFAR-10数据集
2. 定义CNN模型
3. 训练模型
4. 评估性能
5. 保存训练好的模型"
```

#### Web开发任务

```bash
python -m openhands.cli.main \
  --config-file config.toml \
  --task "创建一个Flask Web应用：
1. 用户注册和登录功能
2. 数据库集成
3. RESTful API
4. 前端界面
5. 部署配置"
```

## 故障排除

### 常见问题

#### 1. Nomad连接失败

```bash
# 检查Nomad服务状态
sudo systemctl status nomad

# 检查网络连接
curl http://localhost:4646/v1/status/leader

# 检查防火墙
sudo ufw status
sudo iptables -L
```

#### 2. Docker权限问题

```bash
# 添加用户到docker组
sudo usermod -aG docker $USER
newgrp docker

# 重启Docker服务
sudo systemctl restart docker
```

#### 3. GPU不可用

```bash
# 检查NVIDIA驱动
nvidia-smi

# 检查Docker GPU支持
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# 重启Nomad客户端
sudo systemctl restart nomad
```

#### 4. 内存不足

```bash
# 检查系统资源
free -h
df -h

# 调整Nomad配置
# 在nomad.hcl中减少资源分配
```

#### 5. 网络端口冲突

```bash
# 检查端口占用
netstat -tlnp | grep :4646

# 修改Nomad端口配置
# 在nomad.hcl中修改ports配置
```

### 调试技巧

#### 1. 启用详细日志

```bash
# Nomad详细日志
nomad agent -config=/etc/nomad.d/nomad.hcl -log-level=DEBUG

# OpenHands调试模式
export OPENHANDS_DEBUG=true
python -m openhands.cli.main --config-file config.toml --task "test"
```

#### 2. 检查作业规范

```bash
# 验证作业规范
nomad job validate job.nomad

# 计划作业 (不运行)
nomad job plan job.nomad
```

#### 3. 资源监控

```bash
# 系统资源
htop
iotop

# Docker资源
docker stats

# Nomad资源
nomad node status -verbose
```

## 高级配置

### 1. ACL安全配置

#### 启用ACL

```bash
# 在nomad.hcl中启用ACL
acl {
  enabled = true
}

# 重启Nomad
sudo systemctl restart nomad

# 引导ACL系统
nomad acl bootstrap
```

#### 创建策略和令牌

```bash
# 创建策略文件
cat > openhands-policy.hcl <<EOF
namespace "default" {
  policy = "write"
}

node {
  policy = "read"
}

agent {
  policy = "read"
}
EOF

# 创建策略
nomad acl policy apply openhands-policy openhands-policy.hcl

# 创建令牌
nomad acl token create -name="openhands-token" -policy="openhands-policy"
```

### 2. 多数据中心配置

```bash
# 数据中心1配置
datacenter = "dc1"
region = "global"

# 数据中心2配置
datacenter = "dc2"
region = "global"

# 跨数据中心作业
job "multi-dc-job" {
  datacenters = ["dc1", "dc2"]
  # ...
}
```

### 3. 服务发现集成

```bash
# Consul集成
consul {
  address = "127.0.0.1:8500"
  server_service_name = "nomad"
  client_service_name = "nomad-client"
  auto_advertise = true
  server_auto_join = true
  client_auto_join = true
}
```

### 4. 监控集成

#### Prometheus监控

```bash
# 在nomad.hcl中启用telemetry
telemetry {
  collection_interval = "1s"
  disable_hostname = true
  prometheus_metrics = true
  publish_allocation_metrics = true
  publish_node_metrics = true
}
```

#### Grafana仪表板

```bash
# 导入Nomad Grafana仪表板
# Dashboard ID: 3314
```

### 5. 备份和恢复

```bash
# 备份Nomad状态
nomad operator snapshot save backup.snap

# 恢复Nomad状态
nomad operator snapshot restore backup.snap
```

## 生产环境建议

### 1. 安全配置

- 启用ACL认证
- 使用TLS加密
- 配置防火墙规则
- 定期更新系统和软件

### 2. 高可用配置

- 部署多个Server节点 (奇数个)
- 使用负载均衡器
- 配置数据备份
- 监控和告警

### 3. 性能优化

- 合理分配资源
- 使用SSD存储
- 优化网络配置
- 监控资源使用

### 4. 运维自动化

- 使用Infrastructure as Code
- 自动化部署脚本
- 监控和告警系统
- 日志聚合和分析

## 总结

通过本手册，您应该能够：

1. ✅ 成功部署Nomad集群
2. ✅ 配置OpenHands使用Nomad runtime
3. ✅ 启动和运行OpenHands任务
4. ✅ 配置GPU支持 (如需要)
5. ✅ 监控和故障排除
6. ✅ 进行高级配置和优化

如果遇到问题，请参考故障排除部分或查看相关日志文件。

## 支持和帮助

- OpenHands文档: https://docs.all-hands.dev/
- Nomad文档: https://www.nomadproject.io/docs
- GitHub Issues: https://github.com/Ycpljl/OpenHands/issues

祝您使用愉快！