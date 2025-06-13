# OpenHands Nomad Runtime 完整指南

欢迎使用OpenHands Nomad Runtime！这是一个完整的配置和使用指南，帮助您快速上手并充分利用Nomad集群的强大功能。

## 📋 文档目录

| 文档 | 描述 | 适用场景 |
|------|------|----------|
| [快速启动指南](./QUICK_START.md) | 10分钟快速配置 | 新手入门、快速测试 |
| [完整配置手册](./NOMAD_SETUP_GUIDE.md) | 详细的安装和配置指南 | 生产环境、深度定制 |
| [本文档](./NOMAD_README.md) | 概览和最佳实践 | 了解全貌、选择方案 |

## 🚀 三种安装方式

### 方式1: 一键自动安装 (推荐)

```bash
# 基础安装
curl -fsSL https://raw.githubusercontent.com/Ycpljl/OpenHands/feat/add-nomad-runtime-plugin/scripts/setup-nomad-runtime.sh | bash

# GPU支持安装
./scripts/setup-nomad-runtime.sh --gpu

# 多节点集群安装
./scripts/setup-nomad-runtime.sh --multi-node
```

### 方式2: 快速手动安装

参考 [快速启动指南](./QUICK_START.md) 进行手动安装。

### 方式3: 完整定制安装

参考 [完整配置手册](./NOMAD_SETUP_GUIDE.md) 进行详细配置。

## 🎯 功能特性

### ✅ 核心功能

- **容器编排**: 基于HashiCorp Nomad的强大容器编排
- **资源管理**: 精确的CPU、内存资源分配
- **高可用性**: 支持多节点集群和故障转移
- **安全性**: ACL认证、TLS加密、命名空间隔离
- **监控**: 完整的作业监控和日志管理

### ✅ GPU支持

- **灵活配置**: 可配置GPU数量和类型
- **多GPU支持**: 支持分配多个GPU
- **类型约束**: 支持特定GPU型号选择
- **自动配置**: 自动配置NVIDIA Docker运行时
- **环境变量**: 自动设置GPU相关环境变量

### ✅ 企业级特性

- **多数据中心**: 支持跨数据中心部署
- **服务发现**: 集成Consul服务发现
- **负载均衡**: 智能作业调度和负载均衡
- **备份恢复**: 完整的数据备份和恢复机制

## 📊 架构概览

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   OpenHands     │    │  Nomad Cluster  │    │ Docker Runtime  │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │    Agent    │ │───▶│ │   Server    │ │───▶│ │ Container 1 │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │Configuration│ │    │ │   Client    │ │    │ │ Container 2 │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔧 配置选项

### 基础配置

```toml
[core]
runtime = "nomad"

[sandbox]
# Nomad集群配置
nomad_address = "http://localhost:4646"
nomad_token = "your-nomad-token"          # 可选
nomad_namespace = "openhands"             # 可选
nomad_datacenter = "dc1"                  # 可选

# 资源分配
nomad_cpu = 2000                          # CPU (MHz)
nomad_memory = 4096                       # 内存 (MB)

# 容器配置
runtime_container_image = "ghcr.io/all-hands-ai/runtime:latest"
```

### GPU配置

```toml
[sandbox]
# GPU支持
enable_gpu = true
nomad_gpu_count = 2                       # GPU数量
nomad_gpu_type = "nvidia/tesla-v100"      # GPU类型

# GPU优化镜像
runtime_container_image = "tensorflow/tensorflow:latest-gpu"

[sandbox.runtime_startup_env_vars]
CUDA_VISIBLE_DEVICES = "all"
TF_FORCE_GPU_ALLOW_GROWTH = "true"
```

### 高级配置

```toml
[sandbox]
# 网络配置
nomad_network_mode = "bridge"
nomad_port_map = { http = 8080, api = 3000 }

# 存储配置
nomad_volumes = [
  { source = "/host/data", destination = "/container/data", read_only = false }
]

# 约束条件
nomad_constraints = [
  { attribute = "${attr.kernel.name}", operator = "=", value = "linux" }
]
```

## 🎮 使用示例

### 命令行使用

```bash
# 基础任务
python -m openhands.cli.main \
  --config-file config.toml \
  --task "创建一个Python Web应用"

# GPU任务
python -m openhands.cli.main \
  --config-file config-gpu.toml \
  --task "训练一个图像分类模型"

# 指定工作目录
python -m openhands.cli.main \
  --config-file config.toml \
  --workspace-dir /path/to/project \
  --task "分析这个项目的代码"
```

### Web界面使用

```bash
# 启动Web服务器
python -m openhands.server.main \
  --config-file config.toml \
  --port 3000

# 访问 http://localhost:3000
```

### 示例任务脚本

```bash
# 运行预定义的示例任务
./scripts/run-example-tasks.sh basic      # 基础编程任务
./scripts/run-example-tasks.sh ml         # 机器学习任务
./scripts/run-example-tasks.sh system     # 系统管理任务
./scripts/run-example-tasks.sh api        # API开发任务
./scripts/run-example-tasks.sh all        # 所有任务
```

## 📈 监控和管理

### Nomad UI

访问 `http://localhost:4646` 查看：
- 集群状态
- 作业列表
- 资源使用情况
- 节点信息
- 分配详情

### 命令行监控

```bash
# 查看集群状态
nomad node status

# 查看作业状态
nomad job status

# 查看作业详情
nomad job status <job-name>

# 查看实时日志
nomad alloc logs -f <allocation-id>

# 查看资源使用
nomad node status -verbose
```

### 日志管理

```bash
# Nomad服务日志
sudo journalctl -u nomad -f

# OpenHands日志
tail -f ~/.openhands/logs/openhands.log

# 容器日志
docker logs <container-id>
```

## 🔒 安全最佳实践

### 1. 启用ACL认证

```bash
# 引导ACL系统
nomad acl bootstrap

# 创建策略
nomad acl policy apply openhands-policy policy.hcl

# 创建令牌
nomad acl token create -name="openhands" -policy="openhands-policy"
```

### 2. 配置TLS加密

```bash
# 生成CA证书
nomad tls ca create

# 生成服务器证书
nomad tls cert create -server

# 生成客户端证书
nomad tls cert create -client
```

### 3. 网络安全

```bash
# 配置防火墙
sudo ufw allow 4646/tcp  # Nomad HTTP
sudo ufw allow 4647/tcp  # Nomad RPC
sudo ufw allow 4648/tcp  # Nomad Serf
```

## 🚀 性能优化

### 1. 资源调优

```toml
# 根据工作负载调整资源
nomad_cpu = 4000      # 高CPU任务
nomad_memory = 8192   # 高内存任务

# GPU工作负载
enable_gpu = true
nomad_gpu_count = 2
```

### 2. 存储优化

```bash
# 使用SSD存储
data_dir = "/ssd/nomad/data"

# 配置tmpfs
mount -t tmpfs -o size=2G tmpfs /tmp/nomad-tmp
```

### 3. 网络优化

```toml
# 使用host网络模式
nomad_network_mode = "host"

# 配置端口映射
nomad_port_map = { app = 8080 }
```

## 🔧 故障排除

### 常见问题

| 问题 | 症状 | 解决方案 |
|------|------|----------|
| Nomad连接失败 | 无法连接到Nomad API | 检查Nomad服务状态和网络 |
| Docker权限错误 | Permission denied | 添加用户到docker组 |
| GPU不可用 | GPU未检测到 | 检查NVIDIA驱动和Docker配置 |
| 内存不足 | 作业调度失败 | 调整资源分配或增加节点 |
| 端口冲突 | 服务启动失败 | 检查端口占用情况 |

### 调试技巧

```bash
# 启用详细日志
export OPENHANDS_DEBUG=true
export NOMAD_LOG_LEVEL=DEBUG

# 检查作业规范
nomad job validate job.nomad
nomad job plan job.nomad

# 监控资源使用
htop
docker stats
nomad node status -verbose
```

## 📚 学习资源

### 官方文档

- [OpenHands文档](https://docs.all-hands.dev/)
- [Nomad文档](https://www.nomadproject.io/docs)
- [Docker文档](https://docs.docker.com/)

### 社区资源

- [OpenHands GitHub](https://github.com/All-Hands-AI/OpenHands)
- [Nomad GitHub](https://github.com/hashicorp/nomad)
- [HashiCorp Learn](https://learn.hashicorp.com/nomad)

### 示例项目

- [Nomad示例](https://github.com/hashicorp/nomad/tree/main/demo)
- [OpenHands示例](./examples/)

## 🤝 贡献和支持

### 报告问题

如果遇到问题，请：

1. 查看[故障排除](#故障排除)部分
2. 搜索现有的[GitHub Issues](https://github.com/Ycpljl/OpenHands/issues)
3. 创建新的Issue并提供详细信息

### 贡献代码

欢迎贡献代码！请：

1. Fork仓库
2. 创建功能分支
3. 提交Pull Request
4. 确保通过所有测试

### 获取帮助

- GitHub Issues: 技术问题和bug报告
- Discussions: 使用问题和功能讨论
- 文档: 查看完整的配置和使用指南

## 🎉 开始使用

现在您已经了解了OpenHands Nomad Runtime的全貌，选择适合您的安装方式开始使用吧：

1. **快速体验**: 使用[快速启动指南](./QUICK_START.md)
2. **生产部署**: 参考[完整配置手册](./NOMAD_SETUP_GUIDE.md)
3. **示例学习**: 运行`./scripts/run-example-tasks.sh`

祝您使用愉快！🚀

---

**版本**: 1.0.0  
**更新时间**: 2025-06-13  
**维护者**: OpenHands Team