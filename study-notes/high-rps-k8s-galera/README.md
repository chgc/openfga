# 🚀 K8s + MariaDB Galera OpenFGA 高 RPS 設計方案

本資料夾包含完整的 Kubernetes 環境中使用 MariaDB Galera 3 節點集群支持 OpenFGA 高 RPS（10,000+ 請求/秒）負載的設計方案。

## 📁 資料夾結構

```
high-rps-k8s-galera/
├─ 📄 README.md (本文件)
│
├─ 📚 docs/                          # 完整文檔和指南
│  ├─ README.md                      # 項目概述
│  ├─ QUICK_START.md                 # ⭐ 5分鐘快速開始
│  ├─ QUICK_REFERENCE.md             # ⭐ 30秒速查卡
│  ├─ POD_RPS_CAPACITY_MONITORING.md # ⭐ Pod RPS 容量監控指南
│  ├─ MYSQL_GALERA_CONNECTION_POOL_OPTIMIZATION.md  # 深度優化指南
│  ├─ MONITORING_AND_TROUBLESHOOTING.md              # 運維故障排除
│  ├─ INDEX.md                       # 資源導航
│  └─ SUMMARY.md                     # 視覺化總結
│
├─ 🧮 tools/                         # 自動化工具
│  ├─ connection_pool_calculator.py  # 連接池配置計算器
│  ├─ pod_rps_monitor.py             # ⭐ Pod RPS 實時監控器
│  └─ k8s_deployment_checker.py      # 部署健康檢查工具
│
└─ 📋 k8s-configs/                   # Kubernetes 配置檔案
   └─ k8s-openfga-mariadb-galera-deployment.yaml  # 完整部署配置
```

## 🎯 核心推薦配置

**目標**: 10,000 RPS，500 萬筆資料，99.99% 可用性

```yaml
OpenFGA:
  Pod 副本: 8-10
  MaxOpenConns: 150 per Pod
  MaxIdleConns: 50 per Pod
  
MariaDB Galera:
  節點數: 3 (High Availability)
  max_connections: 2000
  存儲: 100Gi per node (SSD)

性能指標:
  吞吐量: 10,000 RPS
  p99 延遲: < 150ms
  可用性: 99.99%
```

## 🔍 如何知道每個 Pod 能乘載的 RPS 量？

**方法 1: 理論計算（快速預估）**
```bash
# 使用計算器獲得理論容量
python tools/connection_pool_calculator.py

# 理論公式:
# RPS/Pod = (MaxOpenConns × 1000) / (平均延遲ms × 安全係數)
# 例如: (150 × 1000) / (50 × 1.5) = 2,000 RPS/Pod
```

**方法 2: 實時監控（實際測量）⭐ 推薦**
```bash
# 監控每個 Pod 的實際 RPS
kubectl port-forward -n monitoring svc/prometheus 9090:9090 &
python tools/pod_rps_monitor.py

# 顯示:
# • 每個 Pod 的當前 RPS
# • 容量使用百分比
# • 錯誤率和延遲
# • 資源使用情況
```

**方法 3: 壓力測試（確定最大容量）**
```bash
# 詳見 docs/POD_RPS_CAPACITY_MONITORING.md
# 使用 ghz 或 k6 進行漸進式壓力測試
# 找出導致延遲或錯誤率上升的臨界 RPS 值
```

💡 **實際容量 ≈ 理論容量 × 0.6-0.8**（受查詢複雜度、資源限制等因素影響）

詳細指南: [docs/POD_RPS_CAPACITY_MONITORING.md](docs/POD_RPS_CAPACITY_MONITORING.md)

## 🚀 5 分鐘快速開始

### 步驟 1: 生成最優配置

```bash
python tools/connection_pool_calculator.py
```

### 步驟 2: 部署到 Kubernetes

```bash
kubectl create namespace openfga-prod
kubectl apply -f k8s-configs/k8s-openfga-mariadb-galera-deployment.yaml
```

### 步驟 3: 驗證部署

```bash
python tools/k8s_deployment_checker.py
```

### 步驟 4: 監控實際 RPS (可選)

```bash
# 如果已部署 Prometheus
kubectl port-forward -n monitoring svc/prometheus 9090:9090 &
python tools/pod_rps_monitor.py
```

## 📚 文檔指南

| 文檔 | 閱讀時間 | 適合場景 |
|------|--------|--------|
| **QUICK_REFERENCE.md** | 5 分鐘 | 快速查詢常用命令 |
| **POD_RPS_CAPACITY_MONITORING.md** | 15 分鐘 | ⭐ 監控實際 Pod RPS 容量 |
| **QUICK_START.md** | 15 分鐘 | 部署和基本操作 |
| **README.md** | 20 分鐘 | 項目概述 |
| **MYSQL_GALERA_CONNECTION_POOL_OPTIMIZATION.md** | 60 分鐘 | 深度理解優化原理 |
| **MONITORING_AND_TROUBLESHOOTING.md** | 60 分鐘 | 監控和故障處理 |
| **INDEX.md** | 15 分鐘 | 資源導航 |
| **SUMMARY.md** | 10 分鐘 | 視覺化總結 |

## 🧮 自動化工具

### connection_pool_calculator.py
自動計算最優的連接池配置（理論值）

```bash
# 運行計算器
python tools/connection_pool_calculator.py

# 功能:
# ✅ 4 個預設場景 (1K/5K/10K/20K RPS)
# ✅ 自定義 RPS 計算
# ✅ 自動生成 YAML 配置
# ✅ 成本估算 (AWS)
# ✅ 資源預測
```

### pod_rps_monitor.py
實時監控每個 Pod 的實際 RPS 和容量使用率

```bash
# 運行監控器（需要 Prometheus）
kubectl port-forward -n monitoring svc/prometheus 9090:9090 &
python tools/pod_rps_monitor.py

# 功能:
# ✅ 實時 RPS 監控
# ✅ 容量使用百分比
# ✅ 錯誤率追蹤
# ✅ 延遲統計 (p50, p99)
# ✅ 資源使用情況
# ✅ 彩色狀態指示器
# ✅ 告警過載 Pod
```

### k8s_deployment_checker.py
驗證部署是否符合規範

```bash
# 運行檢查
python tools/k8s_deployment_checker.py

# 檢查項目:
# ✅ Namespace 存在
# ✅ Pod 狀態就緒
# ✅ MySQL 連接正常
# ✅ Galera 集群健康
# ✅ 資源使用情況
```

## 📋 K8s 配置

`k8s-configs/k8s-openfga-mariadb-galera-deployment.yaml` 包含：

- ✅ OpenFGA Deployment (8 副本)
- ✅ MariaDB Galera StatefulSet (3 節點)
- ✅ ConfigMap 和 Secret
- ✅ 存儲配置 (SSD)
- ✅ 網絡策略
- ✅ HPA 和 PDB
- ✅ Prometheus 監控配置

可直接部署，無需修改。

## 💰 成本分析 (AWS)

```
月度成本:
  OpenFGA (10 x m5.large)     $500
  MariaDB (3 x m5.2xlarge)    $900
  存儲 (300Gi EBS)             $30
  ─────────────────────────────────
  總計                        $1,430/月

效率:
  每 1K RPS 成本: $143
  月度支持請求: 2.6 × 10¹¹
```

## 🔍 推薦學習路徑

### 初級 (30 分鐘)
1. 讀 QUICK_REFERENCE.md
2. 讀 QUICK_START.md
3. 運行 connection_pool_calculator.py

### 中級 (1.5 小時)
1. 完成初級內容
2. 讀 MYSQL_GALERA_CONNECTION_POOL_OPTIMIZATION.md
3. 查看 k8s-configs/ 配置文件

### 高級 (2.5 小時)
1. 完成中級內容
2. 讀 MONITORING_AND_TROUBLESHOOTING.md
3. 運行 k8s_deployment_checker.py
4. 進行故障排除實驗

## ⚡ 快速命令速查

### 計算理論配置
```bash
python tools/connection_pool_calculator.py
```

### 監控實際 RPS
```bash
# 需要先啟動 Prometheus port-forward
kubectl port-forward -n monitoring svc/prometheus 9090:9090 &
python tools/pod_rps_monitor.py
```

### 部署
```bash
kubectl apply -f k8s-configs/k8s-openfga-mariadb-galera-deployment.yaml
```

### 檢查狀態
```bash
python tools/k8s_deployment_checker.py
```

### 監控連接
```bash
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "SHOW STATUS LIKE 'Threads%';"
```

### 查看 Pod
```bash
kubectl get pods -n openfga-prod
kubectl top pods -n openfga-prod
```

## 📞 快速支持

- **配置問題** → docs/MYSQL_GALERA_CONNECTION_POOL_OPTIMIZATION.md
- **部署問題** → docs/QUICK_START.md
- **故障排除** → docs/MONITORING_AND_TROUBLESHOOTING.md
- **快速查詢** → docs/QUICK_REFERENCE.md

## ✅ 部署檢查清單

### 部署前
- [ ] 讀完 docs/QUICK_START.md
- [ ] 運行 tools/connection_pool_calculator.py
- [ ] K8s 集群準備好 (3+ 節點)

### 部署後
- [ ] 所有 Pod Ready
- [ ] MySQL 連接正常
- [ ] Galera 集群 Primary
- [ ] 運行 tools/k8s_deployment_checker.py ✅

## 🎓 核心知識點

### 連接池優化

```
MaxOpenConns 計算公式:
需要連接數 = (RPS × 平均延遲 / 1000) × 安全係數

例如 (10K RPS):
所需 = (10000 × 50 / 1000) × 1.5 = 750
每 Pod = 750 / 10 ≈ 150 ✓
```

### Galera 特性

✅ **同步複製**: 任何節點故障無數據丟失
✅ **自動轉移**: 應用對故障透明
✅ **讀寫一致**: 任何節點可讀取

### 監控關鍵指標

```prometheus
應用層:
  openfga_check_duration_ms
  openfga_list_objects_duration_ms

數據庫層:
  mysql_global_status_threads_connected
  mysql_global_status_slow_queries

Galera 層:
  wsrep_cluster_status
  wsrep_local_state_comment
```

## 🌟 主要特點

✅ **完整性** - 從理論到實踐的全覆蓋
✅ **實用性** - 可直接部署的生產級配置
✅ **自動化** - Python 工具自動生成最優參數
✅ **可靠性** - 基於 OpenFGA 源碼和最佳實踐
✅ **可擴展性** - 支持 1K 到 50K+ RPS
✅ **可維護性** - 詳細的監控和故障排除指南

## 📝 更新日誌

### v1.0 (2025-12-31)
- ✅ 初始版本
- ✅ 完整的優化指南
- ✅ K8s 部署配置
- ✅ 監控和故障排除
- ✅ 自動化工具
- ✅ 資料夾結構化整理

## 🚀 開始使用

1. **快速開始**: 見 `docs/QUICK_START.md`
2. **生成配置**: 運行 `python tools/connection_pool_calculator.py`
3. **部署**: 應用 `k8s-configs/k8s-openfga-mariadb-galera-deployment.yaml`
4. **驗證**: 運行 `python tools/k8s_deployment_checker.py`

---

**祝你部署成功！** 🎉

最後更新: 2025-12-31
版本: 1.0 (穩定)
狀態: ✅ 生產就緒
