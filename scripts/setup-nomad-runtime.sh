#!/bin/bash

# OpenHands Nomad Runtime 快速安装脚本
# 用法: ./setup-nomad-runtime.sh [--gpu] [--multi-node]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "请不要以root用户运行此脚本"
        exit 1
    fi
}

# 检查操作系统
check_os() {
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        log_error "此脚本仅支持Linux系统"
        exit 1
    fi
    
    if ! command -v apt-get &> /dev/null && ! command -v yum &> /dev/null; then
        log_error "不支持的Linux发行版，请手动安装"
        exit 1
    fi
}

# 解析命令行参数
GPU_SUPPORT=false
MULTI_NODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --gpu)
            GPU_SUPPORT=true
            shift
            ;;
        --multi-node)
            MULTI_NODE=true
            shift
            ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo "选项:"
            echo "  --gpu        启用GPU支持"
            echo "  --multi-node 配置多节点集群"
            echo "  -h, --help   显示帮助信息"
            exit 0
            ;;
        *)
            log_error "未知选项: $1"
            exit 1
            ;;
    esac
done

# 安装Docker
install_docker() {
    log_info "安装Docker..."
    
    if command -v docker &> /dev/null; then
        log_success "Docker已安装"
        return
    fi
    
    # 检测发行版
    if command -v apt-get &> /dev/null; then
        # Ubuntu/Debian
        sudo apt-get update
        sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
        
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        
        echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        sudo apt-get update
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io
    elif command -v yum &> /dev/null; then
        # CentOS/RHEL
        sudo yum install -y yum-utils
        sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        sudo yum install -y docker-ce docker-ce-cli containerd.io
    fi
    
    # 启动Docker服务
    sudo systemctl start docker
    sudo systemctl enable docker
    
    # 添加用户到docker组
    sudo usermod -aG docker $USER
    
    log_success "Docker安装完成"
}

# 安装NVIDIA Docker支持
install_nvidia_docker() {
    if [[ "$GPU_SUPPORT" != "true" ]]; then
        return
    fi
    
    log_info "安装NVIDIA Docker支持..."
    
    # 检查NVIDIA驱动
    if ! command -v nvidia-smi &> /dev/null; then
        log_error "未检测到NVIDIA驱动，请先安装NVIDIA驱动"
        exit 1
    fi
    
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
    
    # 测试GPU支持
    if docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi &> /dev/null; then
        log_success "NVIDIA Docker支持安装完成"
    else
        log_error "NVIDIA Docker支持安装失败"
        exit 1
    fi
}

# 安装Nomad
install_nomad() {
    log_info "安装Nomad..."
    
    if command -v nomad &> /dev/null; then
        log_success "Nomad已安装"
        return
    fi
    
    NOMAD_VERSION="1.7.2"
    
    # 下载Nomad
    wget -q https://releases.hashicorp.com/nomad/${NOMAD_VERSION}/nomad_${NOMAD_VERSION}_linux_amd64.zip
    
    # 解压并安装
    unzip -q nomad_${NOMAD_VERSION}_linux_amd64.zip
    sudo mv nomad /usr/local/bin/
    sudo chmod +x /usr/local/bin/nomad
    
    # 清理
    rm nomad_${NOMAD_VERSION}_linux_amd64.zip
    
    # 验证安装
    if nomad version &> /dev/null; then
        log_success "Nomad安装完成"
    else
        log_error "Nomad安装失败"
        exit 1
    fi
}

# 配置Nomad
configure_nomad() {
    log_info "配置Nomad..."
    
    # 创建目录
    sudo mkdir -p /etc/nomad.d
    sudo mkdir -p /opt/nomad/data
    
    # 生成配置文件
    if [[ "$MULTI_NODE" == "true" ]]; then
        configure_nomad_cluster
    else
        configure_nomad_single
    fi
    
    # 创建systemd服务
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
    
    log_success "Nomad配置完成"
}

# 单节点Nomad配置
configure_nomad_single() {
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
  
  options {
    "driver.allowlist" = "docker"
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

$(if [[ "$GPU_SUPPORT" == "true" ]]; then
cat <<EOG
plugin "nvidia-gpu" {
  config {
    enabled = true
    ignore_topology = false
  }
}
EOG
fi)

ui_config {
  enabled = true
}

bind_addr = "0.0.0.0"
ports {
  http = 4646
  rpc  = 4647
  serf = 4648
}
EOF
}

# 多节点Nomad配置
configure_nomad_cluster() {
    log_info "配置多节点Nomad集群..."
    
    echo "请选择节点类型:"
    echo "1) Server节点"
    echo "2) Client节点"
    read -p "请输入选择 (1-2): " node_type
    
    case $node_type in
        1)
            configure_nomad_server
            ;;
        2)
            configure_nomad_client
            ;;
        *)
            log_error "无效选择"
            exit 1
            ;;
    esac
}

# Server节点配置
configure_nomad_server() {
    read -p "请输入Server节点数量 (推荐3或5): " server_count
    read -p "请输入加密密钥 (可选，回车跳过): " encrypt_key
    
    sudo tee /etc/nomad.d/nomad.hcl > /dev/null <<EOF
datacenter = "dc1"
data_dir = "/opt/nomad/data"
log_level = "INFO"

server {
  enabled = true
  bootstrap_expect = ${server_count}
  $(if [[ -n "$encrypt_key" ]]; then echo "encrypt = \"$encrypt_key\""; fi)
}

bind_addr = "{{ GetInterfaceIP \"eth0\" }}"

ui_config {
  enabled = true
}

ports {
  http = 4646
  rpc  = 4647
  serf = 4648
}
EOF
}

# Client节点配置
configure_nomad_client() {
    read -p "请输入Server节点地址 (格式: server1:4647,server2:4647): " server_addresses
    
    # 转换地址格式
    IFS=',' read -ra ADDR <<< "$server_addresses"
    servers_array=""
    for addr in "${ADDR[@]}"; do
        servers_array="$servers_array\"$addr\", "
    done
    servers_array=${servers_array%, }  # 移除最后的逗号和空格
    
    sudo tee /etc/nomad.d/nomad.hcl > /dev/null <<EOF
datacenter = "dc1"
data_dir = "/opt/nomad/data"
log_level = "INFO"

client {
  enabled = true
  
  servers = [$servers_array]
  
  options {
    "driver.allowlist" = "docker"
  }
  
  meta {
    "node_type" = "worker"
    $(if [[ "$GPU_SUPPORT" == "true" ]]; then echo "\"gpu_enabled\" = \"true\""; fi)
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

$(if [[ "$GPU_SUPPORT" == "true" ]]; then
cat <<EOG
plugin "nvidia-gpu" {
  config {
    enabled = true
    ignore_topology = false
  }
}
EOG
fi)

bind_addr = "{{ GetInterfaceIP \"eth0\" }}"
EOF
}

# 启动Nomad服务
start_nomad() {
    log_info "启动Nomad服务..."
    
    sudo systemctl daemon-reload
    sudo systemctl enable nomad
    sudo systemctl start nomad
    
    # 等待服务启动
    sleep 5
    
    if sudo systemctl is-active --quiet nomad; then
        log_success "Nomad服务启动成功"
    else
        log_error "Nomad服务启动失败"
        sudo systemctl status nomad
        exit 1
    fi
}

# 安装Python依赖
install_python_deps() {
    log_info "安装Python依赖..."
    
    # 检查Python版本
    if ! python3 --version | grep -q "3.1[2-9]"; then
        log_warning "建议使用Python 3.12+版本"
    fi
    
    # 安装pip
    if ! command -v pip3 &> /dev/null; then
        if command -v apt-get &> /dev/null; then
            sudo apt-get install -y python3-pip
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3-pip
        fi
    fi
    
    log_success "Python环境准备完成"
}

# 创建OpenHands配置
create_openhands_config() {
    log_info "创建OpenHands配置文件..."
    
    # 基础配置
    cat > config.toml <<EOF
[core]
runtime = "nomad"

[sandbox]
nomad_address = "http://localhost:4646"
nomad_cpu = 2000
nomad_memory = 4096
runtime_container_image = "ghcr.io/all-hands-ai/runtime:latest"

$(if [[ "$GPU_SUPPORT" == "true" ]]; then
cat <<EOG
enable_gpu = true
nomad_gpu_count = 1
nomad_gpu_type = "nvidia/gpu"
EOG
fi)

[llm]
model = "gpt-4"
# api_key = "your-openai-api-key"

[agent]
name = "CodeActAgent"
EOF
    
    # GPU配置
    if [[ "$GPU_SUPPORT" == "true" ]]; then
        cat > config-gpu.toml <<EOF
[core]
runtime = "nomad"

[sandbox]
nomad_address = "http://localhost:4646"
nomad_cpu = 4000
nomad_memory = 8192
enable_gpu = true
nomad_gpu_count = 1
nomad_gpu_type = "nvidia/tesla-v100"
runtime_container_image = "tensorflow/tensorflow:latest-gpu"

[sandbox.runtime_startup_env_vars]
CUDA_VISIBLE_DEVICES = "all"
TF_FORCE_GPU_ALLOW_PROGRESS = "true"

[llm]
model = "gpt-4"
# api_key = "your-openai-api-key"

[agent]
name = "CodeActAgent"
EOF
        log_success "GPU配置文件已创建: config-gpu.toml"
    fi
    
    # 环境变量文件
    cat > .env <<EOF
# OpenAI配置
# OPENAI_API_KEY=your-openai-api-key

# Nomad配置
NOMAD_ADDR=http://localhost:4646
# NOMAD_TOKEN=your-nomad-token

# 工作目录
WORKSPACE_BASE=/tmp/openhands_workspace
EOF
    
    log_success "配置文件已创建: config.toml, .env"
}

# 验证安装
verify_installation() {
    log_info "验证安装..."
    
    # 检查Docker
    if ! docker ps &> /dev/null; then
        log_error "Docker未正常运行"
        return 1
    fi
    
    # 检查Nomad
    if ! nomad node status &> /dev/null; then
        log_error "Nomad未正常运行"
        return 1
    fi
    
    # 检查GPU (如果启用)
    if [[ "$GPU_SUPPORT" == "true" ]]; then
        if ! nomad node status -verbose | grep -q "nvidia/gpu"; then
            log_warning "GPU未在Nomad中检测到"
        fi
    fi
    
    log_success "安装验证完成"
}

# 显示后续步骤
show_next_steps() {
    log_success "安装完成！"
    echo
    echo "后续步骤:"
    echo "1. 重新登录以应用Docker组权限: newgrp docker"
    echo "2. 编辑配置文件设置API密钥: nano config.toml"
    echo "3. 安装OpenHands: git clone https://github.com/Ycpljl/OpenHands.git && cd OpenHands && pip install -e ."
    echo "4. 运行测试任务:"
    echo "   python -m openhands.cli.main --config-file config.toml --task '创建一个Hello World程序'"
    echo
    echo "Web界面访问: http://localhost:4646 (Nomad UI)"
    echo
    echo "配置文件位置:"
    echo "- OpenHands配置: ./config.toml"
    if [[ "$GPU_SUPPORT" == "true" ]]; then
        echo "- GPU配置: ./config-gpu.toml"
    fi
    echo "- 环境变量: ./.env"
    echo "- Nomad配置: /etc/nomad.d/nomad.hcl"
    echo
    echo "有用的命令:"
    echo "- 查看Nomad状态: nomad node status"
    echo "- 查看Nomad作业: nomad job status"
    echo "- 查看Nomad日志: sudo journalctl -u nomad -f"
    echo "- 重启Nomad: sudo systemctl restart nomad"
}

# 主函数
main() {
    log_info "开始安装OpenHands Nomad Runtime..."
    
    check_root
    check_os
    
    install_docker
    install_nvidia_docker
    install_nomad
    configure_nomad
    start_nomad
    install_python_deps
    create_openhands_config
    verify_installation
    show_next_steps
}

# 运行主函数
main "$@"