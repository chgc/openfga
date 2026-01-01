# 🗂️ Tools 整理完成！快速導航指南

## 📍 新的資料夾結構已完成

你的 `tools/` 資料夾已按功能分類整理：

```
tools/
├── 📂 core-tools/      → 核心監控工具（5 個 Python）
├── 📂 deployments/     → 部署配置（3 個 YAML）
├── 📂 scripts/         → 自動化腳本（1 個 Shell）
├── 📂 docs/            → 詳細文檔（9 個 Markdown）
├── 📂 examples/        → 範例配置（1 個 YAML）
├── INDEX.md            → 完整的整理說明
└── 其他根目錄檔案...
```

---

## 🚀 快速開始 (3 分鐘)

### 方式 A: 使用自動化腳本（最簡單）

```bash
cd tools/scripts
bash deploy-monitoring.sh deploy-all
bash deploy-monitoring.sh verify
```

### 方式 B: 運行監控工具

```bash
cd tools/core-tools
python k8s_prometheus_monitor.py
```

### 方式 C: 手動部署

```bash
kubectl apply -f tools/deployments/prometheus-deployment.yaml
kubectl apply -f tools/deployments/mysql-exporter-deployment.yaml
```

---

## 📂 各資料夾用途

### 🟢 `core-tools/` - 監控工具

| 工具                                | 用途                                       |
| ----------------------------------- | ------------------------------------------ |
| `k8s_prometheus_monitor.py`         | ⭐ **Prometheus 實時監控**（無需 kubectl） |
| `k8s_deployment_checker.py`         | kubectl 部署檢查                           |
| `k8s_deployment_checker_offline.py` | 離線配置驗證                               |
| `connection_pool_calculator.py`     | 連接池計算                                 |
| `pod_rps_monitor.py`                | RPS 監控                                   |

```bash
cd tools/core-tools
python k8s_prometheus_monitor.py
```

---

### 🟡 `deployments/` - 部署配置

| 配置                             | 用途              | 部署順序 |
| -------------------------------- | ----------------- | -------- |
| `prometheus-deployment.yaml`     | ⭐ **Prometheus** | 1️⃣ 優先  |
| `mysql-exporter-deployment.yaml` | MySQL Exporter    | 2️⃣ 其次  |
| `example-deployment.yaml`        | 範例（參考）      | 3️⃣ 參考  |

```bash
kubectl apply -f tools/deployments/prometheus-deployment.yaml
```

---

### 🟠 `scripts/` - 自動化腳本

| 腳本                   | 功能            |
| ---------------------- | --------------- |
| `deploy-monitoring.sh` | ⭐ **一鍵部署** |

**支持的命令**:

```bash
cd tools/scripts

bash deploy-monitoring.sh check           # 檢查環境
bash deploy-monitoring.sh deploy-all      # 一鍵部署
bash deploy-monitoring.sh verify          # 驗證部署
bash deploy-monitoring.sh monitor         # 啟動監控
bash deploy-monitoring.sh uninstall       # 卸載監控
```

---

### 🔵 `docs/` - 詳細文檔

**推薦閱讀順序**:

1. ⭐ **[START_HERE.md](docs/START_HERE.md)** - 首先閱讀（核心概念，5 分鐘）
2. **[QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** - 快速查詢卡（2 分鐘）
3. **[PROMETHEUS_SOLUTION_SUMMARY.md](docs/PROMETHEUS_SOLUTION_SUMMARY.md)** - 完整方案（10 分鐘）
4. **[PROMETHEUS_MONITORING_GUIDE.md](docs/PROMETHEUS_MONITORING_GUIDE.md)** - 技術細節（30 分鐘）
5. **[COMPLETE_MONITORING_GUIDE.md](docs/COMPLETE_MONITORING_GUIDE.md)** - 工具對比（20 分鐘）
6. **[README_MONITORING.md](docs/README_MONITORING.md)** - 工具概覽（15 分鐘）

**按場景查找**:

- 🟢 **新手** → START_HERE.md + QUICK_REFERENCE.md
- 🟡 **中級** → PROMETHEUS_SOLUTION_SUMMARY.md
- 🔴 **高級** → PROMETHEUS_MONITORING_GUIDE.md

---

### 🟣 `examples/` - 範例配置

| 範例                      | 說明                      |
| ------------------------- | ------------------------- |
| `example-deployment.yaml` | OpenFGA + Galera 完整範例 |

```bash
cp tools/examples/example-deployment.yaml ./my-deployment.yaml
kubectl apply -f my-deployment.yaml
```

---

## 📍 整理資源總結

### 📊 檔案統計

| 類型           | 數量   | 位置           |
| -------------- | ------ | -------------- |
| 🐍 Python 工具 | 5      | `core-tools/`  |
| 📝 YAML 配置   | 3      | `deployments/` |
| 🔧 Shell 腳本  | 1      | `scripts/`     |
| 📖 文檔        | 9      | `docs/`        |
| 📋 範例        | 1      | `examples/`    |
| **總計**       | **19** | **已整理** ✅  |

---

## 💡 常用命令速查

### 最常用的 3 個命令

```bash
# 1️⃣ 一鍵部署（5 分鐘）
cd tools/scripts && bash deploy-monitoring.sh deploy-all

# 2️⃣ 驗證部署（1 分鐘）
cd tools/scripts && bash deploy-monitoring.sh verify

# 3️⃣ 啟動監控（立即）
cd tools/core-tools && python k8s_prometheus_monitor.py
```

### 按用途分類

```bash
# 🔍 配置驗證（部署前）
cd tools/core-tools && python k8s_deployment_checker_offline.py

# ✅ 部署檢查（部署後）
cd tools/core-tools && python k8s_deployment_checker.py

# 📊 實時監控（長期運維）
cd tools/core-tools && python k8s_prometheus_monitor.py

# 🔧 部署配置
ls tools/deployments/*.yaml

# 📚 查看文檔
cat tools/docs/START_HERE.md
```

---

## 🎯 五分鐘快速開始

### 第 1 步：檢查環境（1 分鐘）

```bash
cd tools/scripts
bash deploy-monitoring.sh check
```

### 第 2 步：部署監控（2 分鐘）

```bash
bash deploy-monitoring.sh deploy-all
```

### 第 3 步：驗證部署（1 分鐘）

```bash
bash deploy-monitoring.sh verify
```

### 第 4 步：啟動監控（1 分鐘）

```bash
cd ../core-tools
python k8s_prometheus_monitor.py
# 選擇 2: 持續監控
```

**完成！你現在有了實時監控系統！** 🎉

---

## 📖 各類用戶的推薦路徑

### 👨‍💼 我是管理員（沒有技術背景）

1. 閱讀 `docs/START_HERE.md` (10 分鐘)
2. 運行 `scripts/deploy-monitoring.sh deploy-all` (5 分鐘)
3. 訪問 Prometheus UI 查看數據

### 👨‍💻 我是開發者（想快速上手）

1. 閱讀 `docs/QUICK_REFERENCE.md` (2 分鐘)
2. 運行部署腳本 (5 分鐘)
3. 修改 `deployments/` 中的配置 (15 分鐘)
4. 查看 `docs/PROMETHEUS_MONITORING_GUIDE.md`

### 🔬 我是架構師（需要深入理解）

1. 閱讀 `docs/COMPLETE_MONITORING_GUIDE.md` (30 分鐘)
2. 分析 `docs/PROMETHEUS_SOLUTION_SUMMARY.md` (15 分鐘)
3. 審查 `deployments/` 中的配置 (20 分鐘)
4. 配置自定義告警規則 (1 小時)

---

## ✨ 核心特點提醒

### 🔐 無需 kubectl 權限

```bash
# Prometheus 監控只需要 HTTP 訪問
# 可在任何地方運行，無需集群訪問
cd tools/core-tools
python k8s_prometheus_monitor.py
```

### 📊 實時 + 歷史 + 告警

- ⏱️ **實時**: 15 秒刷新
- 📈 **歷史**: 30 天數據保留
- 🚨 **告警**: PromQL 規則系統

### 🚀 一鍵部署

```bash
# 無需複雜配置，直接運行
bash tools/scripts/deploy-monitoring.sh deploy-all
```

---

## 📞 常見問題

**Q: 檔案在哪個資料夾？**

```
.py 工具     → tools/core-tools/
.yaml 配置   → tools/deployments/
.sh 腳本     → tools/scripts/
.md 文檔     → tools/docs/
範例         → tools/examples/
```

**Q: 從哪裡開始？**  
→ `tools/docs/START_HERE.md`

**Q: 如何部署？**  
→ `tools/scripts/deploy-monitoring.sh deploy-all`

**Q: 如何監控？**  
→ `tools/core-tools/k8s_prometheus_monitor.py`

**Q: 找不到檔案？**  
→ 查看 `tools/INDEX.md` 的完整說明

---

## 🎓 後續學習

### 初級（今天）

- [ ] 閱讀 START_HERE.md
- [ ] 運行部署腳本
- [ ] 看到實時監控數據

### 中級（本週）

- [ ] 閱讀 PROMETHEUS_MONITORING_GUIDE.md
- [ ] 學習 PromQL 查詢
- [ ] 配置自定義告警

### 高級（本月）

- [ ] 集成 Grafana
- [ ] 設置 Alertmanager
- [ ] 優化監控規則

---

## 📝 維護提示

### 添加新工具時

1. Python 工具 → `core-tools/`
2. YAML 配置 → `deployments/`
3. Shell 腳本 → `scripts/`
4. 文檔 → `docs/`

### 清理根目錄

原始檔案已複製到各資料夾，可刪除：

```bash
cd tools
rm -f *.py *.yaml *.sh  # 保留 .md 和 .gitignore
```

---

## 🏁 立即行動

### 現在就開始（5 分鐘）

```bash
cd tools/scripts
bash deploy-monitoring.sh deploy-all
```

### 完成後（立即）

```bash
cd ../core-tools
python k8s_prometheus_monitor.py
# 選擇 2: 持續監控
```

---

## 📚 相關文件

- **完整說明**: [INDEX.md](INDEX.md)
- **核心文檔**: [docs/START_HERE.md](docs/START_HERE.md)
- **快速參考**: [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)
- **技術指南**: [docs/PROMETHEUS_MONITORING_GUIDE.md](docs/PROMETHEUS_MONITORING_GUIDE.md)

---

**✅ 整理完成！開始使用新的結構吧！** 🎉

**更新日期**: 2026-01-01  
**版本**: 1.0  
**狀態**: 生產就緒 ✨
