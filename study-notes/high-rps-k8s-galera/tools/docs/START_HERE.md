# ✅ Prometheus 監控完整解決方案

## 🎯 核心答案

**問題**: 即時監控有辦法使用 Prometheus metrics 代替 kubectl 嗎？

**✅ 完全可以，而且更強大！**

---

## 📦 完整方案內容

### 新增核心工具 (4 個)

| # | 工具 | 類型 | 作用 |
|---|------|------|------|
| 1️⃣ | `k8s_prometheus_monitor.py` | 💻 Python | **Prometheus 實時監控工具** ⭐ |
| 2️⃣ | `prometheus-deployment.yaml` | 📄 K8s | Prometheus 完整部署配置 |
| 3️⃣ | `mysql-exporter-deployment.yaml` | 📄 K8s | MySQL/Galera metrics 導出 |
| 4️⃣ | `deploy-monitoring.sh` | 🔧 Shell | 自動化部署和驗證腳本 |

### 新增詳細指南 (6 份)

| 文檔 | 長度 | 內容 |
|------|------|------|
| `QUICK_REFERENCE.md` | 1 頁 | ⚡ 快速查詢卡 |
| `PROMETHEUS_SOLUTION_SUMMARY.md` | 3 頁 | 📋 完整方案說明 |
| `PROMETHEUS_MONITORING_GUIDE.md` | 8 頁 | 📖 詳細技術文檔 |
| `COMPLETE_MONITORING_GUIDE.md` | 6 頁 | 🔄 工具對比和決策 |
| `README_MONITORING.md` | 5 頁 | 📚 工具總體說明 |
| `FILE_MANIFEST.md` | 5 頁 | 📑 文件清單 |

---

## 🚀 三層監控方案

### 層級 1️⃣: 離線配置檢查 (任何地方，無需權限)

```bash
python k8s_deployment_checker_offline.py
```

**用途**: 部署前驗證配置  
**特點**: ✅ YAML 分析、❌ 無需訪問權限

---

### 層級 2️⃣: kubectl 狀態檢查 (部署直後)

```bash
python k8s_deployment_checker.py
```

**用途**: 部署狀態快速驗證  
**特點**: ✅ 實時查詢、⚠️ 需要 kubectl 權限

---

### 層級 3️⃣: Prometheus 實時監控 (長期監控) ⭐

```bash
python k8s_prometheus_monitor.py
```

**用途**: 無 kubectl 的實時監控和歷史分析  
**特點**: 
- ✅ **無需 kubectl**（只需 Prometheus HTTP）
- ✅ **實時監控**（15 秒刷新）
- ✅ **30 天歷史數據**
- ✅ **完整告警系統**
- ✅ **Grafana 支持**

---

## 📊 Prometheus 實時監控工具

### 功能特性

```python
# 選項 1: 一次性儀表板
# 展示當前時刻的所有指標

# 選項 2: 持續監控（推薦）
# 每 5 秒自動更新，實時觀測

# 選項 3: 自定義刷新間隔
# 指定任意時間間隔

# 選項 4: 摘要報告
# 簡潔的健康狀態報告
```

### 監控指標

```
✅ Pod 狀態和就緒數
✅ CPU 使用率（%）
✅ Memory 使用量（GiB）
✅ Network I/O（KB/s）
✅ MySQL 連接數和查詢速率
✅ Galera 集群狀態和大小
```

### 輸出示例

```
[監控週期 #1] 2026-01-01 12:00:00

[1] Pod 狀態
✅ 總計: 12 Pod，就緒: 12 Running
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
✅ 集群大小: 3，✅ 就緒: 是
```

---

## ⚡ 快速開始 (3 分鐘)

### 方式 A: 一鍵部署 (推薦)

```bash
cd tools
bash deploy-monitoring.sh deploy-all
bash deploy-monitoring.sh verify
python k8s_prometheus_monitor.py
```

### 方式 B: 手動部署

```bash
# 1. 部署 Prometheus
kubectl apply -f prometheus-deployment.yaml

# 2. 部署 MySQL Exporter
kubectl apply -f mysql-exporter-deployment.yaml

# 3. 驗證
kubectl get pods -n monitoring

# 4. 運行監控工具
python k8s_prometheus_monitor.py
```

### 方式 C: 僅運行監控（Prometheus 已存在）

```bash
# 確保 Prometheus 可訪問
python k8s_prometheus_monitor.py
# 輸入 Prometheus URL (如: http://localhost:9090)
```

---

## 🎯 核心優勢

### vs kubectl 方案

| 對比項 | kubectl | Prometheus |
|--------|---------|-----------|
| 🔑 需要權限 | ✅ kubectl | ❌ 只需 HTTP |
| ⏱️ 實時性 | ✅ 實時 | ✅ 實時 |
| 📈 歷史數據 | ❌ | ✅ 30 天 |
| 🚨 告警 | ❌ | ✅ 完整 |
| 🌐 Network I/O | ❌ | ✅ 支持 |
| 📊 Grafana | ❌ | ✅ 支持 |
| 🔄 跨集群 | ❌ | ✅ 支持 |

### 三大核心優勢

1. **🔐 無需 kubectl 權限**
   - 更安全（HTTP 訪問可限制）
   - 更靈活（任何地方可訪問）
   - 更易用（無需複雜權限配置）

2. **📊 實時 + 歷史 + 告警**
   - 實時監控：15 秒刷新
   - 歷史分析：30 天數據
   - 自動告警：基於規則

3. **💡 開放標準 + 完整生態**
   - PromQL 標準查詢語言
   - Grafana 可視化
   - Alertmanager 通知
   - 社區豐富的 Exporters

---

## 📚 文檔導航

### 第一次使用？按這個順序

1. ⚡ [快速參考卡](QUICK_REFERENCE.md) (2 分鐘)
2. 📋 [方案總結](PROMETHEUS_SOLUTION_SUMMARY.md) (10 分鐘)
3. 🚀 [快速開始](README_MONITORING.md) (5 分鐘)
4. 🔍 [部署](deploy-monitoring.sh) (10 分鐘)
5. 📖 [深入指南](PROMETHEUS_MONITORING_GUIDE.md) (30 分鐘)

### 需要特定信息？

- 🔄 工具對比 → [完整對比指南](COMPLETE_MONITORING_GUIDE.md)
- 🎯 使用決策 → [決策樹](COMPLETE_MONITORING_GUIDE.md#使用決策樹)
- 📡 PromQL 查詢 → [查詢示例](PROMETHEUS_MONITORING_GUIDE.md#promql-查詢示例)
- 🚨 告警規則 → [告警配置](PROMETHEUS_MONITORING_GUIDE.md#設置告警規則)
- 📋 文件清單 → [完整清單](FILE_MANIFEST.md)

---

## 💾 部署清單

- [ ] 檢查 kubectl 訪問: `kubectl cluster-info`
- [ ] 檢查 Python: `python3 --version`
- [ ] 安裝依賴: `pip install requests`
- [ ] 部署監控: `bash deploy-monitoring.sh deploy-all`
- [ ] 驗證部署: `bash deploy-monitoring.sh verify`
- [ ] 啟動監控: `python k8s_prometheus_monitor.py`
- [ ] 訪問 Prometheus UI: `kubectl port-forward ...`

---

## 🔧 常用命令速查

### 部署相關

```bash
# 完整檢查和部署
bash deploy-monitoring.sh check              # 環境檢查
bash deploy-monitoring.sh deploy-all         # 一鍵全部部署
bash deploy-monitoring.sh verify             # 驗證部署
bash deploy-monitoring.sh monitor            # 啟動監控
bash deploy-monitoring.sh uninstall          # 卸載監控
```

### 監控相關

```bash
# Python 監控工具
python k8s_prometheus_monitor.py             # 交互式菜單
python -c "from k8s_prometheus_monitor import PrometheusMonitor; ..."  # 命令行

# Prometheus UI
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# 訪問 http://localhost:9090
```

### 查詢相關

```promql
# CPU 使用
rate(container_cpu_usage_seconds_total{namespace="openfga-prod"}[5m]) * 100

# Memory 使用
container_memory_working_set_bytes{namespace="openfga-prod"} / 1024 / 1024

# Pod 狀態
kube_pod_status_phase{namespace="openfga-prod"}

# MySQL 連接
mysql_global_status_threads_connected
```

---

## 🎓 推薦工作流程

### 開發環境

```
1. 編寫 YAML 配置
   ↓
2. python k8s_deployment_checker_offline.py  (驗證配置)
   ↓
3. kubectl apply -f deployment.yaml          (部署應用)
   ↓
4. python k8s_deployment_checker.py          (檢查部署)
   ↓
5. 測試應用程序
```

### 生產環境 ⭐

```
1. python k8s_deployment_checker_offline.py  (驗證配置)
   ↓
2. bash deploy-monitoring.sh deploy-all      (部署監控)
   ↓
3. kubectl apply -f production-deployment.yaml (部署應用)
   ↓
4. python k8s_prometheus_monitor.py          (持續監控，選項 2)
   ↓
5. http://prometheus:9090                    (Prometheus UI)
   ↓
6. 基於指標調整配置和告警
```

---

## 🎉 成功標誌

部署完成後，確認以下項目：

- [ ] ✅ Prometheus pod 運行: `kubectl get pods -n monitoring`
- [ ] ✅ MySQL Exporter 連接: `kubectl logs -n openfga-prod deployment/mysql-exporter`
- [ ] ✅ Prometheus UI 可訪問: http://localhost:9090
- [ ] ✅ Prometheus targets UP: 訪問 http://localhost:9090/targets
- [ ] ✅ 監控工具能連接: `python k8s_prometheus_monitor.py` 選項 1
- [ ] ✅ 看到實時指標數據

---

## 📞 常見問題

**Q: 部署需要多長時間？**  
A: 3-10 分鐘（根據集群狀態）

**Q: 如果 Prometheus 故障會怎樣？**  
A: 應用不受影響，只是無法監控

**Q: 如何備份監控數據？**  
A: Prometheus 數據存儲在 PVC，支持 K8s 備份工具

**Q: 如何添加自定義告警？**  
A: 在 prometheus-deployment.yaml ConfigMap 中添加規則

**Q: 支持多集群監控嗎？**  
A: 支持，通過 Prometheus 聯合或中央 Prometheus

---

## 🏆 最佳實踐

1. **定期備份監控數據**
   - 定期 snapshot PVC
   - 保留至少 30 天數據

2. **設置告警規則**
   - CPU > 80% 告警
   - Pod 不就緒告警
   - MySQL 連接過多告警

3. **集成 Grafana**
   - 美化儀表板
   - 便於團隊查看
   - 支持報表生成

4. **定期審查指標**
   - 監控容量使用趨勢
   - 規劃擴容時機
   - 識別異常模式

---

## 📈 監控成熟度等級

### 等級 1: 基礎監控 (本方案提供)

- ✅ 實時系統指標
- ✅ Pod 狀態監控
- ✅ MySQL 基本指標
- ✅ 簡單告警

### 等級 2: 增強監控 (進階)

- 應用性能監控 (APM)
- 分布式追蹤 (Tracing)
- 日誌聚合 (ELK)

### 等級 3: 成熟監控 (企業級)

- 機器學習異常檢測
- 自動化響應
- 完整可觀測性 (O11y)

---

## 🎯 下一步

1. **立即開始**: `bash deploy-monitoring.sh deploy-all`
2. **學習 PromQL**: 訪問 Prometheus 官方文檔
3. **集成 Grafana**: 安裝 Grafana 並匯入儀表板
4. **配置告警**: 添加告警規則並集成 Slack/釘釘
5. **持續改進**: 根據監控數據調整配置

---

## 📝 重要提醒

### 安全事項

- ✅ 限制 Prometheus 訪問 IP 範圍
- ✅ MySQL 密碼通過 Secrets 管理
- ✅ 定期更新 Prometheus 和 Exporters
- ✅ 監控數據備份

### 性能考慮

- Prometheus: ~100m CPU + 1Gi Memory
- MySQL Exporter: ~50m CPU + 100Mi Memory
- 總體開銷: < 200m CPU + 2Gi Memory

### 數據保留

- 默認 30 天（可配置）
- 磁盤占用: ~50Gi（可調整）
- 支持外部存儲（可選）

---

## 📞 技術支持

遇到問題？按順序嘗試：

1. 查看相應的指南文檔
2. 檢查 pod 日誌: `kubectl logs <pod-name>`
3. 運行驗證: `bash deploy-monitoring.sh verify`
4. 查詢 Prometheus targets: http://localhost:9090/targets

---

## ✨ 總結

### 你現在擁有

- ✅ **3 層監控工具** (離線、kubectl、Prometheus)
- ✅ **完整部署配置** (一鍵部署)
- ✅ **6 份詳細指南** (快速到深入)
- ✅ **自動化腳本** (簡化操作)
- ✅ **生產就緒** (經過驗證)

### 核心優勢

- 🔐 無需 kubectl 權限的監控
- 📊 實時 + 歷史 + 告警的完整方案
- 🚀 3 分鐘快速部署
- 📖 完善的文檔支持

### 推薦使用場景

| 場景 | 推薦工具 |
|------|---------|
| 部署前驗證 | 離線工具 |
| 部署直後檢查 | kubectl 工具 |
| 長期監控 | **Prometheus 工具** ⭐ |
| 沒有 kubectl 權限 | **Prometheus 工具** ⭐ |
| 生產環境運維 | **Prometheus 工具** ⭐ |

---

## 🎉 立即開始

```bash
# 進入工具目錄
cd tools

# 一鍵部署和驗證
bash deploy-monitoring.sh deploy-all && bash deploy-monitoring.sh verify

# 啟動實時監控
python k8s_prometheus_monitor.py

# 選擇 2: 持續監控（每 5 秒更新）
```

**祝監控順利！** 🚀

---

**版本**: 1.0  
**更新**: 2026-01-01  
**狀態**: ✅ 生產就緒  
**支持**: 完整文檔 + 自動化腳本
