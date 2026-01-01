# Prometheus 實時監控使用指南

## 概述

使用 **Prometheus metrics** 代替 kubectl 命令進行實時監控，優點：

- ✅ **無需 kubectl 權限** - 只需要訪問 Prometheus API
- ✅ **實時性能指標** - CPU、Memory、Network I/O
- ✅ **歷史數據保留** - 可查詢過去 30 天的數據
- ✅ **便於告警** - 可基於 metrics 設置 Prometheus 告警規則
- ✅ **與 Grafana 集成** - 可視化監控面板

## 架構

```
┌─────────────────────────────────────────────────┐
│         Kubernetes Cluster                      │
│                                                 │
│  ┌─────────────┐        ┌──────────────┐      │
│  │   OpenFGA   │        │  MariaDB     │      │
│  │   Pods      │        │  Galera      │      │
│  │             │        │  Pods        │      │
│  └──────┬──────┘        └────┬─────────┘      │
│         │                    │                 │
│         │ metrics            │ metrics         │
│         │ :8081              │ :9104           │
│         ▼                    ▼                 │
│  ┌─────────────────────────────────┐          │
│  │  MySQL Exporter                │          │
│  │  (Scrapes MariaDB metrics)     │          │
│  └────────────────┬────────────────┘          │
│                   │                           │
│  ┌────────────────┴──────────────────────┐   │
│  │         Prometheus                    │    │
│  │  (Collects & Stores metrics)          │    │
│  │  Port: 9090                           │    │
│  └────────────────┬──────────────────────┘   │
│                   │                           │
└───────────────────┼───────────────────────────┘
                    │
                    │ HTTP API
                    │
          ┌─────────▼─────────┐
          │ k8s_prometheus    │
          │ _monitor.py       │
          │                   │
          │ (本工具)          │
          └───────────────────┘
```

## 安裝步驟

### 1. 建立 Monitoring Namespace

```bash
kubectl create namespace monitoring
```

### 2. 部署 Prometheus

```bash
kubectl apply -f prometheus-deployment.yaml
```

檢查狀態：

```bash
kubectl get pods -n monitoring
kubectl get svc -n monitoring
```

### 3. 部署 MySQL Exporter

```bash
kubectl apply -f mysql-exporter-deployment.yaml
```

### 4. 驗證 Metrics 收集

#### 4.1 訪問 Prometheus Web UI

```bash
# 本地訪問
kubectl port-forward -n monitoring svc/prometheus 9090:9090

# 然後在瀏覽器中訪問: http://localhost:9090
```

#### 4.2 檢查 Targets

在 Prometheus UI 中：
1. 進入 Status → Targets
2. 應該看到：
   - kubernetes-apiservers (UP)
   - kubernetes-nodes (UP)
   - kubernetes-pods (UP)
   - mysql-exporter (UP)
   - kube-state-metrics (UP)

#### 4.3 查詢指標

在 Prometheus UI 的 Graph 標籤中，試試查詢：

```promql
# Pod 狀態
kube_pod_status_phase{namespace="openfga-prod"}

# CPU 使用
rate(container_cpu_usage_seconds_total{namespace="openfga-prod"}[5m]) * 100

# Memory 使用
container_memory_working_set_bytes{namespace="openfga-prod"} / 1024 / 1024

# MySQL 連接數
mysql_global_status_threads_connected
```

## 使用監控工具

### 安裝依賴

```bash
pip install requests
```

### 運行監控工具

#### 1. 一次性監控報告

```bash
python k8s_prometheus_monitor.py
# 選擇: 1
# 輸入 Prometheus 地址: http://localhost:9090
# 輸入 namespace: openfga-prod
```

輸出示例：

```
✅ 已連接到 Prometheus
   Namespace: openfga-prod
   刷新間隔: 5秒

[監控週期 #1] 2026-01-01 12:00:00
────────────────────────────────────────────────────

[1] Pod 狀態
✅ 總計: 12 Pod
   就緒: 12 Running, 0 其他狀態
   OpenFGA: 10 Running
   MariaDB: 3 Running

[2] CPU 使用率
✅ 平均 CPU: 25.50%
   OpenFGA 平均: 18.75%
   MariaDB 平均: 42.33%

[3] 內存使用
✅ 總計: 12.45 GiB (12748.80 MiB)
   OpenFGA: 3.84 GiB
   MariaDB: 8.61 GiB

[4] 網絡 I/O (字節/秒)
✅ 進流量: 512.34 KB/s
   出流量: 789.12 KB/s

[5] MySQL 連接和查詢
✅ 活動連接: 245
   總查詢: 156234

[6] Galera 集群狀態
✅ 集群大小: 3
   ✅ 就緒: 是
```

#### 2. 持續監控（每 5 秒更新）

```bash
python k8s_prometheus_monitor.py
# 選擇: 2
```

會不斷更新顯示，按 Ctrl+C 停止。

#### 3. 自定義更新間隔

```bash
python k8s_prometheus_monitor.py
# 選擇: 3
# 輸入更新間隔: 10
```

每 10 秒更新一次。

#### 4. 摘要報告

```bash
python k8s_prometheus_monitor.py
# 選擇: 4
```

生成簡潔的健康狀態報告。

## PromQL 查詢示例

### OpenFGA 相關指標

```promql
# Pod 數量和狀態
count(kube_pod_status_phase{namespace="openfga-prod",phase="Running"})

# OpenFGA 副本數
kube_deployment_status_replicas{namespace="openfga-prod",deployment="openfga-server"}

# 請求延遲（P95）
histogram_quantile(0.95, rate(openfga_http_request_duration_seconds_bucket[5m]))

# 錯誤率
rate(openfga_http_requests_total{status=~"5.."}[5m])

# QPS
rate(openfga_http_requests_total[5m])
```

### MariaDB/MySQL 指標

```promql
# 活動連接數
mysql_global_status_threads_connected

# Galera 集群大小
mysql_global_status_wsrep_cluster_size

# 讀寫操作速率
rate(mysql_global_status_innodb_rows_read[1m])
rate(mysql_global_status_innodb_rows_written[1m])

# Replication lag
mysql_global_status_seconds_behind_master

# Query 速率
rate(mysql_global_status_questions[1m])
```

### 系統資源指標

```promql
# CPU 使用百分比
rate(container_cpu_usage_seconds_total{namespace="openfga-prod"}[5m]) * 100

# Memory 使用（MiB）
container_memory_working_set_bytes{namespace="openfga-prod"} / 1024 / 1024

# 網絡進流量
rate(container_network_receive_bytes_total{namespace="openfga-prod"}[5m])

# 磁盤 I/O
rate(container_fs_io_time_seconds_total[5m])
```

## 設置告警規則

在 `prometheus-deployment.yaml` 中的 ConfigMap 添加告警規則：

```yaml
groups:
  - name: openfga
    interval: 30s
    rules:
    # 高 CPU 使用
    - alert: HighCPUUsage
      expr: rate(container_cpu_usage_seconds_total{namespace="openfga-prod"}[5m]) * 100 > 80
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "高 CPU 使用: {{ $value }}%"
    
    # Pod 不就緒
    - alert: PodNotReady
      expr: count(kube_pod_status_phase{namespace="openfga-prod",phase="Running"}) < 8
      for: 2m
      labels:
        severity: critical
      annotations:
        summary: "Pod 不就緒，只有 {{ $value }} 個運行中"
    
    # MySQL 連接數過多
    - alert: HighMySQLConnections
      expr: mysql_global_status_threads_connected > 300
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "MySQL 連接數過多: {{ $value }}"
    
    # Galera 集群不健康
    - alert: GaleraClusterUnhealthy
      expr: mysql_global_status_wsrep_cluster_size < 3
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "Galera 集群大小異常: {{ $value }}"
```

## 與 Grafana 集成

### 安裝 Grafana

```bash
kubectl create -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/main/example/prometheus-operator-crd.yaml

helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm install grafana grafana/grafana -n monitoring
```

### 添加 Prometheus 數據源

1. 訪問 Grafana: `http://localhost:3000`
2. 默認用戶: admin / admin
3. 添加 Prometheus 數據源: `http://prometheus:9090`
4. 匯入 Dashboard：
   - 3662 (Prometheus 統計)
   - 7249 (Kubernetes 監控)
   - 10566 (MySQL 監控)

## 故障排查

### Prometheus 無法連接

```bash
# 檢查 Prometheus pod
kubectl logs -n monitoring prometheus-0

# 檢查配置
kubectl get configmap -n monitoring prometheus-config -o yaml
```

### MySQL Exporter 無法連接 MariaDB

```bash
# 檢查連接
kubectl logs -n openfga-prod deployment/mysql-exporter

# 測試連接
kubectl port-forward -n openfga-prod svc/mariadb-galera 3306:3306
mysql -h localhost -u root -p
```

### 指標不可用

```bash
# 檢查 metrics endpoints
curl http://localhost:8081/metrics  # OpenFGA
curl http://localhost:9104/metrics  # MySQL Exporter

# 檢查 Prometheus 抓取日誌
kubectl logs -n monitoring prometheus-0 | grep "scrape"
```

## 優勢對比

| 功能 | kubectl | Prometheus |
|------|---------|-----------|
| **需要權限** | kubectl access | HTTP 訪問 |
| **實時性** | 實時 | 實時 |
| **歷史數據** | ❌ | ✅ 30 天 |
| **性能指標** | 基本 | ✅ 詳細 |
| **告警功能** | ❌ | ✅ |
| **可視化** | CLI | ✅ Grafana |
| **跨集群監控** | 單集群 | ✅ 多集群 |

## 安全建議

### 1. 限制 Prometheus 訪問

```yaml
# 添加到 Service 中
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: prometheus-access
  namespace: monitoring
spec:
  podSelector:
    matchLabels:
      app: prometheus
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: monitoring-client
    ports:
    - protocol: TCP
      port: 9090
```

### 2. 使用 Ingress + Authentication

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: prometheus
  namespace: monitoring
  annotations:
    nginx.ingress.kubernetes.io/auth-type: basic
    nginx.ingress.kubernetes.io/auth-secret: basic-auth
spec:
  rules:
  - host: prometheus.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: prometheus
            port:
              number: 9090
```

## 總結

使用 **Prometheus 監控**，你可以：

1. ✅ **不需要 kubectl 權限** - 只需 Prometheus HTTP 訪問
2. ✅ **實時監控** - 查看系統運行狀態
3. ✅ **歷史分析** - 保留 30 天數據用於分析
4. ✅ **自動告警** - 基於規則自動告警
5. ✅ **可視化** - 與 Grafana 完美配合

建議的監控工作流程：

```bash
# 1️⃣ 部署 Prometheus 和 MySQL Exporter
kubectl apply -f prometheus-deployment.yaml
kubectl apply -f mysql-exporter-deployment.yaml

# 2️⃣ 驗證 Prometheus 收集指標
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# 訪問 http://localhost:9090

# 3️⃣ 使用監控工具查看狀態
python k8s_prometheus_monitor.py

# 4️⃣ （可選）安裝 Grafana 進行可視化
helm install grafana grafana/grafana -n monitoring
```

這樣即使沒有 kubectl 權限，也能進行完整的實時監控！
