# 📊 Grafana Dashboard 使用指南

將 `k8s_prometheus_monitor.py` 的監控內容轉換為 Grafana Dashboard

---

## 🎯 Dashboard 總覽

這個 Grafana Dashboard 完整呈現了 `k8s_prometheus_monitor.py` 中的所有監控指標，提供可視化的實時監控界面。

### 📋 監控面板對應

| 面板 ID | Python 工具對應               | Dashboard 面板             | 說明                                   |
| ------- | ----------------------------- | -------------------------- | -------------------------------------- |
| **[1]** | `get_pod_status()`            | Pod 狀態總覽 + 按應用分類  | Pod 運行狀態，OpenFGA/MariaDB 分類統計 |
| **[2]** | `get_cpu_usage()`             | CPU 使用率                 | CPU 百分比，5 分鐘平均                 |
| **[3]** | `get_memory_usage()`          | 內存使用 (GiB)             | 工作集內存，GiB 單位                   |
| **[4]** | `get_network_io()`            | 網絡進/出流量              | 網絡 I/O，KB/s 單位                    |
| **[5]** | `get_mysql_metrics()`         | MySQL 連接 + 查詢 + InnoDB | 活動連接、總查詢、InnoDB 操作          |
| **[6]** | `get_galera_cluster_status()` | Galera 集群狀態            | 集群大小、就緒狀態、歷史趨勢           |
| **[7]** | -                             | Pod 狀態詳細列表           | 表格視圖，所有 Pod 詳情                |

---

## 🚀 快速開始

### 方法 1: Grafana UI 導入（推薦）

#### 步驟 1：登入 Grafana

```bash
# 如果使用本地 Grafana
open http://localhost:3000

# 默認帳號密碼
Username: admin
Password: admin
```

#### 步驟 2：導入 Dashboard

1. 點擊左側菜單 **"+"** → **"Import"**
2. 選擇 **"Upload JSON file"**
3. 選擇文件：`deployments/grafana-dashboard-openfga-galera.json`
4. 點擊 **"Load"**
5. 選擇 Prometheus 數據源
6. 輸入或確認 Namespace（默認 `openfga-prod`）
7. 點擊 **"Import"**

完成！Dashboard 已可用 🎉

---

### 方法 2: 使用 Grafana API（自動化）

```bash
# 設置變量
GRAFANA_URL="http://localhost:3000"
GRAFANA_API_KEY="your-api-key-here"
DASHBOARD_FILE="deployments/grafana-dashboard-openfga-galera.json"

# 導入 Dashboard
curl -X POST \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @"$DASHBOARD_FILE" \
  "$GRAFANA_URL/api/dashboards/db"
```

---

### 方法 3: 使用 Kubernetes ConfigMap（生產環境）

#### 步驟 1：創建 ConfigMap

```bash
kubectl create configmap grafana-dashboard-openfga \
  --from-file=openfga-galera.json=deployments/grafana-dashboard-openfga-galera.json \
  -n monitoring
```

#### 步驟 2：配置 Grafana 自動加載

在 Grafana Deployment 中添加 volume：

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  namespace: monitoring
spec:
  template:
    spec:
      containers:
        - name: grafana
          image: grafana/grafana:latest
          volumeMounts:
            - name: dashboard-openfga
              mountPath: /etc/grafana/provisioning/dashboards/openfga-galera.json
              subPath: openfga-galera.json
      volumes:
        - name: dashboard-openfga
          configMap:
            name: grafana-dashboard-openfga
```

#### 步驟 3：配置自動發現

創建 `dashboard-provider.yaml`：

```yaml
apiVersion: 1

providers:
  - name: "OpenFGA Dashboards"
    orgId: 1
    folder: "OpenFGA"
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

掛載到 `/etc/grafana/provisioning/dashboards/provider.yaml`

---

## 📊 Dashboard 功能說明

### 🔹 面板 1: Pod 狀態總覽

**對應 Python 代碼**:

```python
pod_status = monitor.get_pod_status()
print(f"總計: {pod_status['total']} Pod")
print(f"就緒: {pod_status['ready']} Running")
```

**Grafana 查詢**:

```promql
# 運行中的 Pod
count(kube_pod_status_phase{namespace="openfga-prod", phase="Running"})

# 總 Pod 數
count(kube_pod_status_phase{namespace="openfga-prod"})

# OpenFGA Running
count(kube_pod_status_phase{namespace="openfga-prod", pod=~".*openfga.*", phase="Running"})

# MariaDB Running
count(kube_pod_status_phase{namespace="openfga-prod", pod=~".*mariadb.*", phase="Running"})
```

**視圖類型**:

- Stat（統計數字）
- Time Series（時間序列圖表）

---

### 🔹 面板 2: CPU 使用率

**對應 Python 代碼**:

```python
cpu_data = monitor.get_cpu_usage()
print(f"平均 CPU: {cpu_data['total_avg']:.2f}%")
```

**Grafana 查詢**:

```promql
# OpenFGA 平均 CPU
avg(rate(container_cpu_usage_seconds_total{namespace="openfga-prod", pod=~".*openfga.*"}[5m])) * 100

# MariaDB 平均 CPU
avg(rate(container_cpu_usage_seconds_total{namespace="openfga-prod", pod=~".*mariadb.*"}[5m])) * 100

# 所有 Pod 詳細 CPU
rate(container_cpu_usage_seconds_total{namespace="openfga-prod"}[5m]) * 100
```

**閾值設置**:

- 🟢 綠色: < 60%
- 🟡 黃色: 60% - 80%
- 🔴 紅色: > 80%

---

### 🔹 面板 3: 內存使用

**對應 Python 代碼**:

```python
mem_data = monitor.get_memory_usage()
print(f"總計: {mem_data['total_gib']:.2f} GiB")
```

**Grafana 查詢**:

```promql
# OpenFGA 總內存
sum(container_memory_working_set_bytes{namespace="openfga-prod", pod=~".*openfga.*"}) / 1024 / 1024 / 1024

# MariaDB 總內存
sum(container_memory_working_set_bytes{namespace="openfga-prod", pod=~".*mariadb.*"}) / 1024 / 1024 / 1024

# 所有 Pod 詳細內存
container_memory_working_set_bytes{namespace="openfga-prod"} / 1024 / 1024 / 1024
```

**單位**: GiB（Gibibytes）

---

### 🔹 面板 4: 網絡 I/O

**對應 Python 代碼**:

```python
network_data = monitor.get_network_io()
print(f"進流量: {total_recv/1024:.2f} KB/s")
print(f"出流量: {total_trans/1024:.2f} KB/s")
```

**Grafana 查詢**:

```promql
# 進流量
rate(container_network_receive_bytes_total{namespace="openfga-prod"}[5m]) / 1024

# 出流量
rate(container_network_transmit_bytes_total{namespace="openfga-prod"}[5m]) / 1024
```

**單位**: KB/s（Kilobytes per second）

---

### 🔹 面板 5: MySQL 指標

**對應 Python 代碼**:

```python
mysql_data = monitor.get_mysql_metrics()
print(f"活動連接: {total_conn:.0f}")
print(f"總查詢: {total_q:.0f}")
```

**Grafana 查詢**:

```promql
# 活動連接
sum(mysql_global_status_threads_connected{namespace="openfga-prod"})

# 總查詢
sum(mysql_global_status_questions{namespace="openfga-prod"})

# InnoDB 讀取速率
rate(mysql_global_status_innodb_rows_read{namespace="openfga-prod"}[5m])

# InnoDB 寫入速率
rate(mysql_global_status_innodb_rows_written{namespace="openfga-prod"}[5m])

# InnoDB 刪除速率
rate(mysql_global_status_innodb_rows_deleted{namespace="openfga-prod"}[5m])
```

**閾值設置** (連接數):

- 🟢 綠色: < 100
- 🟡 黃色: 100 - 200
- 🔴 紅色: > 200

---

### 🔹 面板 6: Galera 集群狀態

**對應 Python 代碼**:

```python
galera_status = monitor.get_galera_cluster_status()
print(f"集群大小: {size:.0f}")
print(f"就緒狀態: {'✅' if is_ready == 1 else '❌'}")
```

**Grafana 查詢**:

```promql
# 集群大小
max(mysql_global_status_wsrep_cluster_size{namespace="openfga-prod"})

# 就緒狀態
min(mysql_global_status_wsrep_ready{namespace="openfga-prod"})

# 歷史狀態
mysql_global_status_wsrep_cluster_size{namespace="openfga-prod"}
mysql_global_status_wsrep_ready{namespace="openfga-prod"}
```

**狀態映射**:

- `wsrep_ready = 1` → 🟢 就緒
- `wsrep_ready = 0` → 🔴 未就緒

**集群大小閾值**:

- 🔴 紅色: < 2（集群故障）
- 🟡 黃色: 2（降級運行）
- 🟢 綠色: ≥ 3（健康）

---

### 🔹 面板 7: Pod 狀態詳細列表

**視圖類型**: Table（表格）

**顯示列**:

- Pod 名稱
- 狀態（Running/Pending/Failed）

**背景顏色**:

- 🟢 Running
- 🟡 Pending
- 🔴 Failed

---

## ⚙️ Dashboard 配置

### 🔄 自動刷新

Dashboard 設置為 **15 秒自動刷新**，與 Python 工具的默認刷新間隔一致。

可選刷新間隔：

- 5 秒（高頻監控）
- 10 秒
- 15 秒（推薦，默認）
- 30 秒
- 1 分鐘
- 5 分鐘

在 Dashboard 右上角點擊刷新圖標修改。

---

### 📅 時間範圍

默認時間範圍：**最近 1 小時**

可調整為：

- 最近 5 分鐘
- 最近 15 分鐘
- 最近 30 分鐘
- 最近 1 小時（默認）
- 最近 3 小時
- 最近 6 小時
- 最近 12 小時
- 最近 24 小時

---

### 🎛️ 變量配置

Dashboard 支持兩個變量：

#### 1. **數據源** (`DS_PROMETHEUS`)

- 類型: Datasource
- 查詢: `prometheus`
- 自動發現所有 Prometheus 數據源

#### 2. **Namespace** (`namespace`)

- 類型: Textbox
- 默認值: `openfga-prod`
- 可修改為任何 Kubernetes namespace

**修改 Namespace**:

1. 點擊 Dashboard 頂部的 **"Namespace"** 下拉選單
2. 輸入新的 namespace 名稱
3. 按 Enter 或點擊外部應用

---

## 🔧 高級配置

### 添加告警規則

在任何面板中添加告警：

1. 點擊面板標題 → **Edit**
2. 切換到 **Alert** 標籤
3. 點擊 **Create Alert**
4. 配置告警條件

**示例告警**（CPU > 80%）:

```yaml
Condition: WHEN avg() OF query(A, 5m, now) IS ABOVE 80

Notifications:
  Send to: email / Slack / PagerDuty
```

---

### 自定義面板

#### 添加新的查詢

1. 點擊面板標題 → **Edit**
2. 在 **Queries** 部分點擊 **"+ Query"**
3. 輸入 PromQL 表達式
4. 配置 Legend（圖例）格式

**範例**：添加慢查詢監控

```promql
rate(mysql_global_status_slow_queries{namespace="$namespace"}[5m])
```

---

### 修改閾值

1. 點擊面板標題 → **Edit**
2. 切換到 **Thresholds** 部分
3. 修改數值和顏色

**示例**（調整 CPU 閾值）:

```
綠色: 0 - 50%
黃色: 50% - 75%
紅色: > 75%
```

---

## 📖 與 Python 工具的對比

### 優勢對比

| 特性         | Python 工具          | Grafana Dashboard   |
| ------------ | -------------------- | ------------------- |
| **實時性**   | ✅ 即時（15 秒刷新） | ✅ 即時（可調）     |
| **歷史數據** | ❌ 無（僅當前值）    | ✅ 有（最多 30 天） |
| **可視化**   | ⚠️ 文本輸出          | ✅ 豐富圖表         |
| **告警**     | ❌ 無內建告警        | ✅ 完整告警系統     |
| **權限控制** | ❌ 無                | ✅ RBAC 支持        |
| **多用戶**   | ❌ 單用戶            | ✅ 多用戶共享       |
| **部署**     | ✅ 無需安裝          | ⚠️ 需要 Grafana     |
| **便攜性**   | ✅ 任何地方運行      | ⚠️ 需要訪問 Grafana |

---

### 使用場景建議

#### 🟢 使用 Python 工具

- 快速檢查當前狀態
- 無法訪問 Grafana UI
- 腳本自動化
- CI/CD 集成
- 臨時監控任務

```bash
cd tools/core-tools
python k8s_prometheus_monitor.py
# 選擇 1: 瞬時快照
```

---

#### 🟢 使用 Grafana Dashboard

- 長期監控
- 多人協作
- 需要歷史數據分析
- 需要告警通知
- 管理多個集群
- 生產環境監控

---

## 🎨 定制化建議

### 1. 為不同環境創建多個 Dashboard

```bash
# 開發環境
Namespace: openfga-dev
刷新間隔: 30s

# 測試環境
Namespace: openfga-test
刷新間隔: 15s

# 生產環境
Namespace: openfga-prod
刷新間隔: 5s
告警: 啟用
```

---

### 2. 添加業務指標

除了基礎設施指標，還可以添加：

```promql
# OpenFGA 請求延遲（如果有）
histogram_quantile(0.95, rate(openfga_http_request_duration_seconds_bucket[5m]))

# OpenFGA 錯誤率
rate(openfga_http_requests_total{status=~"5.."}[5m])

# OpenFGA 總請求數
rate(openfga_http_requests_total[5m])
```

---

### 3. 集成到現有 Dashboard

如果你已有 Grafana Dashboard，可以：

1. 複製單個面板：

   - 在源 Dashboard 中點擊面板標題 → **More** → **Copy**
   - 在目標 Dashboard 中 **Paste**

2. 導出並合併 JSON：
   - 手動編輯 JSON，將 `panels` 數組合併

---

## 🔍 故障排查

### 問題 1: 無數據顯示

**可能原因**:

- Prometheus 數據源未配置
- Namespace 錯誤
- Prometheus 無法採集指標

**解決方法**:

```bash
# 1. 檢查 Prometheus 數據源
Grafana UI → Configuration → Data Sources → Prometheus

# 2. 驗證 Prometheus 指標
curl http://prometheus:9090/api/v1/query?query=up

# 3. 檢查 Namespace
kubectl get pods -n openfga-prod
```

---

### 問題 2: 圖表顯示 "No Data"

**可能原因**:

- 時間範圍內無數據
- PromQL 查詢錯誤
- Pod 標籤不匹配

**解決方法**:

```bash
# 1. 調整時間範圍
時間選擇器 → 最近 5 分鐘

# 2. 直接在 Prometheus 測試查詢
http://prometheus:9090/graph
輸入查詢：kube_pod_status_phase{namespace="openfga-prod"}

# 3. 檢查 Pod 標籤
kubectl get pods -n openfga-prod --show-labels
```

---

### 問題 3: 刷新緩慢

**可能原因**:

- 查詢範圍過大
- Prometheus 性能不足

**解決方法**:

```yaml
# 1. 優化查詢範圍
從 [1h] 減少到 [5m]

# 2. 調整刷新間隔
從 5s 增加到 15s 或 30s

# 3. 增加 Prometheus 資源
kubectl edit deployment prometheus -n monitoring
# 增加 CPU/Memory limits
```

---

## 📚 相關資源

### 文檔

- Python 監控工具: [core-tools/k8s_prometheus_monitor.py](../core-tools/k8s_prometheus_monitor.py)
- Prometheus 部署: [prometheus-deployment.yaml](prometheus-deployment.yaml)
- 監控指南: [../docs/PROMETHEUS_MONITORING_GUIDE.md](../docs/PROMETHEUS_MONITORING_GUIDE.md)

### 外部鏈接

- [Grafana 官方文檔](https://grafana.com/docs/)
- [PromQL 查詢語法](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboard 最佳實踐](https://grafana.com/docs/grafana/latest/best-practices/)

---

## 🎯 總結

### 核心對應關係

| Python 函數                   | Dashboard 面板 | PromQL 查詢                                   |
| ----------------------------- | -------------- | --------------------------------------------- |
| `get_pod_status()`            | 面板 1         | `kube_pod_status_phase`                       |
| `get_cpu_usage()`             | 面板 2         | `rate(container_cpu_usage_seconds_total[5m])` |
| `get_memory_usage()`          | 面板 3         | `container_memory_working_set_bytes`          |
| `get_network_io()`            | 面板 4         | `rate(container_network_*_bytes_total[5m])`   |
| `get_mysql_metrics()`         | 面板 5         | `mysql_global_status_*`                       |
| `get_galera_cluster_status()` | 面板 6         | `mysql_global_status_wsrep_*`                 |

---

### 快速命令參考

```bash
# 1. 導入 Dashboard
# Grafana UI → Import → Upload JSON → 選擇 grafana-dashboard-openfga-galera.json

# 2. 訪問 Dashboard
http://grafana:3000/d/openfga-galera-monitor

# 3. 修改 Namespace
Dashboard 頂部 → Namespace 下拉選單 → 輸入新值

# 4. 調整刷新間隔
Dashboard 右上角 → 刷新圖標 → 選擇間隔

# 5. 導出 Dashboard
Dashboard 設置 → JSON Model → 複製
```

---

**✅ 現在你擁有完整的可視化監控系統！**

結合 Python 工具的靈活性和 Grafana Dashboard 的可視化能力，實現全方位監控 🎉

---

**更新日期**: 2026-01-01  
**版本**: 1.0  
**狀態**: 生產就緒 ✨
