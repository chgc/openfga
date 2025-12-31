# K8s + MariaDB Galera OpenFGA 快速開始指南

## 快速部署（5 分鐘）

### 前置要求

- Kubernetes 集群（1.20+）
- kubectl 已配置
- 足夠的資源（至少 4 個 CPU，8GB 記憶體）

### 步驟 1：創建 Namespace

```bash
kubectl create namespace openfga-prod
```

### 步驟 2：部署完整堆棧

```bash
# 部署 Secret、ConfigMap、StorageClass
kubectl apply -f k8s-openfga-mariadb-galera-deployment.yaml -n openfga-prod

# 等待 Galera 初始化（2-3 分鐘）
kubectl wait --for=condition=ready pod \
  -l app=mariadb-galera \
  -n openfga-prod \
  --timeout=300s

# 等待 OpenFGA 啟動（1-2 分鐘）
kubectl wait --for=condition=ready pod \
  -l app=openfga \
  -n openfga-prod \
  --timeout=300s
```

### 步驟 3：驗證部署

```bash
# 檢查所有 Pod 狀態
kubectl get pods -n openfga-prod

# 輸出應該類似：
# NAME                       READY   STATUS    RESTARTS   AGE
# mariadb-galera-0           1/1     Running   0          2m
# mariadb-galera-1           1/1     Running   0          2m
# mariadb-galera-2           1/1     Running   0          2m
# openfga-7f9c8d5b9-xxxxx    1/1     Running   0          1m
# openfga-7f9c8d5b9-xxxxx    1/1     Running   0          1m
# ... (共 8 個 OpenFGA Pod)

# 檢查 Galera 集群狀態
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SHOW STATUS LIKE 'wsrep_cluster_status';
  SHOW STATUS WHERE variable_name LIKE 'Threads%';
"

# 應該看到：
# wsrep_cluster_status = Primary
# Threads_connected = (連接數)
# Threads_running = (執行連接數)
```

### 步驟 4：測試連接

```bash
# 進入 OpenFGA Pod
POD=$(kubectl get pods -n openfga-prod -l app=openfga -o jsonpath='{.items[0].metadata.name}')

# 測試 HTTP 端點
kubectl exec -it $POD -n openfga-prod -- \
  curl -X POST http://localhost:8080/v1/check \
  -H "Content-Type: application/json" \
  -d '{
    "store_id": "store-1",
    "tuples": [{"user": "user:alice", "relation": "member", "object": "org:acme"}]
  }'

# 預期輸出：
# {"allowed":true} 或類似的 OpenFGA 響應
```

---

## 配置參數快速參考

### 根據預期 RPS 調整配置

**修改 `k8s-openfga-mariadb-galera-deployment.yaml`**

```bash
# 使用 sed 快速修改（範例：目標 5000 RPS）

# 1. 修改 MaxOpenConns
sed -i 's/value: "150"  # MaxOpenConns/value: "120"/g' k8s-openfga-mariadb-galera-deployment.yaml

# 2. 修改 Pod 副本
sed -i 's/replicas: 8/replicas: 6/g' k8s-openfga-mariadb-galera-deployment.yaml

# 3. 重新應用配置
kubectl apply -f k8s-openfga-mariadb-galera-deployment.yaml -n openfga-prod

# 4. 檢查更新
kubectl rollout status deployment/openfga -n openfga-prod
```

### 常用配置組合

```yaml
# 1000 RPS 場景
OpenFGA Pod 副本: 3
MaxOpenConns: 75
MaxIdleConns: 25

# 5000 RPS 場景
OpenFGA Pod 副本: 6
MaxOpenConns: 120
MaxIdleConns: 40

# 10000 RPS 場景
OpenFGA Pod 副本: 10
MaxOpenConns: 150
MaxIdleConns: 50

# 20000+ RPS 場景
OpenFGA Pod 副本: 15
MaxOpenConns: 200
MaxIdleConns: 80
```

---

## 監控儀表板

### 使用 Prometheus + Grafana

```bash
# 1. 部署 Prometheus Operator (如果還沒有)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace

# 2. 檢查 ServiceMonitor 是否被選中
kubectl get servicemonitor -n openfga-prod

# 3. 訪問 Prometheus
kubectl port-forward -n monitoring svc/prometheus-operated 9090:9090

# 4. 訪問 Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# 預設用戶: admin, 密碼: prom-operator
```

### 關鍵指標查詢

在 Prometheus 中執行以下查詢：

```promql
# 當前連接數
mysql_global_status_threads_connected

# 連接數佔比
mysql_global_status_threads_connected / 1500  # 假設上限 1500

# 每秒查詢數
rate(mysql_global_status_questions[5m])

# p99 查詢延遲
histogram_quantile(0.99, openfga_datastore_query_duration_ms)

# gRPC 錯誤率
rate(grpc_server_handled_total{grpc_code!="OK"}[5m])

# Galera 集群狀態
mysql_global_status_wsrep_cluster_status
```

---

## 故障排除快速指南

### 連接數過高

```bash
# 查看當前連接
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SELECT COUNT(*) as total_connections FROM INFORMATION_SCHEMA.PROCESSLIST;
"

# 查看慢連接
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SELECT ID, USER, TIME, COMMAND, INFO
  FROM INFORMATION_SCHEMA.PROCESSLIST
  WHERE TIME > 60
  ORDER BY TIME DESC;
"

# 解決方案：增加 MaxOpenConns
kubectl set env deployment/openfga \
  OPENFGA_DATASTORE_MAX_OPEN_CONNS=200 \
  -n openfga-prod
```

### Pod 無法啟動

```bash
# 查看 Pod 事件
kubectl describe pod <pod-name> -n openfga-prod

# 查看 Pod 日誌
kubectl logs <pod-name> -n openfga-prod

# 常見原因：
# 1. 資源不足 → 增加節點或釋放資源
# 2. Galera 未就緒 → 等待 Galera 初始化
# 3. Secret 不存在 → 檢查 Secret 創建
```

### 查詢超時

```bash
# 檢查慢查詢日誌
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SELECT * FROM mysql.slow_log
  ORDER BY start_time DESC LIMIT 5;
"

# 檢查當前執行的查詢
kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e "
  SHOW PROCESSLIST;
"

# 增加超時時間
kubectl set env deployment/openfga \
  OPENFGA_GRPC_UPSTREAMTIMEOUT=60s \
  OPENFGA_HTTP_UPSTREAMTIMEOUT=60s \
  -n openfga-prod
```

---

## 性能測試

### 使用 ghz 進行壓力測試

```bash
# 安装 ghz
go install github.com/bojand/ghz@latest

# 運行測試
ghz --insecure \
  --proto ./proto/openfga/v1/openfga.proto \
  --call openfga.v1.OpenFGA/Check \
  -d '{
    "store_id": "store-1",
    "tuple_key": {
      "user": "user:alice",
      "relation": "member",
      "object": "org:acme"
    }
  }' \
  -c 100 \
  -n 10000 \
  -rate 1000 \
  openfga-grpc.openfga-prod.svc.cluster.local:8081

# 預期結果 (假設 10K RPS)：
# Total: 10.0s
# Slowest: 250ms
# Fastest: 5ms
# Average: 50ms
# Requests/sec: 1000
```

### 監控測試期間的指標

```bash
# 終端 1：監控 Pod 資源
watch -n 1 'kubectl top pods -n openfga-prod -l app=openfga'

# 終端 2：監控資料庫連接
watch -n 1 'kubectl exec -it mariadb-galera-0 -n openfga-prod -- mysql -e \
  "SHOW STATUS LIKE \"Threads%\";"'

# 終端 3：監控 OpenFGA 日誌
kubectl logs -f deployment/openfga -n openfga-prod --all-containers=true | \
  grep -i "error\|warning\|timeout"
```

---

## 縱向擴展 (Vertical Scaling)

### 增加 Pod 副本

```bash
# 縮放到 12 個副本
kubectl scale deployment openfga --replicas=12 -n openfga-prod

# 監控滾動更新進度
kubectl rollout status deployment/openfga -n openfga-prod
```

### 增加資源限制

```bash
# 編輯 Deployment
kubectl edit deployment openfga -n openfga-prod

# 修改 resources 部分：
# resources:
#   requests:
#     cpu: "1000m"        # 增加
#     memory: "1Gi"       # 增加
#   limits:
#     cpu: "4000m"        # 增加
#     memory: "4Gi"       # 增加
```

---

## 清理資源

```bash
# 刪除整個 openfga-prod namespace
kubectl delete namespace openfga-prod

# 或保留 namespace 但刪除部署
kubectl delete -f k8s-openfga-mariadb-galera-deployment.yaml -n openfga-prod
```

---

## 常見問題 (FAQ)

### Q: 如何修改 MariaDB 密碼？

```bash
# 編輯 Secret
kubectl edit secret mariadb-secret -n openfga-prod

# 編輯 data.root-password (base64 編碼)
# 編輯後，刪除 Galera Pod 強制重新啟動
kubectl delete pods -l app=mariadb-galera -n openfga-prod
```

### Q: 如何添加更多 OpenFGA 客戶端？

```bash
# 編輯 ConfigMap 中的 Galera 配置
kubectl edit configmap mariadb-galera-config -n openfga-prod

# 增加 max_connections
max_connections = 3000
```

### Q: 如何備份資料？

```bash
# 執行 mysqldump
kubectl exec -it mariadb-galera-0 -n openfga-prod -- \
  mysqldump -u root -p$MYSQL_ROOT_PASSWORD --all-databases > backup.sql

# 或使用 Galera 快照
kubectl exec -it mariadb-galera-0 -n openfga-prod -- \
  mariabackup --backup --target-dir=/tmp/backup
```

### Q: 如何進行藍綠部署（升級 OpenFGA）？

```bash
# 1. 更新 Deployment 鏡像
kubectl set image deployment/openfga \
  openfga=openfga/openfga:1.5.0 \
  -n openfga-prod

# 2. 監控滾動更新
kubectl rollout status deployment/openfga -n openfga-prod

# 3. 如果需要回滾
kubectl rollout undo deployment/openfga -n openfga-prod
```

---

## 下一步

1. 閱讀詳細的優化指南：`MYSQL_GALERA_CONNECTION_POOL_OPTIMIZATION.md`
2. 運行配置計算器：`python connection_pool_calculator.py`
3. 設置監控：參考 `MONITORING_AND_TROUBLESHOOTING.md`
4. 進行性能測試驗證配置
5. 根據實際 RPS 調整參數

---

## 支持資源

- OpenFGA 文檔：https://openfga.dev/docs
- MariaDB Galera：https://mariadb.com/kb/en/mariadb-galera-cluster/
- Kubernetes：https://kubernetes.io/docs/
- 本倉庫研究筆記：`study-notes/` 目錄
