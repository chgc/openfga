# OpenFGA Experimental Check 記憶體管理與保護機制

## 概述

實驗性 Check 優化（Planner + Thompson Sampling）會將查詢計畫儲存在記憶體中以進行持續學習。為了防止無限的記憶體增長，OpenFGA 提供了多層的配置和保護機制。

---

## 1. 記憶體使用分析

### 1.1 每個計畫的記憶體佔用

**單個 `keyPlan` 物件的記憶體成本**:

```
keyPlan 結構:
├─ stats (sync.Map)
│  └─ 儲存每個策略的 ThompsonStats
│     ├─ default: 1 個 ThompsonStats (~112 bytes)
│     ├─ weight2: 1 個 ThompsonStats (~112 bytes)
│     └─ recursive: 1 個 ThompsonStats (~112 bytes)
│     小計: ~336 bytes
├─ planner (指標): 8 bytes
└─ lastAccessed (atomic.Int64): 8 bytes
────────────────────────────────
小計: ~360 bytes (單個 keyPlan)
```

**ThompsonStats 結構**:

```
ThompsonStats:
└─ params (unsafe.Pointer)
   └─ samplingParams
      ├─ mu (float64): 8 bytes
      ├─ lambda (float64): 8 bytes
      ├─ alpha (float64): 8 bytes
      ├─ beta (float64): 8 bytes
      └─ 小計: 32 bytes (~112 bytes with overhead)
```

### 1.2 典型場景的記憶體估算

**場景 1: 小型應用**

```
査詢模式數: 100 個 (Userset 和 TTU 的組合)
每個 keyPlan: ~360 bytes
其他開銷: ~10%
────────────────────
總記憶體: ~100 × 360 × 1.1 ≈ 40 KB
評估: 可忽略不計
```

**場景 2: 中型應用**

```
査詢模式數: 10,000 個 (複雜的多租戶系統)
每個 keyPlan: ~360 bytes
其他開銷: ~10%
────────────────────
總記憶體: ~10,000 × 360 × 1.1 ≈ 4 MB
評估: 可接受
```

**場景 3: 大型應用（潛在問題）**

```
査詢模式數: 1,000,000 個 (動態、無限增長的模式)
每個 keyPlan: ~360 bytes
其他開銷: ~10%
────────────────────
總記憶體: ~1,000,000 × 360 × 1.1 ≈ 400 MB
評估: 有問題，需要驅逐機制
```

---

## 2. 保護機制概覽

### 2.1 多層防護

```
第一層: 驅逐機制 (Eviction)
└─ EvictionThreshold: 多久未使用的計畫會被移除

第二層: 清理循環 (Cleanup)
└─ CleanupInterval: 多久檢查一次是否有陳舊計畫

第三層: 代碼註釋警告
└─ "Consider also bounding the total number of keys stored"
   (建議也限制儲存的總鍵數)
```

### 2.2 預設配置

```go
// pkg/server/config/config.go
DefaultPlannerEvictionThreshold = 0          // 禁用（永不驅逐）
DefaultPlannerCleanupInterval   = 0          // 禁用（無清理）
```

**預設行為**:

- ✅ 優勢: 最大化學習，計畫永不遺忘
- ❌ 風險: 記憶體可能無限增長

---

## 3. 配置選項詳解

### 3.1 EvictionThreshold (驅逐阈值)

**含義**: 計畫多久未被使用就會從記憶體中移除

```go
type Config struct {
    EvictionThreshold time.Duration  // e.g., 30 * time.Minute
    CleanupInterval   time.Duration  // e.g., 5 * time.Minute
}
```

**實現機制**:

```go
func (p *Planner) evictStaleKeys() {
    evictionThresholdNano := p.evictionThreshold.Nanoseconds()
    nowNano := time.Now().UnixNano()

    p.keys.Range(func(key, value interface{}) bool {
        kp := value.(*keyPlan)
        lastAccessed := kp.lastAccessed.Load()
        // 如果上次訪問時間超過閾值，移除該計畫
        if (nowNano - lastAccessed) > evictionThresholdNano {
            p.keys.Delete(key)
        }
        return true
    })
}
```

**設定範例**:

| 配置值             | 場景         | 效果                |
| ------------------ | ------------ | ------------------- |
| `0` (預設)         | 長期穩定負載 | 永不驅逐，最大學習  |
| `15 * time.Minute` | 中等應用     | 15 分鐘未使用則移除 |
| `30 * time.Minute` | 推薦設定     | 30 分鐘未使用則移除 |
| `1 * time.Hour`    | 多樣化負載   | 1 小時未使用則移除  |
| `24 * time.Hour`   | 低記憶體環境 | 1 天未使用則移除    |

### 3.2 CleanupInterval (清理間隔)

**含義**: 後臺清理程序多久運行一次

```go
func (p *Planner) startCleanupRoutine(interval time.Duration) {
    ticker := time.NewTicker(interval)
    // 每隔 interval 時間執行一次 evictStaleKeys()
    // ...
}
```

**設定範例**:

| 配置值             | 說明                         |
| ------------------ | ---------------------------- |
| `0` (預設)         | 不啟動清理程序               |
| `1 * time.Minute`  | 每分鐘檢查一次（頻繁）       |
| `5 * time.Minute`  | 每 5 分鐘檢查一次（推薦）    |
| `10 * time.Minute` | 每 10 分鐘檢查一次（較鬆散） |

### 3.3 配置的組合效應

```
情況 1: 禁用驅逐（預設）
EvictionThreshold = 0
CleanupInterval = 0
────────────────────
結果: 永不清理，記憶體最大化但可能無限增長
使用場景: 完全受控的環境，査詢模式固定

情況 2: 啟用驅逐，禁用清理（不推薦）
EvictionThreshold = 30 * time.Minute
CleanupInterval = 0
────────────────────
結果: 定義了驅逐規則但無法執行，計畫不會被刪除
使用場景: 幾乎沒有實用價值

情況 3: 啟用驅逐和清理（推薦）
EvictionThreshold = 30 * time.Minute
CleanupInterval = 5 * time.Minute
────────────────────
結果: 每 5 分鐘檢查一次，移除超過 30 分鐘未使用的計畫
使用場景: 生產環境，多樣化負載

情況 4: 激進驅逐（低記憶體環境）
EvictionThreshold = 10 * time.Minute
CleanupInterval = 1 * time.Minute
────────────────────
結果: 計畫快速回收，學習週期短
使用場景: 記憶體受限，短期查詢模式變化快
```

---

## 4. 配置設定方式

### 4.1 命令行標誌

```bash
# 啟動 OpenFGA 時指定
openfga run \
  --planner-eviction-threshold=30m \
  --planner-cleanup-interval=5m
```

### 4.2 環境變數

```bash
export OPENFGA_PLANNER_EVICTION_THRESHOLD=30m
export OPENFGA_PLANNER_CLEANUP_INTERVAL=5m

openfga run
```

### 4.3 配置文件 (YAML)

```yaml
planner:
  evictionThreshold: 30m # 30 分鐘
  cleanupInterval: 5m # 5 分鐘
```

### 4.4 配置文件位置

```
搜尋順序:
1. /etc/openfga/config.yaml
2. $HOME/.openfga/config.yaml
3. ./config.yaml (當前目錄)
```

### 4.5 程式碼配置（開發環境）

```go
package main

import (
    "time"
    "github.com/openfga/openfga/internal/planner"
)

// 建立自訂 Planner
myPlanner := planner.New(&planner.Config{
    EvictionThreshold: 30 * time.Minute,
    CleanupInterval:   5 * time.Minute,
})

// 使用
defer myPlanner.Stop()
```

---

## 5. 建議的配置方案

### 方案 A: 開發環境

```yaml
planner:
  evictionThreshold: 0 # 不驅逐，最大化學習
  cleanupInterval: 0 # 不執行清理程序
```

**理由**:

- 開發中的查詢模式較固定
- 記憶體通常不是限制因素
- 最大化學習效果便於測試

### 方案 B: 中等生產環境（推薦）

```yaml
planner:
  evictionThreshold: 30m # 30 分鐘未使用則驅逐
  cleanupInterval: 5m # 每 5 分鐘檢查一次
```

**理由**:

- 平衡記憶體和學習效果
- 30 分鐘足以應對大多數查詢模式的學習
- 5 分鐘的清理頻率開銷很小

**典型記憶體成本**:

- 活躍計畫數: 5,000-10,000
- 記憶體佔用: 2-4 MB（可接受）
- 驅逐率: 中等（保持記憶體穩定）

### 方案 C: 高併發、多租戶環境

```yaml
planner:
  evictionThreshold: 15m # 15 分鐘（更激進）
  cleanupInterval: 3m # 每 3 分鐘檢查一次
```

**理由**:

- 大量不同的查詢模式
- 需要更激進的記憶體管理
- 更快的計畫回收防止無限增長

**典型記憶體成本**:

- 活躍計畫數: 2,000-5,000
- 記憶體佔用: 1-2 MB（更受控）
- 驅逐率: 高（頻繁回收）

### 方案 D: 記憶體受限環境

```yaml
planner:
  evictionThreshold: 10m # 10 分鐘（非常激進）
  cleanupInterval: 1m # 每分鐘檢查一次
```

**理由**:

- 優先考慮記憶體而非學習完整性
- 快速回收不常用的計畫
- 適合嵌入式或邊界計算環境

**典型記憶體成本**:

- 活躍計畫數: <2,000
- 記憶體佔用: <1 MB
- 驅逐率: 非常高（持續清理）

### 方案 E: 完全禁用（如果記憶體成為問題）

```yaml
experimentals:
  - "" # 不啟用 ExperimentalCheckOptimizations

# 或等同於
```

**何時考慮**:

- 記憶體極其受限（如 <100MB）
- 查詢模式過於多樣化（無法學習）
- 優先考慮固定的、可預測的效能

---

## 6. 監控和調試

### 6.1 檢查 Planner 是否啟用

```bash
# 查看日誌
# 應該看到 "🧪 experimental features enabled: ..."
grep "experimental features" openfga.log

# 或檢查啟用的特性
# 應該包含 "enable-check-optimizations"
```

### 6.2 監控記憶體使用

```bash
# 使用 pprof (內置分析工具)
go tool pprof http://localhost:6060/debug/pprof/heap

# 查詢相關:
# - sync.Map 的大小
# - planner.keyPlan 的數量
# - 堆記憶體用量趨勢
```

### 6.3 效能指標

```go
// 在代碼中查看
dispatchCountHistogram     // 分派次數
requestDurationHistogram   // 請求耗時

// 如果看到 dispatch 次數隨時間減少
// 表示 Planner 成功學習到更高效的策略
```

### 6.4 計畫驅逐日誌

在 `evictStaleKeys()` 中添加日誌（調試用）:

```go
// 簡單的計數版本
func (p *Planner) evictStaleKeys() {
    evictionThresholdNano := p.evictionThreshold.Nanoseconds()
    nowNano := time.Now().UnixNano()
    var evictedCount int

    p.keys.Range(func(key, value interface{}) bool {
        kp := value.(*keyPlan)
        lastAccessed := kp.lastAccessed.Load()
        if (nowNano - lastAccessed) > evictionThresholdNano {
            p.keys.Delete(key)
            evictedCount++
        }
        return true
    })

    if evictedCount > 0 {
        // log.Printf("Evicted %d stale plans", evictedCount)
    }
}
```

---

## 7. 代碼註釋中的警告

### 7.1 原始警告

```go
// evictStaleKeys() 中的註釋:
// NOTE: Consider also bounding the total number of keys stored.
```

**含義**: OpenFGA 開發團隊已意識到可能的無限增長問題，但目前只實現了時間型驅逐。

### 7.2 未來改進方向

可能的改進（非當前實現）:

```go
// 潛在的實現方式
type Config struct {
    EvictionThreshold  time.Duration  // 現有: 時間型
    MaxKeys            int            // 未實現: 總數限制
    EvictionPolicy     string         // 未實現: LRU/LFU/FIFO
}

// 例如:
// - LRU (Least Recently Used): 移除最久未使用的
// - LFU (Least Frequently Used): 移除使用最少的
// - FIFO (First In First Out): 移除最舊的計畫
```

---

## 8. 常見問題和解決方案

### 問題 1: 記憶體持續增長

**症狀**:

```
時間過程中記憶體持續增長，未見平台化
RSS: 500MB → 1GB → 2GB ...
```

**原因**:

- EvictionThreshold 未配置或設為 0
- 查詢模式數過多（每個新模式都創建新計畫）
- CleanupInterval 為 0（驅逐規則未執行）

**解決方案**:

```yaml
# 配置文件
planner:
  evictionThreshold: 30m
  cleanupInterval: 5m
# 重啟 OpenFGA
```

### 問題 2: Planner 總是選擇次優策略

**症狀**:

```
預期選擇 weight2（20ms），但持續選擇 default（50ms）
```

**原因**:

- EvictionThreshold 過短，計畫被頻繁驅逐
- 無法完成學習週期

**解決方案**:

```yaml
# 增加驅逐阈值以完成學習
planner:
  evictionThreshold: 60m # 從 30m 增加到 60m
  cleanupInterval: 5m
```

### 問題 3: Cleanup 線程 CPU 使用率高

**症狀**:

```
後臺 cleanup 程序消耗大量 CPU
```

**原因**:

- CleanupInterval 過短（如 10 秒）
- 計畫總數非常多（百萬級）

**解決方案**:

```yaml
# 減少清理頻率
planner:
  evictionThreshold: 30m
  cleanupInterval: 10m # 從 1m 增加到 10m
```

### 問題 4: 記憶體波動（鋸齒形）

**症狀**:

```
記憶體: 100MB → 200MB → 100MB → 200MB ...（循環）
```

**原因**:

- EvictionThreshold 和 CleanupInterval 組合不合理
- 導致大量計畫同時失效和驅逐

**解決方案**:

```yaml
# 調整為合理比例（驅逐閾值 >= 3 × 清理間隔）
planner:
  evictionThreshold: 30m # 30 分鐘
  cleanupInterval: 10m # 10 分鐘（3:1 比例）
```

---

## 9. 最佳實踐總結

✅ **應該做**:

1. **配置驅逐機制**

   ```yaml
   planner:
     evictionThreshold: 30m
     cleanupInterval: 5m
   ```

2. **定期監控記憶體**

   - 使用 pprof 或系統監控工具
   - 追蹤 heap 和 RSS 記憶體

3. **根據環境調整**

   - 開發: 禁用驅逐（最大化學習）
   - 生產: 啟用驅逐（平衡效能和記憶體）

4. **在高負載測試中驗證**
   - 長期運行測試以觀察記憶體趨勢
   - 確認驅逐機制正常工作

❌ **不應該做**:

1. **使用預設的零配置（生產環境）**

   ```yaml
   # 不推薦，會無限增長
   planner:
     evictionThreshold: 0
     cleanupInterval: 0
   ```

2. **只配置驅逐閾值，不配置清理間隔**

   ```yaml
   # 不推薦，驅逐規則無法執行
   planner:
     evictionThreshold: 30m
     cleanupInterval: 0 # 這樣不行！
   ```

3. **設定過於激進的驅逐**

   ```yaml
   # 不推薦，無法完成學習
   planner:
     evictionThreshold: 1m # 太短
     cleanupInterval: 10s # 太頻繁
   ```

4. **忽略 CleanupInterval 的 CPU 成本**
   - 在計畫非常多時，清理可能成為瓶頸
   - 根據實際情況調整頻率

---

## 10. 快速參考表

### 配置速查

| 環境       | EvictionThreshold | CleanupInterval | 記憶體估算 | 學習質量 |
| ---------- | ----------------- | --------------- | ---------- | -------- |
| 開發       | 0                 | 0               | 高         | 最優     |
| 中小型生產 | 30m               | 5m              | 低-中      | 良好     |
| 大型生產   | 15m               | 3m              | 低         | 中等     |
| 記憶體受限 | 10m               | 1m              | 很低       | 有限     |

### 啟用方式速查

```bash
# 命令行
openfga run --planner-eviction-threshold=30m --planner-cleanup-interval=5m

# 環境變數
export OPENFGA_PLANNER_EVICTION_THRESHOLD=30m
export OPENFGA_PLANNER_CLEANUP_INTERVAL=5m

# 配置文件
# config.yaml
planner:
  evictionThreshold: 30m
  cleanupInterval: 5m
```

---

## 11. 相關源代碼

| 檔案                          | 功能                                |
| ----------------------------- | ----------------------------------- |
| `internal/planner/planner.go` | Planner 主體，evictStaleKeys() 實現 |
| `internal/planner/plan.go`    | keyPlan 定義                        |
| `pkg/server/config/config.go` | PlannerConfig 定義，預設值          |
| `cmd/run/run.go`              | 命令行標誌定義，Planner 初始化      |
| `cmd/run/flags.go`            | 標誌綁定到環境變數                  |
