# 📁 Tools 資料夾結構說明

## 新的組織結構

```
tools/
├── 🟢 core-tools/                 核心監控工具 (Python 腳本)
│   ├── k8s_prometheus_monitor.py          ⭐ Prometheus 實時監控工具
│   ├── k8s_deployment_checker.py          kubectl 部署檢查工具
│   ├── k8s_deployment_checker_offline.py  離線配置檢查工具
│   ├── connection_pool_calculator.py      連接池計算工具
│   └── pod_rps_monitor.py                 RPS 監控工具
│
├── 🟡 deployments/                部署配置檔案 (YAML)
│   ├── prometheus-deployment.yaml         ⭐ Prometheus 部署
│   ├── mysql-exporter-deployment.yaml     MySQL Exporter 部署
│   └── example-deployment.yaml            OpenFGA 範例配置
│
├── 🟠 scripts/                    自動化腳本 (Shell)
│   └── deploy-monitoring.sh               ⭐ 一鍵部署腳本
│
├── 🔵 docs/                       詳細文檔 (Markdown)
│   ├── START_HERE.md                      ⭐ 首先閱讀
│   ├── QUICK_REFERENCE.md                 快速參考卡
│   ├── PROMETHEUS_SOLUTION_SUMMARY.md     完整方案說明
│   ├── PROMETHEUS_MONITORING_GUIDE.md     詳細技術指南
│   ├── COMPLETE_MONITORING_GUIDE.md       工具完整對比
│   ├── README_MONITORING.md               工具概覽
│   ├── FILE_MANIFEST.md                   文件清單
│   ├── OFFLINE_CHECKER_GUIDE.md           離線工具指南
│   └── FINAL_SUMMARY.md                   最終總結
│
├── 🟣 examples/                   範例和範本
│   └── example-deployment.yaml            OpenFGA + Galera 範例
│
└── 其他文件
    └── .gitignore                 git 忽略配置
```

---

## 📂 各資料夾說明

### 1️⃣ `core-tools/` - 核心監控工具

**用途**: 存放所有 Python 監控工具

**檔案清單**:

| 工具                                | 說明                   | 使用時機             |
| ----------------------------------- | ---------------------- | -------------------- |
| `k8s_prometheus_monitor.py`         | ⭐ Prometheus 實時監控 | 長期監控，無 kubectl |
| `k8s_deployment_checker.py`         | kubectl 狀態檢查       | 部署直後             |
| `k8s_deployment_checker_offline.py` | 離線配置驗證           | 部署前               |
| `connection_pool_calculator.py`     | 連接池計算             | 配置優化             |
| `pod_rps_monitor.py`                | RPS 監控               | 性能測試             |

**使用方式**:

```bash
cd tools/core-tools
python k8s_prometheus_monitor.py
```

---

### 2️⃣ `deployments/` - 部署配置檔案

**用途**: 存放所有 Kubernetes YAML 配置

**檔案清單**:

| 配置                             | 說明                      | 部署順序      |
| -------------------------------- | ------------------------- | ------------- |
| `prometheus-deployment.yaml`     | ⭐ Prometheus 完整部署    | 1️⃣ 第一個部署 |
| `mysql-exporter-deployment.yaml` | MySQL/Galera metrics 導出 | 2️⃣ 第二個部署 |
| `example-deployment.yaml`        | OpenFGA + Galera 範例     | 3️⃣ 參考使用   |

**使用方式**:

```bash
cd tools/deployments
kubectl apply -f prometheus-deployment.yaml
kubectl apply -f mysql-exporter-deployment.yaml
```

---

### 3️⃣ `scripts/` - 自動化腳本

**用途**: 存放自動化部署和管理腳本

**檔案清單**:

| 腳本                   | 說明            | 功能                 |
| ---------------------- | --------------- | -------------------- |
| `deploy-monitoring.sh` | ⭐ 一鍵部署腳本 | 環境檢查、部署、驗證 |

**使用方式**:

```bash
cd tools/scripts
bash deploy-monitoring.sh deploy-all      # 一鍵部署
bash deploy-monitoring.sh verify          # 驗證部署
bash deploy-monitoring.sh monitor         # 啟動監控
```

**支持的命令**:

```
check               環境檢查
deploy-prometheus  部署 Prometheus
deploy-exporter    部署 MySQL Exporter
deploy-all         一鍵部署所有
verify             驗證部署
monitor            啟動監控工具
uninstall          卸載監控
```

---

### 4️⃣ `docs/` - 詳細文檔

**用途**: 存放所有說明文檔和指南

**推薦閱讀順序**:

| #   | 文檔                             | 長度 | 重點            |
| --- | -------------------------------- | ---- | --------------- |
| 1️⃣  | `START_HERE.md`                  | 8 頁 | **首先閱讀** ⭐ |
| 2️⃣  | `QUICK_REFERENCE.md`             | 1 頁 | 快速查詢        |
| 3️⃣  | `PROMETHEUS_SOLUTION_SUMMARY.md` | 3 頁 | 完整方案        |
| 4️⃣  | `PROMETHEUS_MONITORING_GUIDE.md` | 8 頁 | 詳細技術        |
| 5️⃣  | `COMPLETE_MONITORING_GUIDE.md`   | 6 頁 | 工具對比        |
| 6️⃣  | `README_MONITORING.md`           | 5 頁 | 工具概覽        |
| 7️⃣  | `FILE_MANIFEST.md`               | 5 頁 | 文件清單        |
| 8️⃣  | `OFFLINE_CHECKER_GUIDE.md`       | 4 頁 | 離線工具        |
| 9️⃣  | `FINAL_SUMMARY.md`               | 8 頁 | 最終總結        |

**按場景查找**:

- 🟢 **初級**（新手快速上手）

  - START_HERE.md
  - QUICK_REFERENCE.md

- 🟡 **中級**（深入了解方案）

  - PROMETHEUS_SOLUTION_SUMMARY.md
  - README_MONITORING.md

- 🔴 **高級**（詳細技術文檔）
  - PROMETHEUS_MONITORING_GUIDE.md
  - COMPLETE_MONITORING_GUIDE.md

---

### 5️⃣ `examples/` - 範例和範本

**用途**: 存放可復用的範例配置

**包含內容**:

- `example-deployment.yaml` - OpenFGA + Galera 完整範例配置

**使用方式**:

```bash
cp tools/examples/example-deployment.yaml ./my-deployment.yaml
kubectl apply -f my-deployment.yaml
```

---

## 🚀 快速開始指南

### 方式 A: 使用自動化腳本（推薦）

```bash
cd tools/scripts
bash deploy-monitoring.sh deploy-all
bash deploy-monitoring.sh verify
```

### 方式 B: 手動部署

```bash
# 1. 部署 Prometheus
kubectl apply -f tools/deployments/prometheus-deployment.yaml

# 2. 部署 MySQL Exporter
kubectl apply -f tools/deployments/mysql-exporter-deployment.yaml

# 3. 驗證
kubectl get pods -n monitoring
```

### 方式 C: 運行監控工具

```bash
cd tools/core-tools
python k8s_prometheus_monitor.py
```

---

## 📖 文檔快速查找

### 按問題類型查找

**Q: 我是第一次使用，不知道從何開始？**  
→ 讀 `docs/START_HERE.md`

**Q: 我需要快速參考命令？**  
→ 查 `docs/QUICK_REFERENCE.md`

**Q: 我想了解完整的監控方案？**  
→ 閱讀 `docs/PROMETHEUS_SOLUTION_SUMMARY.md`

**Q: 我需要詳細的技術文檔？**  
→ 參考 `docs/PROMETHEUS_MONITORING_GUIDE.md`

**Q: 我想比較三種監控工具？**  
→ 查看 `docs/COMPLETE_MONITORING_GUIDE.md`

**Q: 離線工具如何使用？**  
→ 讀 `docs/OFFLINE_CHECKER_GUIDE.md`

### 按場景查找

| 場景           | 推薦文檔                       |
| -------------- | ------------------------------ |
| 部署前配置驗證 | OFFLINE_CHECKER_GUIDE.md       |
| 部署後狀態檢查 | README_MONITORING.md           |
| 長期實時監控   | PROMETHEUS_MONITORING_GUIDE.md |
| 工具選型決策   | COMPLETE_MONITORING_GUIDE.md   |
| 完整方案概述   | PROMETHEUS_SOLUTION_SUMMARY.md |
| 快速命令查詢   | QUICK_REFERENCE.md             |

---

## 💻 常用命令集合

### 部署相關

```bash
# 從 scripts 目錄
cd tools/scripts
bash deploy-monitoring.sh check
bash deploy-monitoring.sh deploy-all
bash deploy-monitoring.sh verify

# 或手動部署
cd tools/deployments
kubectl apply -f prometheus-deployment.yaml
kubectl apply -f mysql-exporter-deployment.yaml
```

### 監控工具相關

```bash
# 從 core-tools 目錄
cd tools/core-tools

# Prometheus 實時監控
python k8s_prometheus_monitor.py

# 配置驗證
python k8s_deployment_checker_offline.py

# kubectl 狀態檢查
python k8s_deployment_checker.py

# 連接池計算
python connection_pool_calculator.py
```

### 文檔查看

```bash
# 開啟首頁
cat tools/docs/START_HERE.md

# 快速參考
cat tools/docs/QUICK_REFERENCE.md

# 部署指南
cat tools/docs/PROMETHEUS_MONITORING_GUIDE.md
```

---

## 📊 資料夾使用統計

| 資料夾         | 檔案數        | 大小   | 說明         |
| -------------- | ------------- | ------ | ------------ |
| `core-tools/`  | 5 個 Python   | ~50KB  | 核心監控工具 |
| `deployments/` | 3 個 YAML     | ~15KB  | K8s 配置     |
| `scripts/`     | 1 個 Shell    | ~10KB  | 自動化腳本   |
| `docs/`        | 9 個 Markdown | ~200KB | 詳細文檔     |
| `examples/`    | 1 個 YAML     | ~3KB   | 範例配置     |

**總計**: 19 個檔案，~280KB

---

## 🔧 維護指南

### 新增工具時

1. Python 工具 → `core-tools/`
2. YAML 配置 → `deployments/`
3. Shell 腳本 → `scripts/`
4. 文檔 → `docs/`
5. 範例 → `examples/`

### 更新現有工具時

1. 保持檔名不變
2. 更新 `docs/` 中的相應文檔
3. 更新 `START_HERE.md` 中的版本號

### 清理無用檔案

```bash
# 根目錄下的原始檔案可以刪除
rm -f tools/*.py tools/*.yaml tools/*.sh
```

---

## ✅ 整理前後對比

### 整理前 ❌

```
tools/
├── k8s_prometheus_monitor.py
├── k8s_deployment_checker.py
├── k8s_deployment_checker_offline.py
├── prometheus-deployment.yaml
├── mysql-exporter-deployment.yaml
├── example-deployment.yaml
├── deploy-monitoring.sh
├── connection_pool_calculator.py
├── pod_rps_monitor.py
├── START_HERE.md
├── QUICK_REFERENCE.md
├── PROMETHEUS_SOLUTION_SUMMARY.md
├── PROMETHEUS_MONITORING_GUIDE.md
├── COMPLETE_MONITORING_GUIDE.md
├── README_MONITORING.md
├── FILE_MANIFEST.md
├── OFFLINE_CHECKER_GUIDE.md
├── FINAL_SUMMARY.md
├── .gitignore
└── ... 混亂！
```

### 整理後 ✅

```
tools/
├── core-tools/          (5 個 Python 工具)
├── deployments/         (3 個 YAML 配置)
├── scripts/             (1 個 Shell 腳本)
├── docs/                (9 個文檔)
├── examples/            (1 個範例)
└── .gitignore           (Git 配置)
```

---

## 📝 下一步建議

### 立即操作

1. ✅ 使用新的資料夾結構（已完成）
2. 👉 根據需要刪除根目錄下的舊檔案（可選）
3. 📖 閱讀 `docs/START_HERE.md`
4. 🚀 運行 `scripts/deploy-monitoring.sh deploy-all`

### 日常使用

1. 部署工具 → 進 `scripts/`
2. 查找工具 → 進 `core-tools/`
3. 修改配置 → 進 `deployments/`
4. 查閱文檔 → 進 `docs/`

### 長期維護

1. 新工具按類型放入對應資料夾
2. 新文檔放入 `docs/`
3. 定期更新 README（本檔案）

---

## 💡 提示

**快速導航**:

- 想快速開始？ → `docs/START_HERE.md`
- 想查快速命令？ → `docs/QUICK_REFERENCE.md`
- 想部署監控？ → `scripts/deploy-monitoring.sh`
- 想看部署配置？ → `deployments/`
- 想用監控工具？ → `core-tools/`

**環境變數建議**:

```bash
export TOOLS_DIR="/path/to/tools"
export TOOLS_CORE="${TOOLS_DIR}/core-tools"
export TOOLS_DEPLOY="${TOOLS_DIR}/deployments"
export TOOLS_DOCS="${TOOLS_DIR}/docs"
export TOOLS_SCRIPTS="${TOOLS_DIR}/scripts"
```

---

**版本**: 1.0  
**更新日期**: 2026-01-01  
**狀態**: ✅ 已整理完成
