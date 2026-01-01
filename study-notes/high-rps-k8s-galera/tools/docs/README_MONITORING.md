# OpenFGA + MariaDB Galera 監控工具完整指南

完整的監控解決方案，支持**三種不同場景**和**不同權限級別**。

## 📚 文檔導航

### 一、快速開始

1. **[完整監控指南](COMPLETE_MONITORING_GUIDE.md)** ⭐ 首先閱讀
   - 三種監控工具對比
   - 使用決策樹
   - 適用場景推薦

2. **[離線檢查工具](OFFLINE_CHECKER_GUIDE.md)**
   - 無需 kubectl 權限
   - 配置驗證
   - YAML 分析

3. **[Prometheus 監控指南](PROMETHEUS_MONITORING_GUIDE.md)**
   - 實時監控
   - 無需 kubectl 權限
   - 歷史數據和告警

### 二、快速部署

```bash
# 方法 1: 交互式部署（推薦）
bash deploy-monitoring.sh

# 方法 2: 直接命令
bash deploy-monitoring.sh deploy-all      # 部署完整棧
bash deploy-monitoring.sh verify          # 驗證部署
bash deploy-monitoring.sh monitor         # 啟動監控

# 方法 3: kubectl 部署
kubectl apply -f prometheus-deployment.yaml
kubectl apply -f mysql-exporter-deployment.yaml
```

## 🛠️ 工具清單

### 監控工具

| 工具 | 文件 | 用途 | 權限要求 |
|------|------|------|---------|
| **kubectl 檢查** | `k8s_deployment_checker.py` | 部署狀態快速檢查 | ✅ kubectl |
| **離線檢查** | `k8s_deployment_checker_offline.py` | 配置驗證、部署前檢查 | ❌ 無 |
| **Prometheus 監控** | `k8s_prometheus_monitor.py` | 實時監控、長期分析 | ✅ Prometheus HTTP |

### 部署配置

| 配置 | 文件 | 內容 |
|------|------|------|
| **Prometheus** | `prometheus-deployment.yaml` | Prometheus 監控系統 |
| **MySQL Exporter** | `mysql-exporter-deployment.yaml` | MySQL/Galera 指標導出 |
| **快速部署腳本** | `deploy-monitoring.sh` | 自動化部署和驗證 |
| **範例配置** | `example-deployment.yaml` | OpenFGA + Galera 範例 |

## 🎯 使用場景

### 場景 1: 開發環境（無 Prometheus）

**需求**: kubectl 訪問權限

```bash
# 步驟 1: 驗證部署配置
python k8s_deployment_checker_offline.py
# 選擇 1，輸入 YAML 文件路徑

# 步驟 2: 部署應用
kubectl apply -f your-deployment.yaml

# 步驟 3: 檢查部署狀態
python k8s_deployment_checker.py
# 輸入 namespace 名稱
```

### 場景 2: 生產環境（有 Prometheus）

**需求**: 無需 kubectl，只需要 Prometheus HTTP 訪問

```bash
# 步驟 1: 驗證配置（在任何地方）
python k8s_deployment_checker_offline.py

# 步驟 2: 部署 Prometheus（需要 kubectl）
bash deploy-monitoring.sh deploy-all

# 步驟 3: 實時監控（任何地方）
python k8s_prometheus_monitor.py
# 選擇 2（持續監控）
```

### 場景 3: 有限權限（無 kubectl，有 Prometheus）

**需求**: 只有 Prometheus HTTP 訪問

```bash
# 驗證配置
python k8s_deployment_checker_offline.py

# 實時監控
python k8s_prometheus_monitor.py
```

## 🚀 快速命令參考

### 一鍵部署監控

```bash
# 檢查環境
bash deploy-monitoring.sh check

# 部署 Prometheus
bash deploy-monitoring.sh deploy-prometheus

# 部署 MySQL Exporter
bash deploy-monitoring.sh deploy-exporter

# 部署完整棧
bash deploy-monitoring.sh deploy-all

# 驗證部署
bash deploy-monitoring.sh verify

# 啟動監控工具
bash deploy-monitoring.sh monitor

# 卸載
bash deploy-monitoring.sh uninstall
```

### 離線配置檢查

```bash
# 交互式
python k8s_deployment_checker_offline.py

# 直接分析 YAML
python -c "
from k8s_deployment_checker_offline import OfflineChecker
OfflineChecker().print_yaml_analysis('your-deployment.yaml')
"
```

### Prometheus 監控

```bash
# 交互式
python k8s_prometheus_monitor.py

# 直接監控（Python）
python -c "
from k8s_prometheus_monitor import PrometheusMonitor
monitor = PrometheusMonitor('http://localhost:9090')
monitor.print_dashboard(continuous=True)
"

# 訪問 Prometheus UI
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# 訪問 http://localhost:9090

# 查詢指標
curl 'http://localhost:9090/api/v1/query?query=up'
```

## 📊 監控指標

### OpenFGA 指標

```promql
# Pod 狀態
kube_pod_status_phase{namespace="openfga-prod"}

# 副本數
kube_deployment_status_replicas{deployment="openfga-server"}

# CPU 使用
rate(container_cpu_usage_seconds_total{namespace="openfga-prod"}[5m]) * 100

# Memory 使用
container_memory_working_set_bytes{namespace="openfga-prod"} / 1024 / 1024

# API 請求率（如果公開 metrics）
rate(openfga_http_requests_total[5m])
```

### MySQL/Galera 指標

```promql
# 連接數
mysql_global_status_threads_connected

# 集群大小
mysql_global_status_wsrep_cluster_size

# 查詢速率
rate(mysql_global_status_questions[1m])

# 複製延遲
mysql_global_status_seconds_behind_master

# 行操作
rate(mysql_global_status_innodb_rows_read[1m])
rate(mysql_global_status_innodb_rows_written[1m])
```

## ⚙️ 配置自定義

### 修改 Prometheus 刷新頻率

編輯 `prometheus-deployment.yaml` 中的 ConfigMap：

```yaml
global:
  scrape_interval: 15s          # 改為需要的值
  evaluation_interval: 15s
```

### 修改數據保留時間

編輯 StatefulSet 的容器 args：

```yaml
- '--storage.tsdb.retention.time=30d'  # 改為需要的時間
```

### 添加自定義告警規則

在 ConfigMap 中添加 `alert.rules` 部分。

## 🔧 故障排查

### 問題: Prometheus 無法連接

```bash
# 1. 檢查 pod 狀態
kubectl get pods -n monitoring

# 2. 查看日誌
kubectl logs -n monitoring prometheus-0

# 3. 測試連接
kubectl port-forward -n monitoring svc/prometheus 9090:9090
curl http://localhost:9090/-/healthy

# 4. 檢查存儲空間
kubectl get pvc -n monitoring
```

### 問題: MySQL Exporter 無法連接 MariaDB

```bash
# 1. 檢查 MySQL 服務
kubectl get svc -n openfga-prod | grep mariadb

# 2. 查看 exporter 日誌
kubectl logs -n openfga-prod deployment/mysql-exporter

# 3. 測試 MySQL 連接
kubectl port-forward -n openfga-prod svc/mariadb-galera 3306:3306
mysql -h localhost -u root -p
```

### 問題: 監控工具無法連接 Prometheus

```bash
# 1. 確認 Prometheus 地址
kubectl get svc -n monitoring prometheus

# 2. 測試 HTTP 訪問
curl http://prometheus-url:9090/-/healthy

# 3. 查看監控工具日誌
python k8s_prometheus_monitor.py  # 會顯示連接錯誤
```

## 📈 性能監控檢查表

使用監控工具時，關注以下指標：

- [ ] **Pod 就緒**: OpenFGA ≥ 8，Galera = 3
- [ ] **CPU**: OpenFGA < 60%，Galera < 50%
- [ ] **Memory**: 總計 < 85% 可用
- [ ] **MySQL 連接**: < 300（根據配置調整）
- [ ] **Galera 狀態**: Primary，集群大小 = 3
- [ ] **網絡 I/O**: 監控異常流量

## 🔐 安全建議

1. **限制 Prometheus 訪問**
   - 使用 Ingress + 認證
   - 限制 IP 範圍
   - 定期更新 credentials

2. **MySQL 密碼管理**
   - 使用 Kubernetes Secrets
   - 定期輪換密碼
   - 限制 exporter 權限

3. **監控數據保護**
   - 啟用 HTTPS
   - 啟用身份驗證
   - 限制查詢範圍

## 📚 參考資源

- [Prometheus 文檔](https://prometheus.io/docs/)
- [MySQL Exporter](https://github.com/prometheus/mysqld_exporter)
- [Kubernetes 監控](https://kubernetes.io/docs/tasks/debug-application-cluster/resource-metrics-pipeline/)
- [Grafana 儀表板](https://grafana.com/grafana/dashboards/)

## ✅ 驗證清單

部署完成後，驗證：

- [ ] Prometheus pod 運行中
- [ ] MySQL Exporter pod 運行中
- [ ] Prometheus 可訪問 (http://localhost:9090)
- [ ] Prometheus targets 都是 UP
- [ ] 可查詢 MySQL metrics
- [ ] 監控工具能連接 Prometheus
- [ ] 儀表板顯示實時數據

## 📞 支持

如遇問題：

1. 查看相應的指南文檔
2. 檢查 pod 日誌: `kubectl logs <pod-name>`
3. 驗證部署: `bash deploy-monitoring.sh verify`
4. 檢查 Prometheus targets: 訪問 http://localhost:9090/targets

## 🎓 學習路徑

**初級**（第一周）
1. 讀完 `COMPLETE_MONITORING_GUIDE.md`
2. 用離線工具檢查 YAML 配置
3. 部署基本 kubectl 檢查工具

**中級**（第二週）
1. 部署 Prometheus 和 MySQL Exporter
2. 學習 PromQL 查詢基礎
3. 實施連續監控

**高級**（第三週）
1. 配置告警規則
2. 集成 Grafana
3. 實施自動化告警回應

## 🎉 總結

三層監控方案：

```
┌─────────────────────────────────────────────────┐
│  實時監控層 (Prometheus Monitor)                │
│  - 無需 kubectl                                 │
│  - 實時 + 歷史數據                              │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│  檢查驗證層 (kubectl + 離線工具)                │
│  - 部署狀態 + 配置檢查                          │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│  基礎設施層 (Prometheus + Exporters)            │
│  - 數據收集 + 存儲                              │
└─────────────────────────────────────────────────┘
```

**立即開始**: `bash deploy-monitoring.sh`
