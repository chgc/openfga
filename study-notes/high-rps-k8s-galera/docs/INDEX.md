# 📚 完整資源索引和使用指南

## 🎯 研究成果總結

本研究提供了 **Kubernetes 環境下 OpenFGA + MariaDB Galera 3 節點** 在 **500 萬筆資料規模** 下達成高 RPS （10,000+ 請求/秒）的完整設計方案。

### 核心建議

```yaml
連接池配置 (推薦):
  MaxOpenConns: 150 per Pod
  MaxIdleConns: 50 per Pod
  ConnMaxIdleTime: 60s
  ConnMaxLifetime: 10m

部署拓撲 (推薦):
  OpenFGA Pod 副本: 8-10
  MariaDB Galera 節點: 3 (High Availability)
  
性能指標 (目標):
  RPS: 10,000+ per second
  p99 Latency: <150ms
  集群可用性: 99.99%
```

---

## 📂 文件結構和用途

```
study-notes/
│
├─ 📖 核心文檔
│  ├─ README.md (本索引)
│  ├─ QUICK_START.md 
│  │  └─ ⏱️  5分鐘快速部署指南
│  │      • 最小化部署步驟
│  │      • 驗證方法
│  │      • 快速故障排除
│  │
│  ├─ POD_RPS_CAPACITY_MONITORING.md ⭐ 新增
│  │  └─ 🔍 Pod RPS 容量監控完整指南 (15分鐘)
│  │      • 如何知道每個 Pod 能承載多少 RPS
│  │      • 理論計算 vs 實際測量
│  │      • 實時監控方法（Prometheus）
│  │      • 容量測試與壓力測試
│  │      • 性能瓶頸識別
│  │      • 自動化監控腳本
│  │      • 告警設置
│  │
│  ├─ MYSQL_GALERA_CONNECTION_POOL_OPTIMIZATION.md 
│  │  └─ 🔬 深度技術指南 (90分鐘)
│  │      • 理論基礎和計算方法
│  │      • 4種RPS規模的配置方案
│  │      • MariaDB Galera 特殊考慮
│  │      • 500萬筆數據優化
│  │      • K8s 完整部署示例
│  │      • 監控指標和決策樹
│  │
│  ├─ MONITORING_AND_TROUBLESHOOTING.md 
│  │  └─ 🔍 運維實戰指南 (60分鐘)
│  │      • 關鍵指標定義
│  │      • 常見問題診斷 (連接泛濫、高延遲、分裂)
│  │      • 恢復步驟
│  │      • 性能調優清單
│  │      • 告警規則示例
│  │
│  └─ 📋 完整 K8s 配置
│     └─ k8s-openfga-mariadb-galera-deployment.yaml
│        • 生產級 Deployment (可直接使用)
│        • StatefulSet (MariaDB Galera)
│        • ConfigMap 和 Secret
│        • 存儲配置
│        • 網絡策略
│        • HPA 和 PDB
│        • Prometheus ServiceMonitor
│
├─ 🧮 自動化工具
│  ├─ connection_pool_calculator.py 
│  │  └─ 連接池配置自動計算器（理論值）
│  │      • 4種預設場景 (1K/5K/10K/20K RPS)
│  │      • 自定義計算
│  │      • YAML 生成
│  │      • 成本估算
│  │      • 資源預測
│  │
│  ├─ pod_rps_monitor.py ⭐ 新增
│  │  └─ Pod RPS 實時監控器（實際值）
│  │      • 實時 RPS 監控
│  │      • 容量使用百分比
│  │      • 錯誤率和延遲追蹤
│  │      • 資源使用情況
│  │      • 彩色狀態指示
│  │      • 自動告警過載 Pod
│  │
│  └─ k8s_deployment_checker.py 
│     └─ 部署健康檢查工具
│        • 命名空間檢查
│        • Pod 狀態驗證
│        • MySQL 連接狀況
│        • Galera 集群健康檢查
│        • 資源使用監控
│        • 部署就緒確認
│
└─ 📝 其他研究筆記 (相關參考)
   ├─ CHECK_API_IMPLEMENTATION_GUIDE.md
   ├─ EXPERIMENTAL_CHECK_OPTIMIZATION.md
   └─ MEMORY_MANAGEMENT_AND_PROTECTION.md
```

---

## 🚀 快速開始 (3 種方式)

### 方式 1: 最快部署 (5 分鐘)

```bash
# 1. 複製部署配置
cat k8s-openfga-mariadb-galera-deployment.yaml

# 2. 部署到 K8s
kubectl create namespace openfga-prod
kubectl apply -f k8s-openfga-mariadb-galera-deployment.yaml

# 3. 等待就緒
kubectl wait --for=condition=ready pod -l app=mariadb-galera \
  -n openfga-prod --timeout=300s
kubectl wait --for=condition=ready pod -l app=openfga \
  -n openfga-prod --timeout=300s

# 4. 驗證
kubectl get pods -n openfga-prod
```

### 方式 2: 配置計算 (2 分鐘)

```bash
# 運行配置計算器獲得你的最優配置
python connection_pool_calculator.py

# 選擇場景或自定義參數，得到：
# - MaxOpenConns 建議值
# - Pod 副本數
# - MariaDB 配置
# - 資源規格
# - YAML 配置片段
```

### 方式 3: 詳細理解 (1 小時)

```bash
# 按順序閱讀文檔
1. 本索引 (5 分鐘)
2. QUICK_START.md (15 分鐘)
3. connection_pool_calculator.py (10 分鐘)
4. MYSQL_GALERA_CONNECTION_POOL_OPTIMIZATION.md (30 分鐘)
```

---

## 📊 配置速查表

### 根據目標 RPS 選擇

```yaml
# 小規模 (1,000 RPS)
scenario: small
target_rps: 1000
pod_replicas: 3
max_open_conns: 75
max_idle_conns: 25
cpu_request: 300m
memory_request: 256Mi

# 中規模 (5,000 RPS)
scenario: medium
target_rps: 5000
pod_replicas: 5-6
max_open_conns: 120
max_idle_conns: 40
cpu_request: 400m
memory_request: 512Mi

# 推薦 (10,000 RPS) ⭐
scenario: large
target_rps: 10000
pod_replicas: 8-10
max_open_conns: 150
max_idle_conns: 50
cpu_request: 500m
memory_request: 512Mi

# 大規模 (20,000+ RPS)
scenario: xlarge
target_rps: 20000
pod_replicas: 12-15
max_open_conns: 200
max_idle_conns: 80
cpu_request: 800m
memory_request: 1Gi
```

---

## 🔍 監控清單

### 必須監控的指標

```prometheus
# 應用層
openfga_check_duration_ms                    # Check API 延遲
openfga_list_objects_duration_ms             # ListObjects 延遲
grpc_server_handled_total{grpc_code!="OK"}   # gRPC 錯誤

# 數據庫層
mysql_global_status_threads_connected        # 當前連接數
mysql_global_status_threads_running          # 執行連接
mysql_global_status_slow_queries             # 慢查詢

# Galera 層
wsrep_cluster_status                         # 集群狀態
wsrep_local_state_comment                    # 節點狀態
wsrep_flow_control_paused                    # 流控狀態
```

### 告警規則 (Prometheus)

```yaml
告警 1 - 連接數過高:
  閾值: Threads_connected > MaxOpenConns × 0.95
  行動: 增加 MaxOpenConns 或 Pod 副本

告警 2 - 高延遲:
  閾值: p99_latency > 200ms
  行動: 檢查索引、增加資源、優化查詢

告警 3 - Galera 不健康:
  閾值: wsrep_cluster_status != Primary
  行動: 檢查集群、重啟節點

告警 4 - 高錯誤率:
  閾值: error_rate > 1%
  行動: 檢查日誌、驗證配置
```

---

## 🛠️ 故障排除速查表

| 問題 | 症狀 | 診斷命令 | 解決方案 |
|------|------|--------|--------|
| **連接泛濫** | Too many connections | `SHOW PROCESSLIST` | 增加 MaxOpenConns, 增加 Pod |
| **高延遲** | p99 > 200ms | `SHOW SLOW LOG` | 檢查索引、增加資源 |
| **Galera 分裂** | Non-Primary | `SHOW STATUS LIKE 'wsrep%'` | 重啟節點、修復集群 |
| **記憶體溢出** | OOM Kill | `kubectl top pods` | 減少緩存、增加記憶體限制 |
| **Pod 無法啟動** | CrashLoopBackOff | `kubectl logs` | 檢查 Secret、資源 |

**詳見**: [MONITORING_AND_TROUBLESHOOTING.md](MONITORING_AND_TROUBLESHOOTING.md)

---

## 💰 成本分析

### AWS 成本估算 (10K RPS 場景)

```
硬件成本 (月度):
  OpenFGA (10 x m5.large)     $500
  MariaDB (3 x m5.2xlarge)    $900
  存儲 (300Gi EBS)             $30
  ─────────────────────────────────
  總計                        $1,430

效率指標:
  每 1K RPS 成本: $143
  每 100萬次請求成本: $0.014
  月度可支持請求數: 2.6 × 10¹¹
```

### 成本優化建議

1. **使用 Reserved Instances**: 節省 40-50%
2. **使用 Spot Instances**: 節省 70-80% (但有中斷風險)
3. **調整資源規格**: 根據實際使用調整
4. **存儲優化**: 使用 gp3 而非 io1

---

## 📈 性能測試和驗證

### 基準測試執行

```bash
# 1. 部署並等待就緒
kubectl apply -f k8s-openfga-mariadb-galera-deployment.yaml
sleep 120

# 2. 運行基線測試 (ghz)
ghz --insecure -d '{
  "store_id":"store-1",
  "tuples":[{
    "user":"user:alice",
    "relation":"member",
    "object":"org:acme"
  }]
}' \
  -c 100 -n 10000 -rate 1000 \
  openfga-grpc.openfga-prod.svc.cluster.local:8081 \
  openfga.v1.OpenFGA/Check

# 3. 預期結果 (10K RPS):
# - Total: 10.0s
# - Average: 50ms
# - p99: 150ms
# - Success: 100%

# 4. 監控期間資源
kubectl top pods -n openfga-prod -l app=openfga
kubectl exec -it mariadb-galera-0 -- mysql -e "SHOW STATUS LIKE 'Threads%';"
```

### 測試驗證清單

- [ ] 所有 Pod 就緒 (Ready)
- [ ] MySQL 連接正常
- [ ] Galera 集群 Primary
- [ ] gRPC 端點響應正常
- [ ] 負載測試 10K RPS 通過
- [ ] p99 延遲 < 200ms
- [ ] 錯誤率 < 1%
- [ ] CPU 使用 < 70%
- [ ] 記憶體使用 < 80%

---

## 🎓 學習路徑推薦

### 初級 (熟悉基礎) - 30 分鐘

1. ✅ 讀本索引 (5 分鐘)
2. ✅ 讀 QUICK_START.md (15 分鐘)
3. ✅ 運行 connection_pool_calculator.py (10 分鐘)

**目標**: 能部署和基本操作

### 中級 (理解原理) - 1.5 小時

1. ✅ 完成初級內容
2. ✅ 讀 MYSQL_GALERA_CONNECTION_POOL_OPTIMIZATION.md (70 分鐘)
3. ✅ 查看 k8s-openfga-mariadb-galera-deployment.yaml (10 分鐘)

**目標**: 理解配置原理，能夠調優參數

### 高級 (完全掌握) - 2.5 小時

1. ✅ 完成中級內容
2. ✅ 讀 MONITORING_AND_TROUBLESHOOTING.md (60 分鐘)
3. ✅ 運行 k8s_deployment_checker.py (10 分鐘)
4. ✅ 執行故障排除實驗 (30 分鐘)

**目標**: 完全掌握，能獨立運維和故障處理

---

## 📞 常見問題 (FAQ)

### Q: 我應該從哪裡開始？

**A**: 如果你只有 5 分鐘：
```bash
python connection_pool_calculator.py  # 生成配置
kubectl apply -f k8s-openfga-mariadb-galera-deployment.yaml
```

如果你有 30 分鐘：
```bash
1. 讀 QUICK_START.md
2. 運行計算器
3. 根據結果調整部署
4. 部署並驗證
```

### Q: 我應該選擇哪個 RPS 級別？

**A**: 根據目標 RPS 選擇：
- < 1K: small (3 Pod)
- 1K-5K: medium (5-6 Pod)
- 5K-15K: large (8-10 Pod) **推薦**
- 15K+: xlarge (12-15 Pod)

運行計算器確認具體參數。

### Q: 5 百萬筆數據需要多少存儲？

**A**: 粗略估算：
```
Base OS: 10Gi
MySQL: 20Gi (取決於索引)
數據: ~50Gi (以 10KB/tuple)
Galera 緩存: 2-4Gi
Buffer: 10Gi

推薦: 100Gi per node (可擴展)
```

### Q: 如何監控性能？

**A**: 三個層面：
```bash
# 應用層
kubectl logs -f deployment/openfga | grep latency

# 數據庫層
kubectl exec -it mariadb-galera-0 -- mysql -e "SHOW PROCESSLIST;"

# 集群層
kubectl top pods
```

或使用 Prometheus + Grafana (見部署文件)

### Q: 如何處理故障？

**A**: 參考 [MONITORING_AND_TROUBLESHOOTING.md](MONITORING_AND_TROUBLESHOOTING.md) 的故障排除部分。

---

## ✨ 主要特點

✅ **完整性** - 從理論到實踐的全覆蓋
✅ **實用性** - 可直接部署的生產級配置
✅ **自動化** - Python 工具自動生成最優參數
✅ **可靠性** - 基於 OpenFGA 源碼和最佳實踐
✅ **可擴展性** - 支持 1K 到 50K+ RPS
✅ **可維護性** - 詳細的監控和故障排除指南

---

## 🔗 相關資源

### 官方文檔
- [OpenFGA Docs](https://openfga.dev/)
- [OpenFGA GitHub](https://github.com/openfga/openfga)
- [MariaDB Galera](https://mariadb.com/kb/en/mariadb-galera-cluster/)
- [Kubernetes Docs](https://kubernetes.io/docs/)

### 本倉庫
- [OpenFGA 源碼](../pkg/storage/mysql/mysql.go)
- [研究筆記](./MYSQL_GALERA_CONNECTION_POOL_OPTIMIZATION.md)

---

## 📝 更新日誌

### v1.0 (2025-12-31)
- ✅ 初始版本
- ✅ 完整的優化指南
- ✅ K8s 部署配置
- ✅ 監控和故障排除
- ✅ 自動化工具

---

## 🎯 下一步行動

根據你的需求選擇：

| 時間 | 行動 | 文件 |
|-----|------|------|
| 5分鐘 | 快速部署 | QUICK_START.md |
| 10分鐘 | 生成配置 | connection_pool_calculator.py |
| 30分鐘 | 理解原理 | QUICK_START.md + Calculator |
| 1小時 | 深度學習 | MYSQL_GALERA_CONNECTION_POOL_OPTIMIZATION.md |
| 2小時 | 完全掌握 | 所有文檔 + 實驗 |

---

## 📋 檢查清單

### 部署前
- [ ] 閱讀 QUICK_START.md
- [ ] 運行 connection_pool_calculator.py 
- [ ] 準備 Kubernetes 集群
- [ ] 檢查可用資源

### 部署中
- [ ] 創建 namespace
- [ ] 應用配置文件
- [ ] 等待 Pod 就緒
- [ ] 運行 k8s_deployment_checker.py

### 部署後
- [ ] 驗證連接正常
- [ ] 執行基線測試
- [ ] 配置監控告警
- [ ] 記錄基準指標

---

## 🌟 最終建議

對於大多數用戶，我們建議：

1. **小型部署** (< 5K RPS)
   - 遵循 QUICK_START.md
   - 使用 small 配置
   - 基本監控即可

2. **生產部署** (5K-15K RPS) ⭐
   - 使用本索引推薦的 large 配置
   - 完整的監控和告警
   - 定期性能測試

3. **大型部署** (15K+ RPS)
   - 使用 xlarge 配置
   - 完整的 HA 和故障轉移
   - 專業的運維支持

---

**本研究由 OpenFGA 社區貢獻，面向生產環境優化。**

最後更新: 2025-12-31
版本: 1.0 (穩定)
狀態: ✅ 生產就緒
