# 📦 Prometheus 監控方案 - 完整文件清單

## 🎯 快速導航

**首次使用？按這個順序讀**:
1. 📖 [快速參考卡](QUICK_REFERENCE.md) ← 從這裡開始 (2 分鐘)
2. 📋 [Prometheus 方案總結](PROMETHEUS_SOLUTION_SUMMARY.md) (10 分鐘)
3. 🚀 [快速部署](README_MONITORING.md#快速部署) (5 分鐘)
4. 📚 [完整指南](PROMETHEUS_MONITORING_GUIDE.md) (深入了解)

---

## 📂 文件結構

```
tools/
├── 【新增核心工具】
│   ├── k8s_prometheus_monitor.py              ⭐ Prometheus 實時監控
│   ├── prometheus-deployment.yaml             ⭐ Prometheus 部署配置
│   ├── mysql-exporter-deployment.yaml         ⭐ MySQL Exporter 配置
│   └── deploy-monitoring.sh                   ⭐ 快速部署腳本
│
├── 【新增詳細指南】
│   ├── PROMETHEUS_SOLUTION_SUMMARY.md         ⭐ Prometheus 方案說明
│   ├── PROMETHEUS_MONITORING_GUIDE.md         詳細使用指南
│   ├── COMPLETE_MONITORING_GUIDE.md           三工具完整對比
│   ├── README_MONITORING.md                   監控工具說明
│   └── QUICK_REFERENCE.md                     快速參考卡
│
├── 【既有工具】
│   ├── k8s_deployment_checker.py              kubectl 狀態檢查
│   ├── k8s_deployment_checker_offline.py      YAML 離線驗證
│   ├── connection_pool_calculator.py          連接池計算
│   ├── pod_rps_monitor.py                     RPS 監控
│   └── example-deployment.yaml                示例配置
│
└── 【配置文件】
    └── .gitignore
```

---

## 🆕 新增工具詳細說明

### 工具 #1: Prometheus 實時監控 ⭐⭐⭐

**文件**: `k8s_prometheus_monitor.py`

**用途**: 無需 kubectl 的實時監控和長期分析

**使用方式**:
```bash
python k8s_prometheus_monitor.py
# 選擇 1-4 中的操作
```

**功能特點**:
- ✅ 實時監控（15 秒刷新）
- ✅ 30 天歷史數據
- ✅ CPU/Memory/Network 完整指標
- ✅ MySQL 連接和查詢監控
- ✅ Galera 集群狀態
- ✅ 無需 kubectl（只需 Prometheus HTTP）

**輸出示例**: 儀表板風格，清晰的實時數據展示

**適用場景**: 
- 生產環境長期監控 ⭐
- 沒有 kubectl 權限
- 需要歷史數據分析

---

### 工具 #2: Prometheus 部署配置

**文件**: `prometheus-deployment.yaml`

**內容**:
- Prometheus StatefulSet
- Service 和 ConfigMap
- RBAC (ServiceAccount, ClusterRole)
- 50Gi 數據存儲

**部署方式**:
```bash
kubectl apply -f prometheus-deployment.yaml
```

**驗證**:
```bash
kubectl get pods -n monitoring
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# 訪問 http://localhost:9090
```

---

### 工具 #3: MySQL Exporter 配置

**文件**: `mysql-exporter-deployment.yaml`

**內容**:
- MySQL Exporter Deployment
- 自動收集 MySQL metrics
- 支持 Galera 監控

**配置要點**:
- MySQL 連接字符串需要更新
- 密碼通過 Kubernetes Secrets 管理
- 暴露 :9104 metrics 端口

---

### 工具 #4: 快速部署腳本

**文件**: `deploy-monitoring.sh`

**用途**: 自動化部署、驗證和管理

**命令列表**:
```bash
bash deploy-monitoring.sh check               # 檢查環境
bash deploy-monitoring.sh deploy-prometheus  # 部署 Prometheus
bash deploy-monitoring.sh deploy-exporter    # 部署 MySQL Exporter
bash deploy-monitoring.sh deploy-all         # 一鍵全部部署
bash deploy-monitoring.sh verify             # 驗證部署
bash deploy-monitoring.sh monitor            # 啟動監控工具
bash deploy-monitoring.sh uninstall          # 卸載監控
```

**特點**:
- 自動環境檢查
- 彩色日誌輸出
- 交互式菜單
- 非交互式支持（CI/CD）

---

## 📖 新增指南詳細說明

### #1 快速參考卡 (QUICK_REFERENCE.md)
**長度**: 1 頁  
**用途**: 快速查詢  
**適合**: 急著上手的人

**包含**:
- 三種工具速查表
- 常用命令集合
- 決策流程圖
- 常見問答

---

### #2 Prometheus 方案總結 (PROMETHEUS_SOLUTION_SUMMARY.md)
**長度**: 3 頁  
**用途**: 完整方案說明  
**適合**: 想全面了解的人

**包含**:
- 核心問題回答
- 三層監控解決方案
- 快速開始指南
- 監控最佳實踐
- 安全建議
- 告警規則示例

---

### #3 完整監控指南 (PROMETHEUS_MONITORING_GUIDE.md)
**長度**: 8 頁  
**用途**: 詳細技術文檔  
**適合**: 需要深入了解的人

**包含**:
- 架構圖
- 安裝步驟
- PromQL 查詢示例
- 告警配置
- Grafana 集成
- 故障排查
- 安全建議

---

### #4 完整工具對比 (COMPLETE_MONITORING_GUIDE.md)
**長度**: 6 頁  
**用途**: 工具選型參考  
**適合**: 需要做決策的人

**包含**:
- 三種工具詳細對比
- 使用決策樹
- 工作流程建議
- 成本效益分析
- 推薦配置

---

### #5 監控工具總體說明 (README_MONITORING.md)
**長度**: 5 頁  
**用途**: 總體概覽  
**適合**: 初次接觸的人

**包含**:
- 文檔導航
- 工具清單
- 使用場景
- 快速命令參考
- 故障排查
- 驗證清單

---

## 🚀 使用方式 (三選一)

### 方式 A: 快速部署（推薦）⭐

```bash
# 進入工具目錄
cd tools

# 一鍵部署
bash deploy-monitoring.sh deploy-all

# 驗證
bash deploy-monitoring.sh verify

# 啟動監控
python k8s_prometheus_monitor.py
```

**時間**: 5-10 分鐘

---

### 方式 B: 手動步驟部署

```bash
# 1. 部署 Prometheus
kubectl apply -f prometheus-deployment.yaml

# 2. 部署 MySQL Exporter
kubectl apply -f mysql-exporter-deployment.yaml

# 3. 檢查狀態
kubectl get pods -n monitoring
kubectl get pods -n openfga-prod

# 4. 訪問 Prometheus UI
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# 訪問 http://localhost:9090

# 5. 啟動監控工具
python k8s_prometheus_monitor.py
```

**時間**: 10-15 分鐘

---

### 方式 C: 完全自動化（CI/CD）

```bash
# 創建 deploy.sh
#!/bin/bash
cd tools
bash deploy-monitoring.sh check
bash deploy-monitoring.sh deploy-all
bash deploy-monitoring.sh verify

# 在 CI/CD 流程中執行
./deploy.sh
```

---

## 📊 功能對比表

### 工具功能矩陣

| 功能 | 離線工具 | kubectl 工具 | Prometheus 工具 |
|------|--------|----------|--------------|
| **需要權限** | ❌ | ✅ kubectl | ✅ HTTP |
| **何時用** | 部署前 | 部署後 | 長期監控 |
| **配置驗證** | ✅ | ❌ | ❌ |
| **實時狀態** | ❌ | ✅ | ✅ |
| **歷史數據** | ❌ | ❌ | ✅ 30天 |
| **告警規則** | ❌ | ❌ | ✅ |
| **Grafana** | ❌ | ❌ | ✅ |
| **Network I/O** | ❌ | ❌ | ✅ |

---

## 🎯 工作流程示例

### 開發環境

```
第 1 步: 驗證配置
python k8s_deployment_checker_offline.py
          ↓
第 2 步: 部署應用
kubectl apply -f my-deployment.yaml
          ↓
第 3 步: 檢查部署
python k8s_deployment_checker.py
```

### 生產環境 (推薦)

```
第 1 步: 驗證配置
python k8s_deployment_checker_offline.py
          ↓
第 2 步: 部署監控基礎設施
bash deploy-monitoring.sh deploy-all
          ↓
第 3 步: 部署應用
kubectl apply -f production-deployment.yaml
          ↓
第 4 步: 實時監控 (任何地方，無需 kubectl)
python k8s_prometheus_monitor.py
          ↓
第 5 步: 長期分析 (Prometheus UI)
http://prometheus-url:9090
          ↓
第 6 步: 可視化儀表板 (Grafana)
http://grafana-url:3000
```

---

## 💾 安裝依賴

### Python 依賴

```bash
# 監控工具需要
pip install requests

# Prometheus 部署（可選的 Grafana）
pip install prometheus-client
```

### 系統要求

- kubectl (部署時需要)
- Python 3.6+ (監控工具)
- Kubernetes 集群 (部署時需要)
- HTTP 訪問 Prometheus (監控時需要)

---

## 🔍 快速查看方式

### 查看 Prometheus UI

```bash
# 端口轉發
kubectl port-forward -n monitoring svc/prometheus 9090:9090

# 訪問
http://localhost:9090

# 查詢範例
rate(container_cpu_usage_seconds_total{namespace="openfga-prod"}[5m]) * 100
```

### 查看監控工具輸出

```bash
# 一次性報告
python k8s_prometheus_monitor.py  # 選擇 1

# 持續監控
python k8s_prometheus_monitor.py  # 選擇 2

# 自定義間隔
python k8s_prometheus_monitor.py  # 選擇 3
```

---

## 🎓 推薦學習路徑

### 初級 (第 1 天)

1. 閱讀 [快速參考卡](QUICK_REFERENCE.md)
2. 執行快速部署
3. 查看實時監控輸出

### 中級 (第 2-3 天)

1. 詳細閱讀 [Prometheus 指南](PROMETHEUS_MONITORING_GUIDE.md)
2. 學習 PromQL 查詢
3. 訪問 Prometheus UI 進行查詢

### 高級 (第 4-7 天)

1. 配置自定義告警規則
2. 集成 Grafana 儀表板
3. 設置 Alertmanager 通知

---

## 📞 常見問答

**Q: Prometheus 監控需要 kubectl 權限嗎?**  
A: 部署時需要，監控時完全不需要

**Q: 能保留多久的數據?**  
A: 默認 30 天（可配置）

**Q: 支持告警嗎?**  
A: 完全支持，通過 PromQL 規則

**Q: 性能開銷大嗎?**  
A: 很小，通常 < 200m CPU + 2Gi Memory

**Q: 可以和 Grafana 配合嗎?**  
A: 可以，Prometheus 是 Grafana 的主要數據源

---

## 🎉 總結

**你現在擁有**:

1. ✅ 完整的監控工具套件 (3 種工具)
2. ✅ 部署配置 (Prometheus + MySQL Exporter)
3. ✅ 快速部署腳本
4. ✅ 詳細的文檔和指南
5. ✅ 工作流程和最佳實踐

**立即開始**:
```bash
bash deploy-monitoring.sh deploy-all
python k8s_prometheus_monitor.py
```

**下一步**: 根據場景選擇適合的工具，參考相應的指南文檔。

---

**更新日期**: 2026-01-01  
**工具版本**: 1.0  
**狀態**: ✅ 生產就緒
