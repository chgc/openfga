# K8s + MariaDB Galera 連接池優化設計指南

## 環境架構概述

- **K8s 環境**: OpenFGA 多個副本（Pods）
- **MariaDB Galera**: 3 個節點的同步複製集群
- **資料量**: 500 萬筆
- **目標**: 高 RPS（每秒請求數）設計

---

## 1. 核心概念

### 1.1 連接池核心參數

OpenFGA MySQL 連接池由以下參數控制：

| 參數                | 環境變數                               | 說明                            | 預設值 | 備註           |
| ------------------- | -------------------------------------- | ------------------------------- | ------ | -------------- |
| **MaxOpenConns**    | `OPENFGA_DATASTORE_MAX_OPEN_CONNS`     | 最大開放連接數                  | 30     | 關鍵參數       |
| **MaxIdleConns**    | `OPENFGA_DATASTORE_MAX_IDLE_CONNS`     | 最大空閒連接數                  | 10     | MySQL 預設為 2 |
| **MinOpenConns**    | `OPENFGA_DATASTORE_MIN_OPEN_CONNS`     | 最小開放連接數（PostgreSQL 用） | 0      | MySQL 不支持   |
| **ConnMaxIdleTime** | `OPENFGA_DATASTORE_CONN_MAX_IDLE_TIME` | 連接最大空閒時間                | 0      | 建議設置       |
| **ConnMaxLifetime** | `OPENFGA_DATASTORE_CONN_MAX_LIFETIME`  | 連接最大生命週期                | 0      | 建議設置       |

### 1.2 連接的生命週期

```
建立連接 → 空閒等待 → 執行查詢 → 空閒等待 → 關閉/復用
  ↑                                         ↓
  └─────────────────────────────────────────┘
            重複復用（直到過期）
```

---

## 2. 理論計算基礎

### 2.1 高 RPS 環境下的連接需求

對於 OpenFGA 的典型場景：

- **Check API**: 平均查詢時間 ~10-50ms
- **List Objects API**: 查詢時間 ~50-200ms
- **Write/Delete API**: 執行時間 ~20-100ms

**連接需求計算**:

```
最少需要的連接數 = (RPS × 平均查詢時間 / 1000) × 安全係數(1.5-2)

例如:
- 目標 RPS: 10,000
- 平均查詢時間: 50ms
- 安全係數: 1.5
- 需要連接數 = (10,000 × 50 / 1000) × 1.5 = 750 個連接
```

### 2.2 單個 Pod 的連接估算

假設 K8s 集群中每個 OpenFGA Pod：

```
Pod 連接數 = (該 Pod 的 RPS × 平均延遲) / 1000 × 1.3

單個 Pod 的 RPS = 總 RPS / Pod 副本數
```

**例子**:

- 總 RPS: 10,000
- Pod 副本: 10
- 每 Pod RPS: 1,000
- 平均延遲: 50ms
- 每 Pod 連接: (1,000 × 50 / 1000) × 1.3 = 65 個連接

---

## 3. MariaDB Galera 特殊考慮

### 3.1 Galera 的連接特性

MariaDB Galera 是**同步複製**集群，有以下特點：

| 特性                       | 影響               | 對策                            |
| -------------------------- | ------------------ | ------------------------------- |
| 寫入所有節點執行           | 寫入延遲較高       | 增加 MaxOpenConns，配置連接隊列 |
| 3 個節點高可用             | 單點故障不影響     | 連接可以自動轉移到其他節點      |
| 同步複製確保一致性         | 讀寫一致           | 可以在任何節點讀取              |
| State Transfer（ST）期間慢 | 集群重啟時響應變慢 | 做好超時配置和重試機制          |

### 3.2 連接分配策略

對於 3 節點 Galera：

```
總連接數 = MaxOpenConns × Pod 副本數 × 安全係數

例如:
MaxOpenConns = 100
Pod 副本 = 10
每個節點的平均連接 = (100 × 10) / 3 ≈ 333 個

負載分配: 均勻分配給 3 個節點（通過 DNS 或連接池）
```

---

## 4. 實踐配置方案

### 4.1 小規模高 RPS（1000-5000 RPS）

**推薦配置**:

```yaml
env:
  - name: OPENFGA_DATASTORE_MAX_OPEN_CONNS
    value: "100"
  - name: OPENFGA_DATASTORE_MAX_IDLE_CONNS
    value: "30"
  - name: OPENFGA_DATASTORE_CONN_MAX_IDLE_TIME
    value: "30s"
  - name: OPENFGA_DATASTORE_CONN_MAX_LIFETIME
    value: "5m"

deployment:
  replicas: 5 # 總連接：500，每節點平均 166
```

**說明**:

- `MaxOpenConns=100`: 每個 Pod 最多 100 個並發連接
- `MaxIdleConns=30`: 保留 30 個空閒連接以加速新請求
- `ConnMaxIdleTime=30s`: 30 秒後關閉空閒連接，節省資源
- `ConnMaxLifetime=5m`: 5 分鐘後強制更新連接，避免長連接問題

### 4.2 中規模高 RPS（5000-20000 RPS）

**推薦配置**:

```yaml
env:
  - name: OPENFGA_DATASTORE_MAX_OPEN_CONNS
    value: "150"
  - name: OPENFGA_DATASTORE_MAX_IDLE_CONNS
    value: "50"
  - name: OPENFGA_DATASTORE_CONN_MAX_IDLE_TIME
    value: "60s"
  - name: OPENFGA_DATASTORE_CONN_MAX_LIFETIME
    value: "10m"

deployment:
  replicas: 8 # 總連接：1200，每節點平均 400
```

**說明**:

- `MaxOpenConns=150`: 增加並發連接數
- `MaxIdleConns=50`: 提高連接復用率，減少連接建立開銷
- `ConnMaxIdleTime=60s`: 60 秒的空閒超時更均衡
- `ConnMaxLifetime=10m`: 更長的生命週期減少連接切換

### 4.3 大規模高 RPS（20000+ RPS）

**推薦配置**:

```yaml
env:
  - name: OPENFGA_DATASTORE_MAX_OPEN_CONNS
    value: "200"
  - name: OPENFGA_DATASTORE_MAX_IDLE_CONNS
    value: "80"
  - name: OPENFGA_DATASTORE_CONN_MAX_IDLE_TIME
    value: "90s"
  - name: OPENFGA_DATASTORE_CONN_MAX_LIFETIME
    value: "15m"

deployment:
  replicas: 12 # 總連接：2400，每節點平均 800
```

**說明**:

- 連接保持常態預熱狀態
- 較高的 MaxIdleConns 減少連接建立延遲
- 更長的超時和生命週期減少連接管理開銷

---

## 5. 針對 500 萬筆資料的具體優化

### 5.1 資料量影響分析

500 萬筆資料在 OpenFGA 中的影響：

```
假設典型場景：
- tuple 表: 500 萬條
- relationship 檢查: ~1-100ms（取決於圖深度）
- 索引有效: 確保 object_id, subject_id, relation 上有複合索引
```

### 5.2 針對大資料量的連接池調優

```yaml
# 為大資料量優化的配置
env:
  # 由於查詢可能更複雜，增加超時
  - name: OPENFGA_DATASTORE_MAX_OPEN_CONNS
    value: "180" # 比基準增加 20%

  - name: OPENFGA_DATASTORE_MAX_IDLE_CONNS
    value: "60" # 高比例閒置連接

  - name: OPENFGA_DATASTORE_CONN_MAX_IDLE_TIME
    value: "120s" # 更長的空閒時間，減少頻繁建立/關閉

  - name: OPENFGA_DATASTORE_CONN_MAX_LIFETIME
    value: "20m" # 更長的生命週期

  # 其他相關配置
  - name: OPENFGA_GRPC_UPSTREAMTIMEOUT
    value: "30s" # 增加 gRPC 超時

  - name: OPENFGA_HTTP_UPSTREAMTIMEOUT
    value: "30s" # 增加 HTTP 超時
```

### 5.3 MariaDB Galera 側的優化

```sql
-- 在 MariaDB 上執行（所有節點）
SET GLOBAL max_connections = 2000;  -- 容納所有 OpenFGA 連接

SET GLOBAL max_allowed_packet = 64M;  -- 支持大查詢

-- 連接管理
SET GLOBAL interactive_timeout = 600;      -- 600 秒（10 分鐘）
SET GLOBAL wait_timeout = 600;             -- 600 秒

-- 性能調優
SET GLOBAL key_buffer_size = 512M;
SET GLOBAL innodb_buffer_pool_size = 8G;   -- 根據可用記憶體調整
SET GLOBAL innodb_log_file_size = 512M;

-- Galera 特定調優
SET GLOBAL wsrep_slave_threads = 8;        -- 應用事務的線程數
SET GLOBAL gcache.size = 2G;               -- Galera 緩存大小
```

---

## 6. K8s 部署配置示例

### 6.1 完整的 Deployment 配置

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openfga
  namespace: default
spec:
  replicas: 8 # 根據 RPS 調整
  selector:
    matchLabels:
      app: openfga
  template:
    metadata:
      labels:
        app: openfga
    spec:
      # 反親和性：分散到多個節點
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - openfga
                topologyKey: kubernetes.io/hostname

      containers:
        - name: openfga
          image: openfga/openfga:latest
          ports:
            - containerPort: 8080 # HTTP
            - containerPort: 8081 # gRPC

          # 關鍵的連接池配置
          env:
            # 資料庫連接
            - name: OPENFGA_DATASTORE_ENGINE
              value: "mysql"

            - name: OPENFGA_DATASTORE_URI
              value: "root:password@tcp(mariadb-galera.default:3306)/openfga"

            # 連接池參數
            - name: OPENFGA_DATASTORE_MAX_OPEN_CONNS
              value: "150"

            - name: OPENFGA_DATASTORE_MAX_IDLE_CONNS
              value: "50"

            - name: OPENFGA_DATASTORE_CONN_MAX_IDLE_TIME
              value: "60s"

            - name: OPENFGA_DATASTORE_CONN_MAX_LIFETIME
              value: "10m"

            # 性能相關配置
            - name: OPENFGA_GRPC_UPSTREAMTIMEOUT
              value: "30s"

            - name: OPENFGA_HTTP_UPSTREAMTIMEOUT
              value: "30s"

            - name: OPENFGA_LOG_LEVEL
              value: "info"

          # 資源配置
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2000m"
              memory: "2Gi"

          # 健康檢查
          livenessProbe:
            grpc:
              port: 8081
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3

          readinessProbe:
            grpc:
              port: 8081
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 2

---
# MariaDB Galera StatefulSet 配置
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mariadb-galera
spec:
  serviceName: mariadb-galera
  replicas: 3
  selector:
    matchLabels:
      app: mariadb-galera
  template:
    metadata:
      labels:
        app: mariadb-galera
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchExpressions:
                  - key: app
                    operator: In
                    values:
                      - mariadb-galera
              topologyKey: kubernetes.io/hostname

      containers:
        - name: mariadb
          image: mariadb:11.4 # 或最新版本

          ports:
            - containerPort: 3306
              name: mysql
            - containerPort: 4567
              name: galera
            - containerPort: 4568
              name: ist
            - containerPort: 4444
              name: sst

          env:
            - name: MYSQL_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: mariadb-secret
                  key: root-password

            - name: MYSQL_DATABASE
              value: "openfga"

          resources:
            requests:
              cpu: "1000m"
              memory: "2Gi"
            limits:
              cpu: "4000m"
              memory: "4Gi"

          volumeMounts:
            - name: data
              mountPath: /var/lib/mysql
            - name: config
              mountPath: /etc/mysql/conf.d

  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: fast-ssd
        resources:
          requests:
            storage: 100Gi

---
# MariaDB Galera 配置 ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: mariadb-galera-config
data:
  galera.cnf: |
    [mysqld]
    # 基本設置
    max_connections = 2000
    max_allowed_packet = 64M
    bind-address = 0.0.0.0

    # Galera 設置
    [galera]
    wsrep_on = ON
    wsrep_provider = /usr/lib/galera/libgalera_smm.so
    wsrep_cluster_address = gcomm://mariadb-galera-0.mariadb-galera,mariadb-galera-1.mariadb-galera,mariadb-galera-2.mariadb-galera
    wsrep_cluster_name = galera-cluster
    wsrep_node_name = "${HOSTNAME}"
    wsrep_node_address = "${POD_IP}"
    wsrep_sst_method = rsync
    wsrep_slave_threads = 8

    # 性能
    innodb_buffer_pool_size = 2G
    innodb_log_file_size = 512M
    key_buffer_size = 512M

    # 連接管理
    interactive_timeout = 600
    wait_timeout = 600

    # Galera 緩存
    gcache.size = 2G
```

### 6.2 服務發現配置

```yaml
---
# Headless Service for Galera Pod to Pod communication
apiVersion: v1
kind: Service
metadata:
  name: mariadb-galera
spec:
  clusterIP: None
  selector:
    app: mariadb-galera
  ports:
    - port: 3306
      name: mysql
    - port: 4567
      name: galera
    - port: 4568
      name: ist
    - port: 4444
      name: sst

---
# 負載均衡服務（供 OpenFGA 使用）
apiVersion: v1
kind: Service
metadata:
  name: mariadb-galera-lb
spec:
  type: ClusterIP
  selector:
    app: mariadb-galera
  ports:
    - port: 3306
      targetPort: 3306
  sessionAffinity: None # 允許連接分散到各節點
```

---

## 7. 監控和調優指標

### 7.1 關鍵監控指標

```prometheus
# 連接池度量
mysql_global_status_threads_connected           # 當前連接數
mysql_global_status_threads_running            # 執行中的連接
mysql_global_status_questions                  # 總查詢數
mysql_global_status_slow_queries               # 慢查詢數

# OpenFGA 度量
openfga_datastore_query_duration_ms            # 查詢延遲
openfga_check_duration_ms                      # Check API 延遲
openfga_list_objects_duration_ms               # List Objects 延遲

# Galera 度量
wsrep_cluster_status                           # 集群狀態
wsrep_local_state_comment                      # 節點狀態
wsrep_flow_control_paused                      # 流控暫停
```

### 7.2 Prometheus 配置示例

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "openfga"
    static_configs:
      - targets: ["localhost:8080"]
    metrics_path: "/metrics"

  - job_name: "mariadb"
    static_configs:
      - targets: ["mariadb-exporter:9104"]
```

### 7.3 調優決策樹

```
監控連接指標
    ↓
┌─────────────────────────────────────────────┐
│ 連接數 < 30% MaxOpenConns?                  │
├──→ 是：連接充足，監控延遲和吞吐量         │
│        - 如果延遲高：檢查 SQL 和索引        │
│        - 如果吞吐量低：增加 Pod 副本       │
│                                             │
├──→ 否：連接接近上限                       │
│        - 如果有可用資源：增加 MaxOpenConns │
│        - 如果無資源：增加 Pod 副本         │
└─────────────────────────────────────────────┘
```

---

## 8. 常見問題和調試

### 8.1 連接超時問題

**症狀**: `context deadline exceeded`, `too many connections`

**診斷步驟**:

```bash
# 查看當前連接
kubectl exec -it mariadb-galera-0 -- mysql -e "SHOW PROCESSLIST;"

# 查看連接狀態
kubectl exec -it mariadb-galera-0 -- mysql -e "SHOW STATUS LIKE 'Threads%';"

# 查看最大連接限制
kubectl exec -it mariadb-galera-0 -- mysql -e "SHOW VARIABLES LIKE 'max_connections';"
```

**解決方案**:

1. 增加 `MaxOpenConns`
2. 增加 MariaDB 的 `max_connections`
3. 降低 `ConnMaxIdleTime`（更快回收）
4. 增加 Pod 副本

### 8.2 連接洩漏

**症狀**: 連接數持續增長，最終達到上限

**檢查**:

```go
// 在 OpenFGA 代碼中檢查
// pkg/storage/mysql/mysql.go 確保連接正確關閉

// 監控指標
SELECT COUNT(*) FROM INFORMATION_SCHEMA.PROCESSLIST
WHERE COMMAND = 'Sleep' AND TIME > 300;  -- 空閒 > 5 分鐘
```

**解決方案**:

- 設置合理的 `ConnMaxIdleTime`
- 監控應用日誌查找未關閉的連接
- 定期重啟 Pod（強制重建連接）

### 8.3 Galera 集群分裂

**症狀**: 某個節點變成 `non-primary`, 寫入失敗

**恢復步驟**:

```bash
# 檢查集群狀態
kubectl exec -it mariadb-galera-0 -- mysql -e \
  "SHOW STATUS LIKE 'wsrep%';"

# 強制加入集群
kubectl exec -it mariadb-galera-X -- mysql -e \
  "SET GLOBAL wsrep_cluster_address = 'gcomm://mariadb-galera-0.mariadb-galera,mariadb-galera-1.mariadb-galera,mariadb-galera-2.mariadb-galera';"

# 重啟 Pod
kubectl delete pod mariadb-galera-X
```

---

## 9. 容量規劃範例

### 9.1 5 百萬筆資料，目標 10K RPS 的部署

```yaml
# OpenFGA
Pod 副本: 10
MaxOpenConns 每 Pod: 150
最大總連接: 1500

# MariaDB Galera
3 節點
max_connections: 2000（容納所有 OpenFGA 連接 + 內部連接）
每節點平均連接: 1500 / 3 = 500

# 資源配置
OpenFGA Pod:
  - 請求: 500m CPU, 512Mi 記憶體
  - 限制: 2000m CPU, 2Gi 記憶體

MariaDB Pod:
  - 請求: 1000m CPU, 2Gi 記憶體
  - 限制: 4000m CPU, 4Gi 記憶體

存儲:
  - MariaDB 資料卷: 100Gi SSD（為未來增長預留）
```

### 9.2 成本估算

```
假設 AWS EC2 instance 成本 (美元/月):
- OpenFGA Pod (10 x m5.large): $500
- MariaDB 節點 (3 x m5.2xlarge): $900
- 存儲 (300Gi EBS): $30

月度成本: ~$1,430

每 RPS 成本: $0.00014
```

---

## 10. 最佳實踐清單

- [ ] 設置 `ConnMaxIdleTime` 避免連接洩漏
- [ ] 設置 `ConnMaxLifetime` 定期更新連接
- [ ] `MaxIdleConns` 設置為 `MaxOpenConns` 的 30-50%
- [ ] 使用 pod 反親和性分散 OpenFGA Pod
- [ ] 使用 pod 親和性將 OpenFGA 靠近 MariaDB
- [ ] 監控 `Threads_connected` 和 `Threads_running`
- [ ] 設置告警當連接 > 80% MaxOpenConns
- [ ] 定期執行 `SHOW PROCESSLIST` 檢查是否有卡住的連接
- [ ] 為 MariaDB 配置適當的 `gcache.size`
- [ ] 進行性能測試驗證配置
- [ ] 記錄基線指標方便未來對比

---

## 總結

對於 K8s + MariaDB Galera 3 節點 + 500 萬筆資料達成 10K+ RPS 的目標：

1. **連接池配置**: MaxOpenConns=150-200, MaxIdleConns=50-80
2. **Pod 副本**: 8-12 個根據實際 RPS
3. **MariaDB 配置**: max_connections=2000+, 適當調大 buffer pool
4. **監控關鍵指標**: 連接數、查詢延遲、Galera 集群狀態
5. **定期評估**: 根據實際 RPS 和延遲動態調整參數

確保有充足的資源預留和監控，這樣才能穩定支持高 RPS 負載。
