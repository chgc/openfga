# Prometheus 監控方案總結

## 核心問題的解決方案

**問題**: 即時監控有辦法使用 Prometheus metrics 代替 kubectl 嗎？

**答案**: ✅ **完全可以！** 而且比 kubectl 更強大。

---

## 三層監控解決方案

### 層級 1️⃣: 離線配置檢查 (部署前)

**工具**: `k8s_deployment_checker_offline.py`

```python
python k8s_deployment_checker_offline.py
# 選擇 1: 分析 YAML 文件
```

**功能**:
- ✅ 無需任何權限
- ✅ 靜態驗證配置規範
- ✅ 檢查資源規格
- ✅ 驗證連接池設置
- ✅ 計算總資源需求

**適用場景**:
- 部署前驗證（開發/測試）
- CI/CD 自動化檢查
- 沒有集群訪問權限

---

### 層級 2️⃣: kubectl 檢查工具 (部署直後)

**工具**: `k8s_deployment_checker.py`（原版）

```bash
python k8s_deployment_checker.py
```

**功能**:
- ✅ 需要 kubectl 權限
- ✅ 查看 Pod 實時狀態
- ✅ 檢查 MySQL 連接
- ✅ 驗證 Galera 集群
- ✅ 查看資源使用情況

**適用場景**:
- 部署直後快速驗證
- 快速問題排查
- 有 kubectl 訪問權限

---

### 層級 3️⃣: Prometheus 實時監控 (長期運維)

**工具**: `k8s_prometheus_monitor.py`（新增）

```bash
python k8s_prometheus_monitor.py
# 選擇 2: 持續監控（每 5 秒更新）
```

**功能**:
- ✅ **無需 kubectl**（只需 Prometheus HTTP 訪問）
- ✅ **實時性能指標** (CPU、Memory、Network)
- ✅ **30 天歷史數據**（用於趨勢分析）
- ✅ **自動告警規則**（基於 PromQL）
- ✅ **與 Grafana 集成**（可視化儀表板）

**適用場景**:
- 長期監控和分析 ⭐
- 沒有 kubectl 權限但有 Prometheus
- 生產環境持續監控
- 性能趨勢分析
- 自動告警和響應

---

## 🚀 快速開始

### 一鍵部署

```bash
# 進入工具目錄
cd tools

# 方法 1: 交互式（推薦）
bash deploy-monitoring.sh

# 方法 2: 一條命令部署所有
bash deploy-monitoring.sh deploy-all

# 方法 3: 驗證部署
bash deploy-monitoring.sh verify

# 方法 4: 啟動監控
bash deploy-monitoring.sh monitor
```

### 或者使用 kubectl

```bash
# 部署 Prometheus
kubectl apply -f prometheus-deployment.yaml

# 部署 MySQL Exporter
kubectl apply -f mysql-exporter-deployment.yaml

# 訪問 Prometheus UI
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# 訪問 http://localhost:9090

# 運行監控工具
python k8s_prometheus_monitor.py
```

---

## 📊 Prometheus 監控優勢

### 相比 kubectl 的優勢

| 特性 | kubectl | Prometheus |
|------|---------|-----------|
| 需要權限 | ✅ kubectl | ❌ 只需 HTTP |
| 實時性 | ✅ 實時 | ✅ 實時 |
| 歷史數據 | ❌ | ✅ 30 天 |
| 告警功能 | ❌ | ✅ PromQL 規則 |
| Network I/O | ❌ | ✅ |
| 可視化 | ❌ CLI | ✅ Grafana |
| 跨集群 | ❌ | ✅ 支持 |

### 核心指標

```promql
# Pod 狀態
kube_pod_status_phase{namespace="openfga-prod"}

# CPU 使用（%）
rate(container_cpu_usage_seconds_total{namespace="openfga-prod"}[5m]) * 100

# Memory 使用（MiB）
container_memory_working_set_bytes{namespace="openfga-prod"} / 1024 / 1024

# 網絡 I/O（字節/秒）
rate(container_network_receive_bytes_total[5m])

# MySQL 連接數
mysql_global_status_threads_connected

# Galera 集群狀態
mysql_global_status_wsrep_cluster_size
```

---

## 🎯 適用場景決策

```
你需要什麼？
├─ 部署前驗證配置
│  └─► 用【離線工具】✅
│
├─ 部署直後檢查狀態
│  └─► 用【kubectl 工具】✅
│
└─ 長期監控 + 無 kubectl
   └─► 用【Prometheus 工具】✅✅✅
```

### 完整工作流程

```bash
# ⓵ 配置驗證（任何地方，無需權限）
python k8s_deployment_checker_offline.py

# ⓶ 部署應用
kubectl apply -f your-deployment.yaml

# ⓷ 部署監控基礎設施（需要 kubectl）
bash deploy-monitoring.sh deploy-all

# ⓸ 實時監控（任何地方，無需 kubectl）
python k8s_prometheus_monitor.py
# 選擇 2（持續監控）

# ⓹ 長期分析（訪問 Prometheus UI）
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# 訪問 http://localhost:9090
```

---

## 📈 監控工具輸出示例

### Prometheus 監控工具輸出

```
[監控週期 #1] 2026-01-01 12:00:00
════════════════════════════════════════

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
✅ 總計: 12.45 GiB
   OpenFGA: 3.84 GiB
   MariaDB: 8.61 GiB

[4] 網絡 I/O
✅ 進流量: 512.34 KB/s
   出流量: 789.12 KB/s

[5] MySQL 連接和查詢
✅ 活動連接: 245
   總查詢: 156234

[6] Galera 集群狀態
✅ 集群大小: 3
   ✅ 就緒: 是
```

---

## 🔧 安裝和配置

### 前置要求

```bash
# Python 依賴
pip install requests

# Kubernetes 訪問（部署監控時）
kubectl access to cluster

# 訪問 Prometheus（運行監控時）
HTTP access to Prometheus:9090
```

### 部署步驟

```bash
# 1. 部署 Prometheus
kubectl apply -f prometheus-deployment.yaml

# 2. 部署 MySQL Exporter
kubectl apply -f mysql-exporter-deployment.yaml

# 3. 驗證部署
bash deploy-monitoring.sh verify

# 4. 啟動監控
python k8s_prometheus_monitor.py
```

---

## 📝 新增文件清單

| 文件 | 用途 |
|------|------|
| `k8s_prometheus_monitor.py` | Prometheus 監控工具（核心） |
| `prometheus-deployment.yaml` | Prometheus 部署配置 |
| `mysql-exporter-deployment.yaml` | MySQL Exporter 部署配置 |
| `deploy-monitoring.sh` | 快速部署腳本 |
| `PROMETHEUS_MONITORING_GUIDE.md` | Prometheus 詳細指南 |
| `COMPLETE_MONITORING_GUIDE.md` | 完整工具對比指南 |
| `README_MONITORING.md` | 監控工具總體說明 |

---

## ✨ 主要特點

### 1️⃣ 無需 kubectl 權限

```bash
# 原版工具（需要 kubectl）
python k8s_deployment_checker.py
# ❌ 需要 kubectl 和集群訪問

# 新工具（只需 Prometheus HTTP）
python k8s_prometheus_monitor.py
# ✅ 只需要 Prometheus URL
# ✅ 可在任何地方運行
```

### 2️⃣ 實時 + 歷史 + 告警

```promql
# Prometheus 提供三層功能：
1. 實時數據：rate(container_cpu_usage_seconds_total[5m])
2. 歷史數據：offset 1d 查看一天前數據
3. 告警規則：alert: HighCPUUsage expr: ... for: 5m
```

### 3️⃣ 與 Grafana 完美集成

```bash
# 安裝 Grafana
helm install grafana grafana/grafana -n monitoring

# 添加 Prometheus 數據源
# http://prometheus:9090

# 匯入儀表板
# Dashboard ID: 10566 (MySQL)
# Dashboard ID: 7249 (Kubernetes)
```

---

## 🎓 監控最佳實踐

### 告警規則示例

```yaml
- alert: HighCPUUsage
  expr: rate(container_cpu_usage_seconds_total{namespace="openfga-prod"}[5m]) * 100 > 80
  for: 5m
  
- alert: PodNotReady
  expr: count(kube_pod_status_phase{namespace="openfga-prod",phase="Running"}) < 8
  for: 2m
  
- alert: HighMySQLConnections
  expr: mysql_global_status_threads_connected > 300
  for: 5m
```

### 定期檢查清單

- [ ] CPU 使用 < 80%
- [ ] Memory 使用 < 85%
- [ ] 所有 Pod 運行中
- [ ] Galera 集群大小 = 3
- [ ] 沒有告警
- [ ] Network I/O 正常

---

## 🔒 安全建議

1. **限制 Prometheus 訪問**
   - 使用 Ingress + 認證
   - 限制 IP 範圍

2. **MySQL 密碼管理**
   - 使用 Kubernetes Secrets
   - 定期輪換密碼

3. **監控數據保護**
   - 啟用 HTTPS
   - 限制查詢範圍

---

## 🎉 總結

### ✅ Prometheus 監控的優勢

1. **✨ 無需 kubectl**
   - 只需 HTTP 訪問 Prometheus
   - 更加安全和靈活

2. **📈 實時 + 歷史**
   - 實時性能監控
   - 30 天歷史數據分析

3. **🚨 自動告警**
   - 基於 PromQL 規則
   - 與 Alertmanager 集成

4. **📊 可視化支持**
   - 與 Grafana 無縫集成
   - 美觀的儀表板

5. **🔧 高度可定製**
   - 靈活的 PromQL 查詢
   - 自定義告警規則
   - 易於擴展

---

## 📞 快速開始

### 立即開始（3 分鐘）

```bash
cd tools

# 一鍵部署
bash deploy-monitoring.sh deploy-all

# 驗證部署
bash deploy-monitoring.sh verify

# 啟動監控
python k8s_prometheus_monitor.py
```

### 下一步

1. 閱讀 [PROMETHEUS_MONITORING_GUIDE.md](PROMETHEUS_MONITORING_GUIDE.md)
2. 查看 [COMPLETE_MONITORING_GUIDE.md](COMPLETE_MONITORING_GUIDE.md)
3. 配置告警規則
4. 集成 Grafana（可選）

---

**有了這個方案，即使沒有 kubectl 權限，也能進行完整的實時監控和長期分析！** 🎯
