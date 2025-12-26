# OpenFGA Check API 實現原理與規則詳解

## 概述

OpenFGA 的 `Check API` 是用於檢查使用者/主體與物件之間是否存在特定關係的核心 API。它透過在授權關係圖（有向圖，可能包含環）上進行遍歷來確定使用者是否擁有某個特定權限。

**核心問題**: `Check(object#relation@user)` - 使用者是否擁有該物件的該關係？

---

## 1. Check API 的執行流程

### 1.1 高層工作流

```
HTTP Request
    ↓
Server#Check()
    ↓
驗證請求 + 解析授權模型
    ↓
CheckCommand#Execute()
    ↓
LocalChecker#ResolveCheck()（遞迴執行）
    ↓
返回 {allowed: true/false}
```

### 1.2 詳細步驟分解

#### 步驟 1: API 入口點（[pkg/server/check.go](pkg/server/check.go)）

```go
func (s *Server) Check(ctx context.Context, req *openfgav1.CheckRequest)
    (*openfgav1.CheckResponse, error)
```

主要工作：

- 構建 `CheckResolver`（包含快取、限流等層）
- 驗證請求
- 解析授權模型（TypeSystem）
- 建立 `CheckCommand` 實例
- 執行檢查並記錄指標

#### 步驟 2: 命令執行（[pkg/server/commands/check_command.go](pkg/server/commands/check_command.go)）

```go
func (c *CheckQuery) Execute(ctx context.Context, params *CheckCommandParams)
    (*graph.ResolveCheckResponse, error)
```

主要工作：

- 驗證 Check 請求的有效性
- 建立 `ResolveCheckRequest`（內部資料結構）
- 包裝資料存儲層（新增快取、條件過濾等）
- 呼叫 `CheckResolver.ResolveCheck()` 執行核心邏輯

#### 步驟 3: 核心遞迴演算法（[internal/graph/check.go](internal/graph/check.go)）

```go
func (c *LocalChecker) ResolveCheck(
    ctx context.Context,
    req *ResolveCheckRequest
) (*ResolveCheckResponse, error)
```

這是實現 Check 的核心方法。工作流程：

1. **深度檢查**: 確保未超過最大解析深度
2. **環檢測**: 檢查是否存在循環依賴
3. **自訂規則**: 如果是自訂定義的關係，直接返回 true
4. **型別驗證**: 確認關係在授權模型中存在
5. **路徑分析**: 檢查是否存在從使用者到關係的路徑
6. **關係重寫解析**: 根據關係的重寫規則執行 `CheckRewrite()`

---

## 2. 關係重寫（Relation Rewrite）機制

OpenFGA 支援四種主要的關係重寫方式：

### 2.1 直接關係（Direct Relationship）

**定義**: `define viewer: [user]`

最簡單的形式，直接在資料庫中查詢是否存在該關係的元組。

**執行流程**:

```
checkDirect()
├── checkDirectUserTuple()      // 查詢 object#relation@user
│   └── storage.ReadUserTuple()
├── checkPublicAssignable()     // 查詢 object#relation@user:*（萬用字元）
│   └── storage.ReadUsersetTuples()
└── checkDirectUsersetTuples()  // 查詢 object#relation@group#member
    └── storage.ReadUsersetTuples()
```

**例子**:

```
Model:
  type document
    relations
      define owner: [user]

Tuples:
  document:1#owner@user:jon

Check(document:1#owner@user:jon) → {allowed: true}
Check(document:1#owner@user:bob) → {allowed: false}
```

### 2.2 計算關係（Computed Userset）

**定義**: `define viewer: editor`

一種間接的關係定義，透過重寫為另一個關係來實現。`viewer` 關係完全由 `editor` 關係定義。

**執行流程**:

```
checkComputedUserset(document:1#viewer@user:jon)
    ↓
改寫元組鑰匙為: document:1#editor@user:jon
    ↓
ResolveCheck(document:1#editor@user:jon)  // 遞迴呼叫
```

**例子**:

```
Model:
  type document
    relations
      define owner: [user]
      define editor: [user] or owner
      define viewer: editor

Check(document:1#viewer@user:jon)
  → 改寫為: Check(document:1#editor@user:jon)
  → 繼續檢查 editor 的定義（包含 union）
```

### 2.3 層次關係（Tuple-to-Userset, TTU）

**定義**: `define viewer: viewer from parent`

用於建立物件間的層次關係。一個物件可以從其父物件繼承權限。

**關鍵約束**:

- 元組集關係（tupleset）必須是直接關係，不能是計算關係
- 元組集關係只能指向直接物件型別（如 `[folder]`），不能是使用者集（如 `[group#member]`）

**執行流程**:

```
checkTTU(document:1#viewer@user:jon, TTU={tupleset: parent, computed: viewer})
    ↓
查詢所有 document:1 的 parent 關係
    ↓  獲得: [folder:x, folder:y]
Union 並行執行:
  ├── ResolveCheck(folder:x#viewer@user:jon)  // 遞迴
  └── ResolveCheck(folder:y#viewer@user:jon)  // 遞迴
    ↓
如果任一返回 true，則整體為 true
```

**例子**:

```
Model:
  type folder
    relations
      define viewer: [user]

  type document
    relations
      define parent: [folder]
      define viewer: viewer from parent

Tuples:
  document:1#parent@folder:x
  document:1#parent@folder:y
  folder:x#viewer@user:jon
  folder:y#viewer@user:andres

Check(document:1#viewer@user:jon)
  1. 查詢 document:1 的所有 parent → [folder:x, folder:y]
  2. 檢查 folder:x#viewer@user:jon → {allowed: true} ✓
  3. 檢查 folder:y#viewer@user:jon → {allowed: false}
  Result: {allowed: true}
```

### 2.4 集合操作（Set Operations）

#### Union（或 - OR）

**定義**: `define viewer: [user] or editor`

如果**任何**一個條件為真，則整體為真。

**執行邏輯**:

```go
func union(ctx context.Context, handlers ...CheckHandlerFunc) {
    // 並行執行所有 handlers
    // 第一個返回 true 的立即返回 true（短路）
    // 所有都是 false 則返回 false
}
```

**呼叫堆棧示例**:

```
Check(document:1#viewer@user:jon)
├── union (並行執行)
│   ├── checkDirect(document:1#viewer@user:jon)     → {allowed: true} ✓ 短路返回
│   └── checkComputedUserset(document:1#editor@user:jon) → (不會執行)
Result: {allowed: true}
```

#### Intersection（與 - AND）

**定義**: `define access: permission and active`

需要**所有**條件都為真。

**執行邏輯**:

```go
func intersection(ctx context.Context, handlers ...CheckHandlerFunc) {
    // 並行執行所有 handlers
    // 任何一個為 false，立即返回 false（短路）
    // 需要全部為 true
}
```

**特性**:

- 如果發現任何 false，立即返回 false
- 錯誤被吞併，除非有明確的 false 結果
- 全部為 true 或全部有錯時才返回 true/error

#### Exclusion（排除 - DIFFERENCE）

**定義**: `define allowed: permission but not blacklist`

基礎條件為真**且**排除條件為假。

**執行邏輯**:

```go
func exclusion(ctx context.Context, handlers ...CheckHandlerFunc) {
    // handlers[0] = 基礎條件
    // handlers[1] = 排除條件

    // 如果 base 為 false → false（短路）
    // 如果 subtract 為 true → false（短路）
    // 否則 → true
}
```

**例子**:

```
Model:
  type document
    relations
      define viewer: [user] or editor but not blocked
      define blocked: [user]
      define editor: [user]

Check(document:1#viewer@user:jon)
  1. 基礎條件: Check(document:1#viewer or editor@user:jon)
  2. 排除條件: Check(document:1#blocked@user:jon)

  如果基礎為 true 且排除為 false → {allowed: true}
  如果基礎為 true 且排除為 true  → {allowed: false}
  如果基礎為 false              → {allowed: false}
```

---

## 3. 核心資料結構與流程

### 3.1 ResolveCheckRequest

```go
type ResolveCheckRequest struct {
    StoreID                  string                    // 存儲 ID
    TupleKey                 *openfgav1.TupleKey      // 目前要檢查的 object#relation@user
    ContextualTuples         []*openfgav1.TupleKey    // 上下文中的臨時關係
    Context                  *structpb.Struct         // 條件上下文（用於 ABAC）
    Consistency              openfgav1.ConsistencyPreference
    AuthorizationModelID     string
    RequestMetadata          *ResolveCheckRequestMetadata
    VisitedPaths             map[string]struct{}      // 用於環檢測
}
```

### 3.2 ResolveCheckResponse

```go
type ResolveCheckResponse struct {
    Allowed                 bool
    ResolutionMetadata      ResolveCheckResponseMetadata
}

type ResolveCheckResponseMetadata struct {
    DatastoreQueryCount     uint32  // 資料庫查詢次數
    DatastoreItemCount      uint32  // 返回的資料項數
    CycleDetected           bool    // 是否檢測到環
}
```

---

## 4. 關鍵優化與效能特性

### 4.1 並行執行

```go
// Union 和 Intersection 中的所有子任務並行執行
pool := concurrency.NewPool(ctx, concurrencyLimit)
for _, handler := range handlers {
    pool.Go(func(ctx context.Context) error {
        result := handler(ctx)  // 並行執行
        return nil
    })
}
```

### 4.2 短路求值（Short-circuit Evaluation）

- **Union**: 找到第一個 true，立即返回 true
- **Intersection**: 找到第一個 false，立即返回 false
- **Exclusion**: base=false 或 subtract=true，立即返回 false

### 4.3 環檢測（Cycle Detection）

```go
func (c *LocalChecker) hasCycle(req *ResolveCheckRequest) bool {
    key := tuple.TupleKeyToString(req.GetTupleKey())
    _, cycleDetected := req.VisitedPaths[key]
    if cycleDetected {
        return true  // 檢測到環
    }
    req.VisitedPaths[key] = struct{}{}
    return false
}
```

當檢測到環時，返回 `{allowed: false, cycleDetected: true}`。

### 4.4 深度限制（Resolution Depth Limit）

```go
if req.GetRequestMetadata().Depth == c.maxResolutionDepth {
    return nil, ErrResolutionDepthExceeded
}
```

防止無限遞迴，預設深度限制可透過設定調整。

### 4.5 快取機制

多層快取策略：

1. **請求級快取**: 在單個 Check 請求內快取相同的子問題
2. **跨請求快取**: 快取常見的查詢結果
3. **條件過濾**: 支援基於 ABAC 條件的快取無效化

### 4.6 資料存儲層優化

```go
// 請求級存儲包裝器，包含：
datastoreWithTupleCache := storagewrappers.NewRequestStorageWrapperWithCache(
    c.datastore,
    params.ContextualTuples,     // 臨時關係
    &operation,                   // 並行設定
    configuration,                // 快取設定
)
```

---

## 5. 執行流程完整示例

### 示例：複雜關係檢查

**模型定義**:

```
type user

type folder
  relations
    define viewer: [user]

type document
  relations
    define parent: [folder]
    define owner: [user]
    define editor: [user] or owner
    define viewer: editor or viewer from parent
```

**資料**:

```
document:1#owner@user:alice
document:1#parent@folder:x
folder:x#viewer@user:bob
```

**查詢**: `Check(document:1#viewer@user:bob)`

**執行過程**:

```
1. Server#Check(document:1#viewer@user:bob)
   ├─ 驗證請求
   ├─ 解析授權模型
   └─ 建立 CheckCommand

2. CheckCommand#Execute()
   └─ CheckResolver#ResolveCheck(document:1#viewer@user:bob)

3. LocalChecker#ResolveCheck(document:1#viewer@user:bob)
   ├─ 深度檢查: depth=0, OK
   ├─ 環檢測: 無環
   ├─ 路徑檢查: viewer → bob 路徑存在
   └─ CheckRewrite(document:1#viewer, rewrite=editor or viewer from parent)

4. CheckRewrite 分發到 Union：
   Union(
       checkComputedUserset(document:1#editor@user:bob),  // 分支1
       checkTTU(document:1#viewer@user:bob)               // 分支2
   ) - 並行執行

   分支1: checkComputedUserset(document:1#editor@user:bob)
   └─ ResolveCheck(document:1#editor@user:bob)  // 遞迴
      ├─ Union(
      │   checkDirect(document:1#editor@user:bob),      // 結果: false
      │   checkComputedUserset(document:1#owner@user:bob) // 結果: false
      │ )
      └─ 返回 {allowed: false}

   分支2: checkTTU(document:1#viewer@user:bob)
   ├─ 查詢 document:1#parent → [folder:x]
   ├─ Union: ResolveCheck(folder:x#viewer@user:bob)
   │  └─ checkDirect(folder:x#viewer@user:bob)
   │     └─ storage.ReadUserTuple() → [folder:x#viewer@user:bob]
   │     └─ 返回 {allowed: true} ✓
   └─ 返回 {allowed: true}

5. Union 匯聚結果:
   分支1 = false
   分支2 = true
   ┗━ 返回 {allowed: true} ✓ （短路返回）

6. Server 返回 CheckResponse{Allowed: true}
```

**效能指標**:

- Dispatch 計數: 2 次（document#parent 和 folder#viewer）
- 資料庫查詢: 3 次
- 並行執行: 2 個分支

---

## 6. 重要規則與限制

### 6.1 TTU 元組集關係約束

❌ **無效** - 元組集不能是使用者集:

```
define parent: [folder#viewer]  // 不允許
```

❌ **無效** - 元組集不能是計算關係:

```
define owner: [folder]
define parent: owner            // 不允許
define viewer: viewer from parent
```

✅ **有效**:

```
define parent: [folder]         // 直接關係
define viewer: viewer from parent
```

### 6.2 一致性選項

```
ConsistencyPreference_CONSISTENCY_UNSPECIFIED  // 預設，較低一致性
ConsistencyPreference_HIGHER_CONSISTENCY       // 強一致性，可能更慢
```

### 6.3 上下文關係（Contextual Tuples）

允許在單個請求中臨時新增關係，用於假設檢查：

```go
req := &CheckRequest{
    TupleKey: ...,
    ContextualTuples: &ContextualTupleKeys{
        TupleKeys: []*TupleKey{
            {Object: "folder:x", Relation: "viewer", User: "user:bob"},
        },
    },
}
```

### 6.4 ABAC 條件

支援基於屬性的存取控制條件：

```
define viewer: [user] with grant=true
```

條件在 CheckRewrite 中由 `checkutil.BuildTupleKeyConditionFilter()` 評估。

---

## 7. 錯誤處理與除錯

### 7.1 常見錯誤

```go
ErrResolutionDepthExceeded     // 超過最大遞迴深度
ErrUnknownSetOperator         // 未知的集合操作符
ErrCycleDetected              // 檢測到循環關係
```

### 7.2 指標和追蹤

```
dispatchCountHistogram        // Dispatch 次數
datastoreQueryCountHistogram  // 資料庫查詢次數
datastoreItemCountHistogram   // 返回資料項數
requestDurationHistogram      // 請求耗時
```

透過 OpenTelemetry 和 Prometheus 監控。

### 7.3 除錯建議

1. 啟用 `ExperimentalCheckOptimizations` 特性旗標來觀察優化效果
2. 檢查 `CycleDetected` 旗標以識別關係模型中的問題
3. 監視 `DispatchCount` 以識別潛在的效能問題
4. 使用 contextual tuples 進行假設分析

---

## 8. 核心檔案對映

| 檔案                                                                         | 功能                             |
| ---------------------------------------------------------------------------- | -------------------------------- |
| [pkg/server/check.go](pkg/server/check.go)                                   | API 入口點，處理請求驗證和指標   |
| [pkg/server/commands/check_command.go](pkg/server/commands/check_command.go) | 命令執行器，編排資料流           |
| [internal/graph/check.go](internal/graph/check.go)                           | 核心演算法實現，包含所有重寫邏輯 |
| [pkg/storage/](pkg/storage/)                                                 | 存儲層介面和包裝器               |
| [pkg/typesystem/](pkg/typesystem/)                                           | 授權模型解析和驗證               |
| [tests/check/](tests/check/)                                                 | 整合測試和測試用例               |
| [docs/check/](docs/check/)                                                   | 詳細文件                         |

---

## 9. 快速參考

### Check 流程總結

```
請求 → 驗證 → 解析模型 → 建立 CheckResolver
  ↓
執行 ResolveCheck（遞迴）
  ├─ 型別/路徑驗證
  ├─ 直接關係查詢
  ├─ 計算關係重寫
  ├─ TTU 層次展開
  ├─ Union/Intersection/Exclusion 集合操作
  └─ 並行執行 + 短路求值
  ↓
返回 {allowed: true/false, metadata}
```

### 關鍵特性

- ✅ 支援遞迴關係定義
- ✅ 並行執行子問題
- ✅ 環檢測和深度限制
- ✅ 靈活的集合操作（並、交、差）
- ✅ 支援條件和上下文關係
- ✅ 多層快取和優化
- ✅ 詳細的效能指標
