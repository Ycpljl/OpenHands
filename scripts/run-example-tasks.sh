#!/bin/bash

# OpenHands Nomad Runtime 示例任务脚本
# 用法: ./run-example-tasks.sh [task-type]

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# 检查配置文件
check_config() {
    if [[ ! -f "config.toml" ]]; then
        log_warning "未找到config.toml，请先运行安装脚本或手动创建配置文件"
        exit 1
    fi
    
    if ! grep -q "api_key.*=" config.toml || grep -q "your-openai-api-key" config.toml; then
        log_warning "请在config.toml中设置您的OpenAI API密钥"
        echo "编辑config.toml文件，将'your-openai-api-key'替换为您的实际API密钥"
        exit 1
    fi
}

# 检查Nomad状态
check_nomad() {
    if ! command -v nomad &> /dev/null; then
        log_warning "Nomad未安装，请先运行安装脚本"
        exit 1
    fi
    
    if ! nomad node status &> /dev/null; then
        log_warning "Nomad未运行，请启动Nomad服务"
        echo "运行: sudo systemctl start nomad"
        echo "或开发模式: nomad agent -config=/etc/nomad.d/nomad.hcl -dev"
        exit 1
    fi
}

# 基础编程任务
run_basic_tasks() {
    log_info "运行基础编程任务..."
    
    # 任务1: Hello World
    log_info "任务1: 创建Hello World程序"
    python -m openhands.cli.main \
        --config-file config.toml \
        --task "创建一个Python脚本，打印'Hello, OpenHands with Nomad!'，并保存为hello.py文件"
    
    log_success "任务1完成"
    
    # 任务2: 数据处理
    log_info "任务2: 数据处理脚本"
    python -m openhands.cli.main \
        --config-file config.toml \
        --task "创建一个Python脚本来处理CSV数据：
1. 生成包含100行随机数据的CSV文件（包含姓名、年龄、城市列）
2. 读取CSV文件并进行数据分析
3. 计算平均年龄和城市分布
4. 生成统计报告并保存为report.txt"
    
    log_success "任务2完成"
    
    # 任务3: Web应用
    log_info "任务3: 简单Web应用"
    python -m openhands.cli.main \
        --config-file config.toml \
        --task "创建一个Flask Web应用：
1. 包含首页、关于页面和联系页面
2. 使用Bootstrap美化界面
3. 添加简单的表单处理
4. 包含静态文件（CSS、JS）
5. 创建requirements.txt文件"
    
    log_success "任务3完成"
}

# 机器学习任务
run_ml_tasks() {
    log_info "运行机器学习任务..."
    
    # 检查GPU配置
    if [[ -f "config-gpu.toml" ]]; then
        CONFIG_FILE="config-gpu.toml"
        log_info "使用GPU配置文件"
    else
        CONFIG_FILE="config.toml"
        log_warning "未找到GPU配置，使用CPU模式"
    fi
    
    # 任务1: 数据科学分析
    log_info "任务1: 数据科学分析"
    python -m openhands.cli.main \
        --config-file "$CONFIG_FILE" \
        --task "创建一个数据科学项目：
1. 使用pandas生成模拟的销售数据
2. 进行数据清洗和预处理
3. 创建数据可视化图表（使用matplotlib/seaborn）
4. 进行统计分析和趋势预测
5. 生成完整的分析报告"
    
    log_success "任务1完成"
    
    # 任务2: 机器学习模型
    log_info "任务2: 机器学习模型"
    python -m openhands.cli.main \
        --config-file "$CONFIG_FILE" \
        --task "创建一个机器学习项目：
1. 使用scikit-learn加载iris数据集
2. 进行数据探索和可视化
3. 训练多个分类模型（决策树、随机森林、SVM）
4. 比较模型性能
5. 保存最佳模型
6. 创建预测脚本"
    
    log_success "任务2完成"
    
    # 任务3: 深度学习 (如果有GPU)
    if [[ "$CONFIG_FILE" == "config-gpu.toml" ]]; then
        log_info "任务3: 深度学习模型"
        python -m openhands.cli.main \
            --config-file "$CONFIG_FILE" \
            --task "创建一个深度学习项目：
1. 使用TensorFlow/Keras构建CNN模型
2. 加载CIFAR-10数据集
3. 设计和训练图像分类模型
4. 验证GPU是否被正确使用
5. 评估模型性能
6. 保存训练好的模型
7. 创建推理脚本"
        
        log_success "任务3完成"
    fi
}

# 系统管理任务
run_system_tasks() {
    log_info "运行系统管理任务..."
    
    # 任务1: 系统监控
    log_info "任务1: 系统监控脚本"
    python -m openhands.cli.main \
        --config-file config.toml \
        --task "创建一个系统监控脚本：
1. 监控CPU、内存、磁盘使用率
2. 检查网络连接状态
3. 监控重要服务状态
4. 生成系统健康报告
5. 支持邮件告警功能
6. 创建定时任务配置"
    
    log_success "任务1完成"
    
    # 任务2: 日志分析
    log_info "任务2: 日志分析工具"
    python -m openhands.cli.main \
        --config-file config.toml \
        --task "创建一个日志分析工具：
1. 解析Apache/Nginx访问日志
2. 统计访问量、IP地址、用户代理
3. 识别异常访问模式
4. 生成可视化报告
5. 支持实时监控模式
6. 创建配置文件"
    
    log_success "任务2完成"
}

# API开发任务
run_api_tasks() {
    log_info "运行API开发任务..."
    
    # 任务1: RESTful API
    log_info "任务1: RESTful API服务"
    python -m openhands.cli.main \
        --config-file config.toml \
        --task "创建一个RESTful API服务：
1. 使用FastAPI框架
2. 实现用户管理API（CRUD操作）
3. 添加JWT认证
4. 集成SQLite数据库
5. 添加API文档（Swagger）
6. 实现数据验证和错误处理
7. 创建Docker配置文件"
    
    log_success "任务1完成"
    
    # 任务2: 微服务
    log_info "任务2: 微服务架构"
    python -m openhands.cli.main \
        --config-file config.toml \
        --task "创建一个微服务项目：
1. 设计用户服务和订单服务
2. 使用Flask/FastAPI实现服务
3. 添加服务间通信（HTTP/gRPC）
4. 实现服务发现机制
5. 添加健康检查端点
6. 创建Docker Compose配置
7. 添加监控和日志"
    
    log_success "任务2完成"
}

# 自动化任务
run_automation_tasks() {
    log_info "运行自动化任务..."
    
    # 任务1: CI/CD流水线
    log_info "任务1: CI/CD流水线"
    python -m openhands.cli.main \
        --config-file config.toml \
        --task "创建CI/CD流水线配置：
1. 创建GitHub Actions工作流
2. 实现自动化测试
3. 添加代码质量检查
4. 配置自动部署
5. 添加通知机制
6. 创建多环境配置
7. 实现回滚策略"
    
    log_success "任务1完成"
    
    # 任务2: 基础设施即代码
    log_info "任务2: 基础设施即代码"
    python -m openhands.cli.main \
        --config-file config.toml \
        --task "创建基础设施即代码项目：
1. 使用Terraform配置云资源
2. 创建Ansible playbook
3. 配置Kubernetes部署文件
4. 实现自动化部署脚本
5. 添加监控和告警配置
6. 创建备份和恢复策略
7. 文档化部署流程"
    
    log_success "任务2完成"
}

# 显示帮助信息
show_help() {
    echo "OpenHands Nomad Runtime 示例任务脚本"
    echo
    echo "用法: $0 [task-type]"
    echo
    echo "任务类型:"
    echo "  basic      - 基础编程任务 (Python脚本、Web应用等)"
    echo "  ml         - 机器学习任务 (数据科学、ML模型、深度学习)"
    echo "  system     - 系统管理任务 (监控、日志分析等)"
    echo "  api        - API开发任务 (RESTful API、微服务等)"
    echo "  automation - 自动化任务 (CI/CD、基础设施即代码等)"
    echo "  all        - 运行所有任务类型"
    echo
    echo "示例:"
    echo "  $0 basic      # 运行基础编程任务"
    echo "  $0 ml         # 运行机器学习任务"
    echo "  $0 all        # 运行所有任务"
    echo
    echo "注意: 请确保已正确配置config.toml文件中的API密钥"
}

# 主函数
main() {
    if [[ $# -eq 0 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
        show_help
        exit 0
    fi
    
    check_config
    check_nomad
    
    case "$1" in
        basic)
            run_basic_tasks
            ;;
        ml)
            run_ml_tasks
            ;;
        system)
            run_system_tasks
            ;;
        api)
            run_api_tasks
            ;;
        automation)
            run_automation_tasks
            ;;
        all)
            log_info "运行所有任务类型..."
            run_basic_tasks
            run_ml_tasks
            run_system_tasks
            run_api_tasks
            run_automation_tasks
            log_success "所有任务完成！"
            ;;
        *)
            echo "错误: 未知的任务类型 '$1'"
            echo "运行 '$0 --help' 查看可用选项"
            exit 1
            ;;
    esac
    
    log_success "任务执行完成！"
    echo
    echo "您可以："
    echo "1. 查看生成的文件和代码"
    echo "2. 在Nomad UI中监控作业状态: http://localhost:4646"
    echo "3. 查看OpenHands日志了解详细信息"
    echo "4. 运行其他任务类型继续探索"
}

# 运行主函数
main "$@"