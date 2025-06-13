# OpenHands Nomad Runtime 快速启动指南

这是一个简化的快速启动指南，帮助您在10分钟内配置好OpenHands和Nomad runtime。

## 🚀 一键安装脚本

### 基础安装 (无GPU)

```bash
# 下载并运行安装脚本
curl -fsSL https://raw.githubusercontent.com/Ycpljl/OpenHands/feat/add-nomad-runtime-plugin/scripts/setup-nomad-runtime.sh | bash

# 或者手动下载
wget https://raw.githubusercontent.com/Ycpljl/OpenHands/feat/add-nomad-runtime-plugin/scripts/setup-nomad-runtime.sh
chmod +x setup-nomad-runtime.sh
./setup-nomad-runtime.sh
```

### GPU支持安装

```bash
# 安装带GPU支持的版本
./setup-nomad-runtime.sh --gpu
```

### 多节点集群安装

```bash
# 配置多节点集群
./setup-nomad-runtime.sh --multi-node
```

## 📋 手动安装步骤

如果您喜欢手动控制安装过程：

### 1. 安装依赖

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 安装Python 3.12+
sudo apt install -y python3.12 python3.12-pip python3.12-venv
```

### 2. 安装Nomad

```bash
# 下载Nomad
NOMAD_VERSION="1.7.2"
wget https://releases.hashicorp.com/nomad/${NOMAD_VERSION}/nomad_${NOMAD_VERSION}_linux_amd64.zip
unzip nomad_${NOMAD_VERSION}_linux_amd64.zip
sudo mv nomad /usr/local/bin/
```

### 3. 配置Nomad

```bash
# 创建配置目录
sudo mkdir -p /etc/nomad.d /opt/nomad/data

# 创建配置文件
sudo tee /etc/nomad.d/nomad.hcl > /dev/null <<EOF
datacenter = "dc1"
data_dir = "/opt/nomad/data"

server {
  enabled = true
  bootstrap_expect = 1
}

client {
  enabled = true
  options {
    "driver.allowlist" = "docker"
  }
}

plugin "docker" {
  config {
    allow_privileged = true
    volumes { enabled = true }
  }
}

ui_config { enabled = true }
bind_addr = "0.0.0.0"
EOF

# 启动Nomad
sudo nomad agent -config=/etc/nomad.d/nomad.hcl -dev &
```

### 4. 安装OpenHands

```bash
# 克隆仓库
git clone https://github.com/Ycpljl/OpenHands.git
cd OpenHands

# 安装
pip install -e .
```

### 5. 创建配置文件

```bash
# 创建config.toml
cat > config.toml <<EOF
[core]
runtime = "nomad"

[sandbox]
nomad_address = "http://localhost:4646"
nomad_cpu = 2000
nomad_memory = 4096
runtime_container_image = "ghcr.io/all-hands-ai/runtime:latest"

[llm]
model = "gpt-4"
api_key = "your-openai-api-key"  # 替换为您的API密钥

[agent]
name = "CodeActAgent"
EOF
```

## ⚡ 快速测试

### 1. 验证环境

```bash
# 检查Docker
docker ps

# 检查Nomad
nomad node status

# 访问Nomad UI
# 打开浏览器访问: http://localhost:4646
```

### 2. 运行第一个任务

```bash
# 简单测试
python -m openhands.cli.main \
  --config-file config.toml \
  --task "创建一个Python脚本，打印Hello World"

# 更复杂的任务
python -m openhands.cli.main \
  --config-file config.toml \
  --task "创建一个Flask web应用，包含首页和关于页面"
```

### 3. 启动Web界面

```bash
# 启动Web服务器
python -m openhands.server.main --config-file config.toml --port 3000

# 访问: http://localhost:3000
```

## 🎯 GPU支持快速配置

如果您有NVIDIA GPU：

### 1. 安装NVIDIA Docker

```bash
# 安装NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 配置Docker
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  }
}
EOF

sudo systemctl restart docker
```

### 2. 更新Nomad配置

```bash
# 在nomad.hcl中添加GPU插件
sudo tee -a /etc/nomad.d/nomad.hcl > /dev/null <<EOF

plugin "nvidia-gpu" {
  config {
    enabled = true
    ignore_topology = false
  }
}
EOF

# 重启Nomad
sudo pkill nomad
sudo nomad agent -config=/etc/nomad.d/nomad.hcl -dev &
```

### 3. 创建GPU配置

```bash
cat > config-gpu.toml <<EOF
[core]
runtime = "nomad"

[sandbox]
nomad_address = "http://localhost:4646"
nomad_cpu = 4000
nomad_memory = 8192
enable_gpu = true
nomad_gpu_count = 1
nomad_gpu_type = "nvidia/gpu"
runtime_container_image = "tensorflow/tensorflow:latest-gpu"

[llm]
model = "gpt-4"
api_key = "your-openai-api-key"

[agent]
name = "CodeActAgent"
EOF
```

### 4. 测试GPU任务

```bash
python -m openhands.cli.main \
  --config-file config-gpu.toml \
  --task "使用TensorFlow创建一个简单的神经网络，并验证GPU可用性"
```

## 🔧 常用命令

### Nomad管理

```bash
# 查看节点状态
nomad node status

# 查看作业
nomad job status

# 查看作业详情
nomad job status <job-name>

# 查看分配日志
nomad alloc logs <allocation-id>

# 停止作业
nomad job stop <job-name>
```

### OpenHands使用

```bash
# 命令行模式
python -m openhands.cli.main --config-file config.toml --task "您的任务"

# Web模式
python -m openhands.server.main --config-file config.toml

# 指定工作目录
python -m openhands.cli.main --config-file config.toml --workspace-dir /path/to/workspace --task "任务"

# 调试模式
OPENHANDS_DEBUG=true python -m openhands.cli.main --config-file config.toml --task "任务"
```

### 日志查看

```bash
# Nomad日志
sudo journalctl -u nomad -f

# OpenHands日志
tail -f ~/.openhands/logs/openhands.log

# Docker容器日志
docker logs <container-id>
```

## 🚨 故障排除

### 常见问题

1. **Docker权限错误**
   ```bash
   sudo usermod -aG docker $USER
   newgrp docker
   ```

2. **Nomad连接失败**
   ```bash
   # 检查Nomad是否运行
   ps aux | grep nomad
   
   # 检查端口
   netstat -tlnp | grep 4646
   ```

3. **GPU不可用**
   ```bash
   # 检查NVIDIA驱动
   nvidia-smi
   
   # 检查Docker GPU支持
   docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
   ```

4. **内存不足**
   ```bash
   # 减少资源分配
   # 在config.toml中调整nomad_cpu和nomad_memory
   ```

### 重置环境

```bash
# 停止所有Nomad作业
nomad job stop -purge $(nomad job status | grep running | awk '{print $1}')

# 重启Nomad
sudo pkill nomad
sudo nomad agent -config=/etc/nomad.d/nomad.hcl -dev &

# 清理Docker容器
docker system prune -f
```

## 📚 更多资源

- [完整配置手册](./NOMAD_SETUP_GUIDE.md)
- [Nomad文档](https://www.nomadproject.io/docs)
- [OpenHands文档](https://docs.all-hands.dev/)
- [GitHub仓库](https://github.com/Ycpljl/OpenHands)

## 🎉 成功！

如果一切正常，您现在应该能够：

✅ 运行Nomad集群  
✅ 使用OpenHands执行任务  
✅ 通过Web界面交互  
✅ 监控作业状态  
✅ 使用GPU加速 (如果配置)  

开始您的OpenHands之旅吧！🚀