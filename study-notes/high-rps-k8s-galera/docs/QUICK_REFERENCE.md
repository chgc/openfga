# 🎯 快速參考卡 (Quick Reference)

## 🚀 30 秒快速開始

```bash
# Step 1: 生成配置
python study-notes/connection_pool_calculator.py

# Step 2: 部署
kubectl create namespace openfga-prod
kubectl apply -f study-notes/k8s-openfga-mariadb-galera-deployment.yaml

# Step 3: 驗證
python study-notes/k8s_deployment_checker.py
```

---

## 📊 配置速查表

### 10,000 RPS (推薦)

```yaml
OpenFGA:
  replicas: 8-10
  maxOpenConns: 150
  maxIdleConns: 50
  cpu: 500m / 2000m (req/lim)
  memory: 512Mi / 2Gi

MariaDB:
  nodes: 3
  maxConnections: 2000
  storage: 100Gi per node
  cpuRequest: 1000m
  memoryRequest: 2Gi
```

### 5,000 RPS (中規模)

```yaml
OpenFGA:
  replicas: 5-6
  maxOpenConns: 120
  maxIdleConns: 40
  cpu: 400m / 1500m
  memory: 256Mi / 1Gi

MariaDB:
  nodes: 3
  maxConnections: 1500
  storage: 50Gi per node
```

### 1,000 RPS (小規模)

```yaml
OpenFGA:
  replicas: 3
  maxOpenConns: 75
  maxIdleConns: 25
  cpu: 300m / 1000m
  memory: 256Mi / 512Mi

MariaDB:
  nodes: 3
  maxConnections: 1000
  storage: 50Gi per node
```

---

## 🔍 關鍵命令速查

### 部署相關

```bash
# 查看 Pod 狀態
kubectl get pods -n openfga-prod

# 查看詳細狀態
kubectl describe pod <pod-name> -n openfga-prod

# 查看 Pod 日誌
kubectl logs <pod-name> -n openfga-prod

# 進入 Pod
kubectl exec -it <pod-name> -n openfga-prod -- bash

# 縮放 Pod
kubectl scale deployment openfga --replicas=12 -n openfga-prod

# 更新環境變數
kubectl set env deployment/openfga \
  OPENFGA_DATASTORE_MAX_OPEN_CONNS=200 \
  -n openfga-prod
```

### 數據庫檢查

```bash
# 進入 MySQL
kubectl exec -it mariadb-galera-0 -n openfga-prod -- \
  mysql -u root -p'password'

# 查看連接數
SHOW STATUS LIKE 'Threads%';

# 查看集群狀態
SHOW STATUS LIKE 'wsrep%';

# 查看當前執行
SHOW PROCESSLIST;

# 查看慢查詢
SHOW SLOW LOG LIMIT 10;

# 檢查索引
SHOW INDEX FROM openfga.tuples;
```

### 監控相關

```bash
# 查看資源使用
kubectl top pods -n openfga-prod

# 監控 CPU/Memory
watch -n 2 'kubectl top pods -n openfga-prod'

# 查看連接數變化
watch -n 5 'kubectl exec -it mariadb-galera-0 -n openfga-prod -- \
  mysql -e "SHOW STATUS LIKE \"Threads_connected\";"'

# 監控日誌
kubectl logs -f deployment/openfga -n openfga-prod

# 查看事件
kubectl get events -n openfga-prod --sort-by='.lastTimestamp'
```

---

## ⚠️ 故障快速診斷

### 連接泛濫

```bash
# 檢查當前連接
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e \
  "SELECT COUNT(*) FROM INFORMATION_SCHEMA.PROCESSLIST;"

# 解決
kubectl set env deployment/openfga \
  OPENFGA_DATASTORE_MAX_OPEN_CONNS=200 \
  -n openfga-prod
```

### Pod 無法啟動

```bash
# 查看事件
kubectl describe pod <pod-name> -n openfga-prod

# 查看日誌
kubectl logs <pod-name> -n openfga-prod

# 常見原因和解決
# - CrashLoopBackOff: 檢查日誌看具體錯誤
# - Pending: 節點資源不足
# - ImagePullBackOff: 鏡像拉取失敗
```

### 高延遲

```bash
# 查看慢查詢
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e \
  "SELECT * FROM mysql.slow_log ORDER BY start_time DESC LIMIT 10;"

# 查看當前執行
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e \
  "SHOW PROCESSLIST;"

# 檢查連接數是否接近上限
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e \
  "SHOW STATUS LIKE 'Threads_connected';"
```

### Galera 不同步

```bash
# 檢查狀態
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e \
  "SHOW STATUS LIKE 'wsrep_cluster_status';"

# 重啟有問題的節點
kubectl delete pod mariadb-galera-2 -n openfga-prod

# 等待恢復
sleep 30
kubectl exec -it mariadb-galera-2 -n openfga-prod -- mysql -e \
  "SHOW STATUS LIKE 'wsrep_local_state_comment';"
```

---

## 💾 文件位置速查

| 內容 | 文件 | 大小 | 閱讀時間 |
|------|------|------|--------|
| 項目總覽 | README.md | 10KB | 20分鐘 |
| 快速開始 | QUICK_START.md | 15KB | 15分鐘 |
| 配置計算 | connection_pool_calculator.py | 8KB | 運行時 |
| 完整指南 | MYSQL_GALERA_CONNECTION_POOL_OPTIMIZATION.md | 50KB | 60分鐘 |
| 運維指南 | MONITORING_AND_TROUBLESHOOTING.md | 40KB | 60分鐘 |
| K8s 配置 | k8s-openfga-mariadb-galera-deployment.yaml | 30KB | 參考 |
| 部署檢查 | k8s_deployment_checker.py | 12KB | 運行時 |
| 資源導航 | INDEX.md | 25KB | 15分鐘 |
| 視覺總結 | SUMMARY.md | 20KB | 10分鐘 |

---

## 📱 按場景快速查詢

### 我只有 5 分鐘
```
1. 看本文件的 30 秒快速開始
2. 部署即用
```

### 我有 15 分鐘
```
1. 讀 QUICK_START.md
2. 運行 connection_pool_calculator.py
3. 根據輸出修改配置
4. 部署
```

### 我有 1 小時
```
1. 讀 README.md 和 QUICK_START.md (30 分鐘)
2. 讀完 connection_pool_calculator.py 代碼 (10 分鐘)
3. 理解 K8s 配置文件 (20 分鐘)
```

### 我要完全掌握
```
1. 按推薦學習時間安排 (見 INDEX.md)
2. 閱讀全部文檔 (3-4 小時)
3. 執行實驗和故障模擬 (2 小時)
```

### 我有生產問題
```
1. 立即查看 MONITORING_AND_TROUBLESHOOTING.md
2. 找對應的故障類型
3. 按步驟診斷和解決
```

---

## 🎯 性能測試命令

```bash
# 使用 ghz 進行 gRPC 壓力測試
ghz --insecure \
  -d '{"store_id":"store-1","tuples":[{"user":"user:alice","relation":"member","object":"org:acme"}]}' \
  -c 100 -n 10000 -rate 1000 \
  openfga-grpc.openfga-prod.svc.cluster.local:8081 \
  openfga.v1.OpenFGA/Check

# 使用 curl 進行 HTTP 測試
for i in {1..100}; do
  curl -X POST http://localhost:8080/v1/check \
    -H "Content-Type: application/json" \
    -d '{"store_id":"store-1","tuples":[{"user":"user:alice","relation":"member","object":"org:acme"}]}'
done

# 使用 ab (Apache Bench) 進行簡單測試
ab -n 10000 -c 100 http://localhost:8080/v1/check
```

---

## 🔐 安全檢查清單

- [ ] Secret 中密碼已修改 (不是默認值)
- [ ] NetworkPolicy 已配置 (限制出入流量)
- [ ] RBAC 已配置 (Pod 權限最小化)
- [ ] 日誌記錄已啟用 (便於審計)
- [ ] 備份已配置 (每日備份)
- [ ] SSL/TLS 已配置 (如需外部訪問)
- [ ] Pod 安全上下文已設置 (無特權)

---

## 📈 性能優化建議優先級

### 第 1 優先 (必做)

- [ ] 設置正確的 MaxOpenConns 和 MaxIdleConns
- [ ] 建立複合索引 (object_id, subject_id, relation)
- [ ] 配置 Galera gcache.size
- [ ] 設置 Pod 資源請求和限制

### 第 2 優先 (重要)

- [ ] 啟用 Prometheus 監控
- [ ] 配置告警規則
- [ ] 進行基線性能測試
- [ ] 啟用 Pod 反親和性分散

### 第 3 優先 (可選)

- [ ] 配置 Grafana 儀表板
- [ ] 實施讀取複製分離 (高級)
- [ ] 設置連接池代理 (如 ProxySQL)
- [ ] 實施應用層緩存層

---

## 💡 常見誤解更正

| 誤解 | 事實 |
|------|------|
| MaxIdleConns = 0 很好 | ❌ 會頻繁創建連接，降低性能 |
| 連接數越多越好 | ❌ 消耗資源，應根據需要調整 |
| Galera 有 Leader 節點 | ❌ 所有節點都是 Primary，無 Leader |
| 可以在線無縫升級 MySQL | ✅ Galera 支持，但要小心 |
| 只需監控 CPU 和內存 | ❌ 還需監控連接、延遲、錯誤 |

---

## 📞 快速支持

### 常見問題直達

- **連接問題**: → MONITORING_AND_TROUBLESHOOTING.md 第 2.1 節
- **延遲問題**: → MONITORING_AND_TROUBLESHOOTING.md 第 2.2 節
- **集群問題**: → MONITORING_AND_TROUBLESHOOTING.md 第 2.3 節
- **配置問題**: → MYSQL_GALERA_CONNECTION_POOL_OPTIMIZATION.md 第 4 節
- **部署問題**: → QUICK_START.md

---

## 🎓 必讀文件排序

```
初級用戶優先級:
1️⃣  本文件 (5 分鐘)
2️⃣  QUICK_START.md (15 分鐘)
3️⃣  README.md (20 分鐘)
4️⃣  connection_pool_calculator.py (運行時)

中級用戶優先級:
1️⃣  完成初級內容
2️⃣  MYSQL_GALERA_CONNECTION_POOL_OPTIMIZATION.md (60 分鐘)
3️⃣  k8s-openfga-mariadb-galera-deployment.yaml (參考)

高級用戶優先級:
1️⃣  完成中級內容
2️⃣  MONITORING_AND_TROUBLESHOOTING.md (60 分鐘)
3️⃣  k8s_deployment_checker.py (實驗)
```

---

## ✅ 部署檢查

### 前置條件

```bash
# 檢查 kubectl
kubectl version

# 檢查集群
kubectl get nodes

# 檢查可用資源
kubectl describe nodes | grep -A 5 "Allocated resources"

# 確認可用存儲
kubectl get sc  # 應該有 fast-ssd
```

### 部署後驗證

```bash
# 全部通過？
python k8s_deployment_checker.py
# 所有項目應該顯示 ✅
```

---

**記住: 遇到問題時，先查本卡，再查對應文檔。❤️**

*最後更新: 2025-12-31*
*版本: 1.0*
