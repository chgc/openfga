# 📋 監控方案快速參考卡

## 核心回答

❓ **問題**: 即時監控有辦法使用 Prometheus metrics 代替 kubectl 嗎？

✅ **答案**: 完全可以！而且更強大。

---

## 三種監控工具速查表

### 工具 #1: 離線檢查工具 🟢
```bash
python k8s_deployment_checker_offline.py
```
| 項目 | 值 |
|------|-----|
| **何時用** | 部署前 |
| **需要權限** | ❌ 無 |
| **YAML 分析** | ✅ 有 |
| **實時監控** | ❌ 無 |
| **告警** | ❌ 無 |

**最適合**: 開發環境、CI/CD 自動化

---

### 工具 #2: kubectl 檢查工具 🟡
```bash
python k8s_deployment_checker.py
```
| 項目 | 值 |
|------|-----|
| **何時用** | 部署直後 |
| **需要權限** | ✅ kubectl |
| **實時查詢** | ✅ 有 |
| **歷史數據** | ❌ 無 |
| **告警** | ❌ 無 |

**最適合**: 快速檢查、問題排查

---

### 工具 #3: Prometheus 監控工具 🔴⭐
```bash
python k8s_prometheus_monitor.py
```
| 項目 | 值 |
|------|-----|
| **何時用** | 長期監控 |
| **需要權限** | ❌ 只需 HTTP |
| **實時監控** | ✅ 實時 |
| **歷史數據** | ✅ 30 天 |
| **告警規則** | ✅ 支持 |
| **Grafana** | ✅ 支持 |

**最適合**: 生產監控、無 kubectl 權限 ⭐

---

## 🚀 一分鐘快速開始

### 1️⃣ 部署 Prometheus（需要 kubectl）

```bash
cd tools
bash deploy-monitoring.sh deploy-all
```

### 2️⃣ 驗證部署

```bash
bash deploy-monitoring.sh verify
```

### 3️⃣ 啟動監控（無需 kubectl）

```bash
python k8s_prometheus_monitor.py
# 選擇 2: 持續監控
```

### 4️⃣ 訪問 Prometheus UI

```bash
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# 訪問 http://localhost:9090
```

---

## 📊 Prometheus 監控指標

### 系統資源
```promql
CPU:    rate(container_cpu_usage_seconds_total[5m]) * 100
Memory: container_memory_working_set_bytes / 1024 / 1024
Network: rate(container_network_receive_bytes_total[5m])
```

### Pod 狀態
```promql
Pod 就緒: count(kube_pod_status_phase{phase="Running"})
Pod 失敗: count(kube_pod_status_phase{phase="Failed"})
```

### MySQL/Galera
```promql
連接數: mysql_global_status_threads_connected
集群: mysql_global_status_wsrep_cluster_size
查詢: rate(mysql_global_status_questions[1m])
```

---

## 🎯 決策流程圖

```
需要監控？
│
├─ 部署前
│  └─ 使用【離線工具】✅
│     python k8s_deployment_checker_offline.py
│
├─ 部署直後
│  └─ 使用【kubectl 工具】✅
│     python k8s_deployment_checker.py
│
└─ 長期監控 + 沒有 kubectl
   └─ 使用【Prometheus 工具】✅✅✅
      python k8s_prometheus_monitor.py
      (持續監控模式)
```

---

## 📁 文件速查

| 文件 | 用途 |
|------|------|
| `k8s_prometheus_monitor.py` | ⭐ Prometheus 實時監控 |
| `k8s_deployment_checker_offline.py` | YAML 配置驗證 |
| `k8s_deployment_checker.py` | kubectl 狀態檢查 |
| `prometheus-deployment.yaml` | Prometheus 部署 |
| `mysql-exporter-deployment.yaml` | MySQL 指標導出 |
| `deploy-monitoring.sh` | 快速部署腳本 |
| `PROMETHEUS_SOLUTION_SUMMARY.md` | 詳細方案說明 |
| `COMPLETE_MONITORING_GUIDE.md` | 完整工具對比 |

---

## ⚡ 常用命令

### 部署
```bash
bash deploy-monitoring.sh check              # 檢查環境
bash deploy-monitoring.sh deploy-all         # 一鍵部署
bash deploy-monitoring.sh verify             # 驗證部署
```

### 監控
```bash
python k8s_prometheus_monitor.py             # 互動式
python k8s_prometheus_monitor.py < script.py # 自動化
```

### 訪問
```bash
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# http://localhost:9090
```

---

## ✨ Prometheus 的 3 大優勢

### 1️⃣ 無需 kubectl
```
❌ kubectl 方案: 需要集群訪問 + kubeconfig
✅ Prometheus: 只需 HTTP 訪問
```

### 2️⃣ 實時 + 歷史
```
❌ kubectl: 只能看當前
✅ Prometheus: 實時 + 30 天歷史 + 趨勢分析
```

### 3️⃣ 自動告警
```
❌ kubectl: 手動檢查
✅ Prometheus: 自動告警 + Alertmanager 通知
```

---

## 🔄 推薦工作流程

```
第 1 步: 編寫 YAML
   ↓
第 2 步: 使用【離線工具】驗證
   ↓
第 3 步: 部署應用和 Prometheus
   ↓
第 4 步: 使用【Prometheus 工具】監控
   ↓
第 5 步: 基於指標調整配置
```

---

## 🎓 學習路徑

| 級別 | 時間 | 學習內容 |
|------|------|---------|
| 初級 | 1 天 | 理解三種工具的區別 |
| 中級 | 1 周 | 部署和運行 Prometheus |
| 高級 | 2 周 | 配置告警 + Grafana |

---

## 💡 核心概念

### 為什麼選 Prometheus？

| 方面 | kubectl | Prometheus |
|------|---------|-----------|
| **安全** | 需要集群訪問 | HTTP 訪問即可 |
| **靈活** | 單點查詢 | 連續監控 + API |
| **可靠** | 依賴 API Server | 獨立存儲 |
| **可視** | CLI | Grafana 美觀 |
| **告警** | 無 | 完整告警系統 |

### Prometheus 三層架構

```
應用層
├─ OpenFGA (metrics :8081)
├─ MariaDB (MySQL Exporter :9104)
└─ Kubernetes (kube-state-metrics)
         ↓
收集層
├─ Prometheus Scraper
├─ Service Discovery
└─ Config Management
         ↓
分析層
├─ PromQL 查詢
├─ Alertmanager
└─ Grafana 展示
```

---

## 🔒 安全性

### Prometheus vs kubectl

```
Prometheus 優勢:
✅ 無需集群管理員權限
✅ HTTP 可限制 IP/密碼
✅ 讀取專用 exporter 數據
✅ 數據隔離存儲

kubectl 風險:
❌ 需要完整集群訪問
❌ 難以精細化權限控制
❌ 直接訪問 API Server
```

---

## 🎯 成功標誌

部署完成後，確認：

- [ ] ✅ Prometheus pod 運行中
- [ ] ✅ MySQL Exporter 連接成功
- [ ] ✅ 可以查詢 metrics
- [ ] ✅ Prometheus UI 顯示 targets UP
- [ ] ✅ 監控工具能連接
- [ ] ✅ 看到實時數據流

---

## 📞 快速查詢

### 問: 需要 kubectl 權限嗎？
**答**: 部署時需要，監控時完全不需要

### 問: 能監控多久的數據？
**答**: 實時 + 最多 30 天（可配置）

### 問: 支持告警嗎？
**答**: 支持，通過 PromQL 規則和 Alertmanager

### 問: 能和 Grafana 配合嗎？
**答**: 可以，Prometheus 是 Grafana 的主要數據源

### 問: 性能開銷大嗎？
**答**: 很小，一般 < 100m CPU + 1Gi Memory

---

## 🎉 最後的話

**有了 Prometheus，你可以:**

1. ✅ **不用 kubectl** 進行監控
2. ✅ **看到歷史數據** 進行分析
3. ✅ **自動告警** 及時響應
4. ✅ **可視化儀表板** 一目了然
5. ✅ **容量規劃** 基於趨勢

**立即開始**:
```bash
bash deploy-monitoring.sh deploy-all
python k8s_prometheus_monitor.py
```

---

**Prometheus 實時監控 = 無需 kubectl 的完整監控方案** 🚀
