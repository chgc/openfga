# K8s Deployment Checker - 離線模式使用指南

## 問題背景

原本的 `k8s_deployment_checker.py` 完全依賴 `kubectl` 命令，需要：
- Kubernetes 集群訪問權限
- kubectl 已安裝並配置
- 對目標 namespace 有讀取權限

**新的離線模式工具** (`k8s_deployment_checker_offline.py`) 可以在**沒有 kubectl 權限**的情況下：
- 靜態分析 YAML 配置文件
- 檢查資源配置是否符合高 RPS 規範
- 驗證連接池設置
- 計算總資源需求

## 使用方式

### 方式 1：分析 YAML 配置（最實用）

```bash
python k8s_deployment_checker_offline.py
# 選擇：1
# 輸入 YAML 文件路徑
```

或直接：

```bash
cd tools
python -c "from k8s_deployment_checker_offline import OfflineChecker; OfflineChecker().print_yaml_analysis('example-deployment.yaml')"
```

### 方式 2：生成範例配置

```bash
python k8s_deployment_checker_offline.py
# 選擇：3
# 輸入輸出路徑: mock_config.json
```

## 檢查項目

### 1. OpenFGA 配置檢查
- ✅ CPU request: 建議 500m-1000m
- ✅ Memory request: 建議 256Mi-512Mi
- ✅ 副本數: 建議 8-12 個（高 RPS）
- ✅ 資源限制設置

### 2. MariaDB Galera 配置檢查
- ✅ CPU request: 建議 ≥1000m (1 core)
- ✅ Memory request: 建議 2Gi-4Gi
- ✅ 副本數: 必須為 3
- ✅ 資源限制設置

### 3. 連接池配置檢查
從 ConfigMap 或環境變數檢查：
- `OPENFGA_DATASTORE_MAX_OPEN_CONNS`: 建議 100-300
- `OPENFGA_DATASTORE_MAX_IDLE_CONNS`: 建議 ≥50

### 4. 資源總計
- 計算所有 Pod 的總 CPU/Memory 需求
- 驗證是否足夠支撐高 RPS

### 5. 高可用性檢查
- OpenFGA 副本數 ≥ 8
- Galera 副本數 = 3
- 所有 Pod 設置資源限制

## 範例輸出

```
================================================================================
🔍 OpenFGA 部署配置分析（離線模式）
================================================================================

分析文件: example-deployment.yaml

[1] Deployment 配置分析
--------------------------------------------------------------------------------

OpenFGA Deployments: 1

  📦 openfga-server
     副本數: 10
     CPU: request=500m, limit=1000m
     Memory: request=256Mi, limit=512Mi
     ✅ 配置符合規範


MariaDB Galera Deployments: 1

  🗄️  mariadb-galera
     副本數: 3
     CPU: request=1000m, limit=2000m
     Memory: request=2Gi, limit=4Gi
     ✅ 配置符合規範


[2] 資源需求總計
--------------------------------------------------------------------------------

  總 CPU: 8.00 cores (8000 millicores)
  總 Memory: 8.00 GiB (8192 MiB)

  ⚠️  總 CPU 可能不足以支撐高 RPS（建議至少 10 cores）
  ⚠️  總 Memory 可能不足（建議至少 10 GiB）


[3] 連接池配置檢查
--------------------------------------------------------------------------------
  ✅ 連接池配置合理


[4] 高可用性檢查
--------------------------------------------------------------------------------
  ✅ OpenFGA 副本數 ≥ 8
  ✅ Galera 副本數 = 3
  ✅ 所有 Pod 設置資源限制

================================================================================
✅ 配置符合高 RPS 設計規範！

建議的下一步:
  1. 使用 kubectl apply 部署配置
  2. 等待所有 Pod 就緒
  3. 執行線上檢查: python k8s_deployment_checker.py
  4. 進行性能測試
================================================================================
```

## 優勢對比

| 功能 | 原版（kubectl） | 離線版 |
|------|----------------|--------|
| 需要 kubectl 權限 | ✅ 必須 | ❌ 不需要 |
| 檢查運行中的集群 | ✅ | ❌ |
| 靜態分析 YAML | ❌ | ✅ |
| 驗證配置規範 | 部分 | ✅ 完整 |
| 資源計算 | 運行時 | ✅ 規劃時 |
| 連接池配置檢查 | ❌ | ✅ |
| 適用階段 | 部署後 | ✅ 部署前+後 |

## 使用場景

### 場景 1：開發階段（本地）
- 沒有 K8s 集群訪問權限
- 需要驗證 YAML 配置是否合理
- **使用離線版** ✅

### 場景 2：CI/CD 流程
- 在部署前自動檢查配置
- 防止錯誤配置進入生產環境
- **使用離線版** ✅

### 場景 3：生產環境監控
- 已部署的集群
- 需要實時監控 Pod 狀態、資源使用
- **使用原版** ✅

### 場景 4：問題排查
- 集群已部署但有問題
- 需要同時檢查配置和運行狀態
- **兩個都用** ✅

## 工作流程建議

```
1. 📝 編寫 YAML 配置
   ↓
2. 🔍 離線檢查器驗證
   python k8s_deployment_checker_offline.py
   ↓
3. 📊 連接池計算器
   python connection_pool_calculator.py
   ↓
4. 🚀 部署到 K8s
   kubectl apply -f deployment.yaml
   ↓
5. ✅ 線上檢查器驗證
   python k8s_deployment_checker.py
   ↓
6. 🧪 性能測試
```

## 兩個工具的搭配使用

```bash
# 階段 1：部署前（離線）
cd tools
python k8s_deployment_checker_offline.py
# 選擇 1，輸入你的 YAML 文件路徑

# 階段 2：計算連接池
python connection_pool_calculator.py
# 根據結果調整 YAML 中的連接池配置

# 階段 3：部署
kubectl apply -f your-deployment.yaml

# 階段 4：部署後驗證（線上）
python k8s_deployment_checker.py
# 檢查實際運行狀態
```

## 快速測試

使用提供的範例配置測試：

```bash
cd tools
python k8s_deployment_checker_offline.py
# 選擇: 1
# 輸入: example-deployment.yaml
```

或使用 Python 直接調用：

```python
from k8s_deployment_checker_offline import OfflineChecker

checker = OfflineChecker()
checker.print_yaml_analysis('example-deployment.yaml')
```

## 注意事項

1. **YAML 格式要求**
   - 必須是有效的 Kubernetes YAML
   - 支持多文檔 YAML（用 `---` 分隔）
   - 只分析 `Deployment` 和 `StatefulSet` 類型

2. **檢查規範**
   - 基於高 RPS 場景的最佳實踐
   - 可能需要根據實際需求調整閾值

3. **限制**
   - 無法檢查實際運行狀態
   - 無法驗證網絡連接
   - 無法測試實際性能

## 總結

**離線檢查器** 讓你在沒有 kubectl 權限的情況下：
- ✅ 提前驗證配置
- ✅ 避免部署錯誤
- ✅ 節省調試時間
- ✅ 符合 DevOps 最佳實踐

**配合原版工具**，可以實現完整的部署驗證流程！
