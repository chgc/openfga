# 連接池監控和故障排除指南

## 快速參考

### 關鍵指標監控命令

```bash
# 檢查 Galera 集群狀態
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SHOW STATUS LIKE 'wsrep%';
"

# 檢查當前連接數
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SHOW STATUS LIKE 'Threads%';
"

# 查看當前執行的查詢
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SHOW PROCESSLIST;
"

# 檢查連接池設置
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SHOW VARIABLES LIKE '%timeout%';
  SHOW VARIABLES LIKE 'max_connections';
"

# 查看 OpenFGA 日誌
kubectl logs -f deployment/openfga -n openfga-prod --all-containers=true

# 監控 OpenFGA Pod 資源使用
kubectl top pods -n openfga-prod -l app=openfga
```

---

## 1. 監控指標定義

### 1.1 數據庫層指標

| 指標                  | 說明         | 正常範圍             | 告警閾值             |
| --------------------- | ------------ | -------------------- | -------------------- |
| **Threads_connected** | 當前連接數   | < MaxOpenConns × 80% | > MaxOpenConns × 95% |
| **Threads_running**   | 執行中的連接 | < Pod RPS × 0.1      | > Pod RPS × 0.5      |
| **Questions**         | 總查詢數     | 線性增長             | 突然下降             |
| **Slow_queries**      | 慢查詢數     | < 1% of Questions    | > 5% of Questions    |
| **Aborted_connects**  | 連接失敗     | ≈ 0                  | > 10/分鐘            |
| **Aborted_clients**   | 客戶端中止   | 低                   | > 100/小時           |

### 1.2 應用層指標 (OpenFGA)

```prometheus
# 查詢延遲分佈
histogram_quantile(0.99, openfga_datastore_query_duration_ms)  # p99

# 連接池使用率
rate(openfga_sql_db_max_open_connections[5m])

# 檢查 API 延遲
openfga_check_duration_ms

# 列表 API 延遲
openfga_list_objects_duration_ms

# gRPC 錯誤率
rate(grpc_server_handled_total{grpc_code!="OK"}[5m])
```

### 1.3 Galera 特定指標

```sql
-- Galera 集群狀態
SHOW STATUS LIKE 'wsrep_cluster_status';        -- Primary / Non-Primary
SHOW STATUS LIKE 'wsrep_local_state_comment';   -- Synced / Donor
SHOW STATUS LIKE 'wsrep_flow_control_paused';   -- 流控暫停狀態
SHOW STATUS LIKE 'wsrep_replicated_bytes';      -- 複製的字節數
SHOW STATUS LIKE 'wsrep_received_bytes';        -- 收到的字節數
```

---

## 2. 常見問題診斷

### 2.1 連接泛濫 (Connection Overflow)

**症狀**:

```
Too many connections
ERROR 1040 (HY000): Too many connections
```

**診斷步驟**:

```bash
# 1. 檢查當前連接數
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SELECT COUNT(*) as total_connections FROM INFORMATION_SCHEMA.PROCESSLIST;
"

# 2. 按連接狀態分類
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SELECT COMMAND, STATE, COUNT(*) as count
  FROM INFORMATION_SCHEMA.PROCESSLIST
  GROUP BY COMMAND, STATE
  ORDER BY count DESC;
"

# 3. 檢查是否有空閒連接未關閉
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SELECT COUNT(*) as idle_over_5min
  FROM INFORMATION_SCHEMA.PROCESSLIST
  WHERE COMMAND = 'Sleep' AND TIME > 300;
"

# 4. 查看 OpenFGA Pod 狀況
kubectl describe pod <pod-name> -n openfga-prod

# 5. 檢查是否有 goroutine 洩漏
kubectl logs deployment/openfga -n openfga-prod | grep goroutine
```

**解決方案**:

1. **增加 MaxOpenConns**:

```yaml
env:
  - name: OPENFGA_DATASTORE_MAX_OPEN_CONNS
    value: "200" # 從 150 增加到 200
```

2. **降低 ConnMaxIdleTime**:

```yaml
env:
  - name: OPENFGA_DATASTORE_CONN_MAX_IDLE_TIME
    value: "30s" # 從 60s 減少到 30s
```

3. **增加 Pod 副本**:

```bash
kubectl scale deployment openfga --replicas=12 -n openfga-prod
```

4. **強制關閉冗餘連接**（謹慎使用）:

```sql
-- 關閉所有 > 5 分鐘的空閒連接
SELECT CONCAT('KILL ', id, ';')
FROM INFORMATION_SCHEMA.PROCESSLIST
WHERE COMMAND = 'Sleep' AND TIME > 300;

-- 複製上述查詢結果並執行
```

### 2.2 高延遲 (High Latency)

**症狀**:

```
OpenFGA Check API 響應時間 > 500ms
MySQL query 執行時間 > 100ms
```

**診斷步驟**:

```bash
# 1. 檢查慢查詢日誌
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SELECT * FROM mysql.slow_log ORDER BY start_time DESC LIMIT 10;
"

# 2. 檢查索引狀況
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SHOW INDEX FROM openfga.tuples;
"

# 3. 檢查表統計
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SELECT TABLE_NAME, TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH
  FROM INFORMATION_SCHEMA.TABLES
  WHERE TABLE_SCHEMA = 'openfga';
"

# 4. 檢查查詢執行計劃
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  EXPLAIN SELECT * FROM tuples WHERE object_id = 'user:alice';
"

# 5. 檢查 Galera 流控狀態
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SHOW STATUS LIKE 'wsrep_flow_control%';
"
```

**解決方案**:

1. **優化索引**:

```sql
-- 確保 tuples 表有複合索引
CREATE INDEX idx_object_subject_relation ON tuples(object_id, subject_id, relation);
CREATE INDEX idx_user_object ON tuples(user_id, object_id);

-- 檢查索引大小
SELECT INDEX_NAME, SEQ_IN_INDEX, COLUMN_NAME
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_SCHEMA = 'openfga' AND TABLE_NAME = 'tuples';
```

2. **增加 MaxOpenConns 來支持更多並發**:

```yaml
env:
  - name: OPENFGA_DATASTORE_MAX_OPEN_CONNS
    value: "200"
```

3. **啟用 MariaDB 查詢緩存** (可選):

```sql
SET GLOBAL query_cache_type = 1;
SET GLOBAL query_cache_size = 256M;
```

4. **檢查 Galera 性能參數**:

```sql
-- 增加 wsrep_slave_threads
SET GLOBAL wsrep_slave_threads = 16;

-- 增加 gcache 大小
SET GLOBAL wsrep_provider_options = "gcache.size=4G";
```

### 2.3 Galera 集群分裂 (Split Brain)

**症狀**:

```
wsrep_cluster_status = Non-Primary
wsrep_local_state_comment = Donor
某些節點拒絕連接
```

**診斷步驟**:

```bash
# 1. 檢查每個節點的狀態
for i in 0 1 2; do
  echo "=== mariadb-galera-$i ==="
  kubectl exec -it mariadb-galera-$i -n openfga-prod -- mysql -e \
    "SHOW STATUS LIKE 'wsrep%' \G"
done

# 2. 檢查集群通信
kubectl exec -it mariadb-galera-0 -n openfga-prod -- netstat -an | grep 4567

# 3. 查看 Galera 日誌
kubectl logs mariadb-galera-0 -n openfga-prod | grep -i "galera\|wsrep"
```

**恢復步驟**:

```bash
# 1. 重啟有問題的節點
kubectl delete pod mariadb-galera-2 -n openfga-prod

# 2. 等待節點重新加入集群
sleep 30
kubectl exec -it mariadb-galera-2 -n openfga-prod -- mysql -e \
  "SHOW STATUS LIKE 'wsrep_cluster_status';"

# 3. 如果仍然分裂，手動修復
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SET GLOBAL wsrep_cluster_address = 'gcomm://mariadb-galera-0.mariadb-galera,mariadb-galera-1.mariadb-galera,mariadb-galera-2.mariadb-galera';
"
```

### 2.4 大量連接超時

**症狀**:

```
context deadline exceeded
connection reset by peer
```

**診斷步驟**:

```bash
# 1. 檢查 OpenFGA 日誌中的超時
kubectl logs -f deployment/openfga -n openfga-prod | grep -i "timeout\|deadline"

# 2. 檢查網絡連通性
kubectl exec -it deployment/openfga -n openfga-prod -- \
  nc -zv mariadb-galera-lb.openfga-prod 3306

# 3. 檢查是否有包丟失
kubectl exec -it deployment/openfga -n openfga-prod -- \
  ping -c 10 mariadb-galera-lb.openfga-prod

# 4. 檢查 iptables 規則
kubectl exec -it deployment/openfga -n openfga-prod -- \
  iptables -L -n | grep 3306
```

**解決方案**:

1. **增加超時配置**:

```yaml
env:
  - name: OPENFGA_GRPC_UPSTREAMTIMEOUT
    value: "60s" # 從 30s 增加到 60s

  - name: OPENFGA_HTTP_UPSTREAMTIMEOUT
    value: "60s"

  - name: OPENFGA_DATASTORE_CONN_MAX_IDLE_TIME
    value: "120s"
```

2. **檢查網絡策略**:

```bash
# 驗證 NetworkPolicy 允許連接
kubectl get networkpolicy -n openfga-prod
kubectl describe networkpolicy openfga-network-policy -n openfga-prod
```

3. **增加 MariaDB 連接超時**:

```sql
SET GLOBAL interactive_timeout = 900;  -- 15 分鐘
SET GLOBAL wait_timeout = 900;
```

---

## 3. 性能調優清單

### 3.1 預部署檢查

- [ ] 驗證 OpenFGA 連接池參數（MaxOpenConns, MaxIdleConns）
- [ ] 驗證 MariaDB 的 `max_connections` 設置 ≥ 2000
- [ ] 驗證 Galera 集群初始化成功（3 個節點都是 Primary）
- [ ] 驗證 DNS 解析正確（mariadb-galera-lb 指向正確 IP）
- [ ] 檢查存儲卷是否足夠（至少 100Gi）
- [ ] 確認節點資源足夠（CPU, 記憶體）

### 3.2 部署後調優

```bash
# 1. 監控基線採集（運行 1 小時）
kubectl top pods -n openfga-prod --containers

# 2. 檢查 Pod 分布
kubectl get pods -o wide -n openfga-prod

# 3. 進行負載測試
# 使用 ghz 或 k6 進行壓力測試
ghz --insecure -d '{"store_id":"my-store","tuples":[{"user":"user:alice","relation":"can_view","object":"doc:123"}]}' \
  -m '{"metadata":"value"}' \
  -c 100 \
  -n 10000 \
  -rate 1000 \
  mariadb-galera-lb.openfga-prod:8081 \
  openfga.v1.OpenFGA/Check

# 4. 監控負載期間的指標
kubectl logs -f deployment/openfga -n openfga-prod
kubectl top pods -n openfga-prod -l app=mariadb-galera

# 5. 根據結果調整參數
# 如果連接接近上限 → 增加 MaxOpenConns
# 如果延遲高 → 增加 Pod 副本或優化查詢
# 如果 Galera 流控 → 增加 wsrep_slave_threads
```

### 3.3 調優參數速查表

```yaml
# 低 RPS (< 1000)
MaxOpenConns: 50
MaxIdleConns: 15
ConnMaxIdleTime: "30s"
Pod replicas: 3

# 中等 RPS (1000-5000)
MaxOpenConns: 100
MaxIdleConns: 30
ConnMaxIdleTime: "60s"
Pod replicas: 5

# 高 RPS (5000-20000)
MaxOpenConns: 150
MaxIdleConns: 50
ConnMaxIdleTime: "60s"
Pod replicas: 10

# 非常高 RPS (> 20000)
MaxOpenConns: 200
MaxIdleConns: 80
ConnMaxIdleTime: "90s"
Pod replicas: 15+
```

---

## 4. 性能測試指令

```bash
# 使用 ghz (gRPC 基準測試)
ghz --insecure \
  -d '{"store_id":"store-1","tuples":[{"user":"user:alice","relation":"member","object":"org:acme"}]}' \
  -c 100 \
  -n 10000 \
  -rate 1000 \
  localhost:8081 \
  openfga.v1.OpenFGA/Check

# 使用 k6 (HTTP 測試)
k6 run - <<EOF
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 100 },
    { duration: '1m30s', target: 1000 },
    { duration: '30s', target: 0 },
  ],
};

export default function() {
  let res = http.post('http://localhost:8080/v1/check', JSON.stringify({
    "store_id": "store-1",
    "tuples": [{"user": "user:alice", "relation": "member", "object": "org:acme"}]
  }));

  check(res, { 'status is 200': (r) => r.status === 200 });
}
EOF

# 監控期間的資源使用
watch -n 1 'kubectl top pods -n openfga-prod -l app=openfga'
watch -n 1 'kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "SHOW STATUS LIKE \"Threads%\";"'
```

---

## 5. 自動告警規則

```yaml
# Prometheus AlertRules
groups:
  - name: openfga
    rules:
      # 連接數接近上限
      - alert: HighDatabaseConnections
        expr: mysql_global_status_threads_connected > 1400 # MaxOpenConns=150 x 10 pods x 0.95
        for: 5m
        annotations:
          summary: "Database connections high: {{ $value }}/{{ maxConns }}"

      # 慢查詢過多
      - alert: HighSlowQueryRate
        expr: rate(mysql_global_status_slow_queries[5m]) > 0.5
        for: 5m
        annotations:
          summary: "Slow queries detected: {{ $value }}/sec"

      # Galera 集群不健康
      - alert: GaleraClusterUnhealthy
        expr: mysql_global_status_wsrep_cluster_status != 1
        for: 1m
        annotations:
          summary: "Galera cluster is not primary"

      # 高查詢延遲
      - alert: HighQueryLatency
        expr: histogram_quantile(0.99, openfga_datastore_query_duration_ms) > 100
        for: 5m
        annotations:
          summary: "p99 query latency high: {{ $value }}ms"

      # Pod OOM
      - alert: PodMemoryUsageHigh
        expr: sum(container_memory_usage_bytes{pod=~"openfga-.*"}) / sum(container_spec_memory_limit_bytes{pod=~"openfga-.*"}) > 0.9
        for: 2m
        annotations:
          summary: "Pod memory usage high: {{ $value | humanizePercentage }}"
```

這個完整的監控和故障排除指南應該能幫助你快速識別和解決高 RPS 環境下的各種問題。
