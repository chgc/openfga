#!/bin/bash
# Prometheus 和 OpenFGA 監控快速部署腳本

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日誌函數
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 檢查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 主菜單
show_menu() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     OpenFGA Prometheus 監控快速部署                           ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    
    echo "選擇操作:"
    echo "  1. 檢查環境準備"
    echo "  2. 部署 Prometheus"
    echo "  3. 部署 MySQL Exporter"
    echo "  4. 部署完整監控棧（1+2+3）"
    echo "  5. 驗證部署"
    echo "  6. 啟動監控工具"
    echo "  7. 卸載監控"
    echo "  0. 退出"
    echo ""
}

# 檢查環境
check_environment() {
    log_info "檢查環境..."
    
    echo ""
    
    # 檢查 kubectl
    if command_exists kubectl; then
        KUBECTL_VERSION=$(kubectl version --client --short 2>/dev/null | awk '{print $3}')
        log_success "kubectl 已安裝: $KUBECTL_VERSION"
    else
        log_error "kubectl 未安裝，請先安裝 kubectl"
        return 1
    fi
    
    # 檢查集群連接
    if kubectl cluster-info &>/dev/null; then
        CLUSTER_NAME=$(kubectl config current-context)
        log_success "已連接到集群: $CLUSTER_NAME"
    else
        log_error "無法連接到 Kubernetes 集群"
        return 1
    fi
    
    # 檢查 namespace
    if kubectl get namespace openfga-prod &>/dev/null; then
        log_success "openfga-prod namespace 已存在"
    else
        log_warn "openfga-prod namespace 不存在，將在部署時創建"
    fi
    
    if kubectl get namespace monitoring &>/dev/null; then
        log_success "monitoring namespace 已存在"
    else
        log_warn "monitoring namespace 不存在，將在部署時創建"
    fi
    
    # 檢查 metrics-server
    if kubectl get deployment metrics-server -n kube-system &>/dev/null; then
        log_success "metrics-server 已安裝"
    else
        log_warn "metrics-server 未安裝（可選）"
    fi
    
    # 檢查存儲類
    if kubectl get storageclass &>/dev/null; then
        STORAGE_CLASSES=$(kubectl get storageclass -o name | wc -l)
        log_success "發現 $STORAGE_CLASSES 個存儲類"
    else
        log_error "未找到存儲類，Prometheus 可能無法持久化數據"
    fi
    
    echo ""
    log_success "環境檢查完成！"
}

# 部署 Prometheus
deploy_prometheus() {
    log_info "部署 Prometheus..."
    
    # 檢查文件
    if [ ! -f "prometheus-deployment.yaml" ]; then
        log_error "prometheus-deployment.yaml 不存在"
        return 1
    fi
    
    log_info "創建 monitoring namespace..."
    kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
    
    log_info "應用 Prometheus 配置..."
    kubectl apply -f prometheus-deployment.yaml
    
    log_info "等待 Prometheus pod 就緒..."
    kubectl wait --for=condition=ready pod \
        -l app=prometheus \
        -n monitoring \
        --timeout=300s \
        2>/dev/null || log_warn "等待超時，pod 仍在啟動中"
    
    log_success "Prometheus 已部署"
    
    # 顯示訪問信息
    echo ""
    echo -e "${YELLOW}訪問 Prometheus UI:${NC}"
    echo "  kubectl port-forward -n monitoring svc/prometheus 9090:9090"
    echo "  然後訪問 http://localhost:9090"
}

# 部署 MySQL Exporter
deploy_mysql_exporter() {
    log_info "部署 MySQL Exporter..."
    
    # 檢查文件
    if [ ! -f "mysql-exporter-deployment.yaml" ]; then
        log_error "mysql-exporter-deployment.yaml 不存在"
        return 1
    fi
    
    log_info "檢查 openfga-prod namespace..."
    kubectl create namespace openfga-prod --dry-run=client -o yaml | kubectl apply -f -
    
    log_info "應用 MySQL Exporter 配置..."
    kubectl apply -f mysql-exporter-deployment.yaml
    
    log_info "等待 MySQL Exporter pod 就緒..."
    kubectl wait --for=condition=ready pod \
        -l app=mysql-exporter \
        -n openfga-prod \
        --timeout=300s \
        2>/dev/null || log_warn "等待超時，pod 仍在啟動中"
    
    log_success "MySQL Exporter 已部署"
}

# 部署完整棧
deploy_full_stack() {
    log_info "部署完整監控棧..."
    
    deploy_prometheus
    echo ""
    deploy_mysql_exporter
    
    log_success "完整監控棧已部署！"
}

# 驗證部署
verify_deployment() {
    log_info "驗證監控部署..."
    
    echo ""
    
    # 檢查 Prometheus
    log_info "檢查 Prometheus..."
    if kubectl get deployment -n monitoring 2>/dev/null | grep -q prometheus; then
        PROM_READY=$(kubectl get deployment prometheus -n monitoring -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        PROM_DESIRED=$(kubectl get deployment prometheus -n monitoring -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
        
        if [ "$PROM_READY" -eq "$PROM_DESIRED" ]; then
            log_success "Prometheus: $PROM_READY/$PROM_DESIRED 個 pod 就緒"
        else
            log_warn "Prometheus: $PROM_READY/$PROM_DESIRED 個 pod 就緒（未完全就緒）"
        fi
        
        # 嘗試連接
        if kubectl port-forward -n monitoring svc/prometheus 9090:9090 &>/dev/null &
        then
            PF_PID=$!
            sleep 2
            
            if curl -s http://localhost:9090/-/healthy &>/dev/null; then
                log_success "Prometheus API 已就緒"
            else
                log_warn "Prometheus API 暫不可用（pod 可能仍在初始化）"
            fi
            
            kill $PF_PID 2>/dev/null || true
        fi
    else
        log_error "Prometheus 未部署"
    fi
    
    # 檢查 MySQL Exporter
    log_info "檢查 MySQL Exporter..."
    if kubectl get deployment -n openfga-prod 2>/dev/null | grep -q mysql-exporter; then
        EXPORTER_READY=$(kubectl get deployment mysql-exporter -n openfga-prod -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        EXPORTER_DESIRED=$(kubectl get deployment mysql-exporter -n openfga-prod -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
        
        if [ "$EXPORTER_READY" -eq "$EXPORTER_DESIRED" ]; then
            log_success "MySQL Exporter: $EXPORTER_READY/$EXPORTER_DESIRED 個 pod 就緒"
        else
            log_warn "MySQL Exporter: $EXPORTER_READY/$EXPORTER_DESIRED 個 pod 就緒（未完全就緒）"
        fi
    else
        log_error "MySQL Exporter 未部署"
    fi
    
    # 檢查 Targets
    log_info "檢查 Prometheus targets..."
    TARGETS=$(kubectl exec -n monitoring prometheus-0 -- \
        curl -s http://localhost:9090/api/v1/targets 2>/dev/null | \
        grep -c '"health":"up"' || echo "0")
    
    if [ "$TARGETS" -gt 0 ]; then
        log_success "Prometheus 已發現 $TARGETS 個 targets"
    else
        log_warn "Prometheus 未發現任何 targets（可能仍在初始化）"
    fi
    
    echo ""
    log_success "驗證完成！"
}

# 啟動監控工具
start_monitoring() {
    log_info "啟動監控工具..."
    
    # 檢查 Python 環境
    if ! command_exists python3; then
        log_error "Python 3 未安裝"
        return 1
    fi
    
    # 檢查依賴
    if ! python3 -c "import requests" 2>/dev/null; then
        log_warn "requests 模塊未安裝，正在安裝..."
        pip install requests || log_error "無法安裝 requests"
        return 1
    fi
    
    # 檢查監控工具文件
    if [ ! -f "k8s_prometheus_monitor.py" ]; then
        log_error "k8s_prometheus_monitor.py 不存在"
        return 1
    fi
    
    log_info "啟動 Prometheus 監控工具..."
    python3 k8s_prometheus_monitor.py
}

# 卸載監控
uninstall_monitoring() {
    log_warn "卸載監控..."
    
    read -p "確定要卸載 Prometheus 和 MySQL Exporter 嗎？(y/N) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ -f "mysql-exporter-deployment.yaml" ]; then
            log_info "刪除 MySQL Exporter..."
            kubectl delete -f mysql-exporter-deployment.yaml --ignore-not-found=true
        fi
        
        if [ -f "prometheus-deployment.yaml" ]; then
            log_info "刪除 Prometheus..."
            kubectl delete -f prometheus-deployment.yaml --ignore-not-found=true
        fi
        
        log_info "刪除 monitoring namespace..."
        kubectl delete namespace monitoring --ignore-not-found=true
        
        log_success "卸載完成"
    else
        log_warn "卸載已取消"
    fi
}

# 主函數
main() {
    while true; do
        show_menu
        read -p "請選擇 (0-7): " choice
        
        case $choice in
            1)
                check_environment
                ;;
            2)
                deploy_prometheus
                ;;
            3)
                deploy_mysql_exporter
                ;;
            4)
                deploy_full_stack
                ;;
            5)
                verify_deployment
                ;;
            6)
                start_monitoring
                ;;
            7)
                uninstall_monitoring
                ;;
            0)
                log_info "退出"
                exit 0
                ;;
            *)
                log_error "無效選擇"
                ;;
        esac
        
        if [ $# -eq 0 ]; then
            read -p "按 Enter 繼續..." -t 5 || true
        else
            break
        fi
    done
}

# 非交互式模式支持
if [ $# -gt 0 ]; then
    case "$1" in
        check)
            check_environment
            ;;
        deploy-prometheus)
            deploy_prometheus
            ;;
        deploy-exporter)
            deploy_mysql_exporter
            ;;
        deploy-all)
            deploy_full_stack
            ;;
        verify)
            verify_deployment
            ;;
        monitor)
            start_monitoring
            ;;
        uninstall)
            uninstall_monitoring
            ;;
        *)
            log_error "未知命令: $1"
            echo "用法: $0 [check|deploy-prometheus|deploy-exporter|deploy-all|verify|monitor|uninstall]"
            exit 1
            ;;
    esac
else
    main
fi
