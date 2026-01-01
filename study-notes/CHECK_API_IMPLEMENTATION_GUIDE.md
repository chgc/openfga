# OpenFGA Check API 實現原理與規則詳解

## 概述

OpenFGA 的 `Check API` 是用於檢查使用者/主體與物件之間是否存在特定關係的核心 API。它透過在授權關係圖（有向圖，可能包含環）上進行遍歷來確定使用者是否擁有某個特定權限。

**核心問題**: `Check(object#relation@user)` - 使用者是否擁有該物件的該關係？

---

## 1. Check API 的執行流程與 SQL 命令

### 1.1 高層工作流

```
HTTP Request
    ↓
Server#Check() - [檢查授權、驗證]
    ↓
resolveTypesystem() - [SQL: SELECT FROM authorization_model]
    ↓
CheckCommand#Execute() - [包裝 contextual tuples]
    ↓
LocalChecker#ResolveCheck() - [遞迴圖遍歷]
    ↓
checkDirect / checkTTU / checkComputedUserset
    ↓
[SQL: SELECT FROM tuple] - 多種查詢模式
    ↓
返回 {allowed: true/false}
```

### 1.2 詳細步驟分解與 SQL 命令

#### 步驟 1: API 入口點（[pkg/server/check.go](pkg/server/check.go#L28)）

```go
func (s *Server) Check(ctx context.Context, req *openfgav1.CheckRequest)
    (*openfgav1.CheckResponse, error)
```

**動作與 SQL 命令：**

1. **驗證請求格式** - 無 SQL
   - 檢查 StoreID、TupleKey 格式
   - 驗證 user、object、relation 是否符合規範

2. **授權檢查** - 可能有 SQL（如果啟用 Access Control）
   - `s.checkAuthz()` 檢查調用者是否有權限執行 Check

3. **解析授權模型** - **SQL #1**
   ```go
   typesys, err := s.resolveTypesystem(ctx, storeID, req.GetAuthorizationModelId())
   ```
   
   執行 SQL:
   ```sql
   -- 如果指定 modelID
   SELECT authorization_model_id, schema_version, serialized_protobuf
   FROM authorization_model
   WHERE store = ? AND authorization_model_id = ?
   
   -- 如果未指定 modelID（使用最新版本）
   SELECT authorization_model_id, schema_version, serialized_protobuf
   FROM authorization_model
   WHERE store = ?
   ORDER BY authorization_model_id DESC
   LIMIT 1
   ```
   
   **目的**: 獲取授權模型定義，包含所有 type、relation、rewrite 規則

4. **構建 CheckResolver** - 無 SQL
   - 創建 LocalChecker（核心解析器）
   - 添加 CachedCheckResolver（查詢結果快取）
   - 添加 DispatchThrottlingResolver（限流）
   - 添加 ShadowResolver（實驗性功能）

5. **創建 CheckCommand** - 無 SQL
   - 設置並發限制、快取配置、throttling 參數

#### 步驟 2: 命令執行（[pkg/server/commands/check_command.go](pkg/server/commands/check_command.go#L105)）

```go
func (c *CheckQuery) Execute(ctx context.Context, params *CheckCommandParams)
    (*graph.ResolveCheckResponse, *graph.ResolveCheckRequestMetadata, error)
```

**動作：**

1. **驗證請求** - 無 SQL
   - 驗證 TupleKey 和 ContextualTuples 是否符合授權模型

2. **創建 RequestStorageWrapper** - 無 SQL
   - 包裝 datastore，加入 contextual tuples 的內存快取
   - 設置並發控制和 throttling

3. **調用 CheckResolver** - 後續會有 SQL
   ```go
   resp, err := c.checkResolver.ResolveCheck(ctx, resolveCheckRequest)
   ```

#### 步驟 3: 核心遞迴演算法（[internal/graph/check.go](internal/graph/check.go#L391)）

```go
func (c *LocalChecker) ResolveCheck(
    ctx context.Context,
    req *ResolveCheckRequest
) (*ResolveCheckResponse, error)
```

**動作：**

1. **深度檢查** - 無 SQL
   - 確保未超過最大解析深度（預設 25）
   - 防止遞迴過深

2. **環檢測** - 無 SQL
   - 檢查是否存在循環依賴
   - 使用 `VisitedPaths` map 追蹤已訪問的路徑

3. **自訂規則檢查** - 無 SQL
   - 如果是自訂定義的關係（如 `user:alice` vs `user:alice`），直接返回 true

4. **型別驗證** - 無 SQL
   - 從 TypeSystem 確認關係在授權模型中存在

5. **路徑分析** - 無 SQL
   - 檢查是否存在從使用者到關係的路徑
   - 使用 TypeSystem 的圖結構分析

6. **關係重寫解析** - **會觸發 SQL**
   ```go
   resp, err := c.CheckRewrite(ctx, req, rel.GetRewrite())(ctx)
   ```

#### 步驟 4: 關係重寫檢查（會執行不同的 SQL 查詢）

根據授權模型中定義的 rewrite 規則，會執行不同的檢查邏輯和 SQL 查詢：

---

## 2. 關係重寫（Relation Rewrite）機制與 SQL 命令

OpenFGA 支援四種主要的關係重寫方式，每種都會執行不同的 SQL 查詢：

### 2.1 直接關係（Direct Relationship）- **SQL #2, #3, #4**

**定義**: `define viewer: [user, group#member]`

最簡單的形式，直接在資料庫中查詢是否存在該關係的元組。

**執行流程與 SQL**:

```
checkDirect() - [internal/graph/check.go#L757]
├── checkDirectUserTuple() - [SQL #2]
│   └── storage.ReadUserTuple()
│       執行: SELECT object_type, object_id, relation, 
│                    user_object_type, user_object_id, user_relation,
│                    condition_name, condition_context
│             FROM tuple
│             WHERE store = ?
│               AND object_type = ?
│               AND object_id = ?
│               AND relation = ?
│               AND user_object_type = ?
│               AND user_object_id = ?
│               AND user_relation = ?
│               AND user_type = ?
│
├── checkPublicAssignable() - [SQL #3]
│   └── storage.ReadUsersetTuples()
│       執行: SELECT store, object_type, object_id, relation,
│                    user_object_type, user_object_id, user_relation,
│                    condition_name, condition_context, ulid, inserted_at
│             FROM tuple
│             WHERE store = ?
│               AND user_type = 'userset'
│               AND object_type = ?
│               AND object_id = ?
│               AND relation = ?
│               AND user_object_type = ?  -- 萬用字元類型
│               AND user_object_id = '*'  -- 萬用字元標記
│
└── checkDirectUsersetTuples() - [SQL #4]
    └── storage.ReadUsersetTuples()
        執行: SELECT store, object_type, object_id, relation,
                     user_object_type, user_object_id, user_relation,
                     condition_name, condition_context, ulid, inserted_at
              FROM tuple
              WHERE store = ?
                AND user_type = 'userset'
                AND object_type = ?
                AND object_id = ?
                AND relation = ?
                AND (user_object_type = ? AND user_relation = ? OR ...)
```

**範例**:
- 請求: `Check(document:doc1#viewer@user:alice)`
- SQL #2 查詢: 是否存在 `document:doc1#viewer@user:alice`
- SQL #3 查詢: 是否存在 `document:doc1#viewer@user:*`（公開訪問）
- SQL #4 查詢: 是否存在 `document:doc1#viewer@group:eng#member`（userset 關係）

**代碼位置**:
- [pkg/storage/sqlite/sqlite.go#L687](pkg/storage/sqlite/sqlite.go#L687) - ReadUserTuple
- [pkg/storage/sqlite/sqlite.go#L753](pkg/storage/sqlite/sqlite.go#L753) - ReadUsersetTuples

### 2.2 計算關係（Computed Userset）- **遞迴調用，無額外 SQL**

**定義**: `define viewer: editor`

一種間接的關係定義，透過重寫為另一個關係來實現。

**執行流程**:

```
checkComputedUserset(document:1#viewer@user:jon) - [internal/graph/check.go#L828]
    ↓ (無 SQL，只改寫 tuple key)
改寫元組鑰匙為: document:1#editor@user:jon
    ↓
ResolveCheck(document:1#editor@user:jon)  // 遞迴呼叫，會觸發新的 SQL
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
  → 遞迴解析 editor 關係（會執行 SQL #2-#4）
```

**特點**: 
- 本身不執行 SQL，只是改寫請求
- 遞迴調用會根據目標關係的定義執行相應的 SQL

### 2.3 元組到用戶集（Tuple to Userset, TTU）- **SQL #5**

**定義**: `define viewer: viewer from parent`

用於建立物件間的層次關係。一個物件可以從其父物件繼承權限。

**關鍵約束**:
- 元組集關係（tupleset）必須是直接關係，不能是計算關係
- 元組集關係只能指向直接物件型別（如 `[folder]`），不能是使用者集（如 `[group#member]`）

**執行流程與 SQL**:

```
checkTTU(document:1#viewer@user:jon) - [internal/graph/check.go#L838]
    ↓ [SQL #5]
storage.Read() 查詢 tupleset 關係
執行: SELECT store, object_type, object_id, relation,
             user_object_type, user_object_id, user_relation,
             condition_name, condition_context, ulid, inserted_at
      FROM tuple
      WHERE store = ?
        AND object_type = 'document'
        AND object_id = '1'
        AND relation = 'parent'
    ↓  獲得: [folder:x, folder:y]
Union 並行執行:
  ├── dispatch → ResolveCheck(folder:x#viewer@user:jon)  // 遞迴，觸發新的 SQL
  └── dispatch → ResolveCheck(folder:y#viewer@user:jon)  // 遞迴，觸發新的 SQL
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
  1. [SQL #5] 查詢 document:1 的所有 parent → [folder:x, folder:y]
  2. dispatch Check(folder:x#viewer@user:jon) → [SQL #2] → {allowed: true} ✓
  3. dispatch Check(folder:y#viewer@user:jon) → [SQL #2] → {allowed: false}
  Result: {allowed: true}
```

**代碼位置**:
- [internal/graph/check.go#L838](internal/graph/check.go#L838) - checkTTU
- [pkg/storage/sqlite/sqlite.go#L158](pkg/storage/sqlite/sqlite.go#L158) - Read (用於查詢 tupleset)

### 2.4 集合操作（Set Operations）- **組合多個 SQL 結果**

#### Union（或 - OR）- **並行執行多個 SQL，短路返回**

**定義**: `define viewer: [user] or editor`

如果**任何**一個條件為真，則整體為真。

**執行邏輯與 SQL**:

```go
func union(ctx context.Context, handlers ...CheckHandlerFunc) {
    // 並行執行所有 handlers
    // 第一個返回 true 的立即返回 true（短路）
    // 所有都是 false 則返回 false
}
```

**呼叫堆棧示例**:

```
Check(document:1#viewer@user:jon)  // viewer: [user] or editor
├── union (並行執行)
│   ├── checkDirect(document:1#viewer@user:jon)     
│   │   → [SQL #2] 查詢直接關係 → {allowed: true} ✓ 短路返回
│   └── checkComputedUserset(document:1#editor@user:jon) 
│       → (不會執行，因為第一個已經返回 true)
Result: {allowed: true}
```

**特點**:
- 並行執行所有分支的 SQL 查詢
- 任一分支返回 true 立即短路，取消其他查詢
- 只有所有分支都返回 false 才返回 false

#### Intersection（與 - AND）- **並行執行多個 SQL，任一 false 短路**

**定義**: `define access: permission and active`

需要**所有**條件都為真。

**執行邏輯與 SQL**:

```go
func intersection(ctx context.Context, handlers ...CheckHandlerFunc) {
    // 並行執行所有 handlers
    // 任何一個為 false，立即返回 false（短路）
    // 需要全部為 true
}
```

**特性**:
- 並行執行所有分支的 SQL 查詢
- 任一分支返回 false 立即短路，取消其他查詢
- 錯誤被吞併，除非有明確的 false 結果
- 全部為 true 或全部有錯時才返回 true/error

#### Exclusion（排除 - DIFFERENCE）- **並行執行兩個 SQL，條件短路**

**定義**: `define allowed: permission but not blacklist`

基礎條件為真**且**排除條件為假。

**執行邏輯與 SQL**:

```go
func exclusion(ctx context.Context, handlers ...CheckHandlerFunc) {
    // handlers[0] = 基礎條件
    // handlers[1] = 排除條件
    // 並行執行

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
  1. 並行執行:
     a) 基礎條件: Check(document:1#viewer or editor@user:jon) → [SQL #2-#4]
     b) 排除條件: Check(document:1#blocked@user:jon) → [SQL #2]

  如果基礎為 true 且排除為 false → {allowed: true}
  如果基礎為 true 且排除為 true  → {allowed: false} (短路)
  如果基礎為 false              → {allowed: false} (短路)
```

**代碼位置**:
- [internal/graph/check.go#L175](internal/graph/check.go#L175) - union
- [internal/graph/check.go#L223](internal/graph/check.go#L223) - intersection
- [internal/graph/check.go#L276](internal/graph/check.go#L276) - exclusion

---

## 3. SQL 命令總結

Check API 執行過程中會觸發以下 SQL 命令：

### SQL #1: 讀取授權模型
```sql
SELECT authorization_model_id, schema_version, serialized_protobuf
FROM authorization_model
WHERE store = ? 
  AND authorization_model_id = ?  -- 如果指定
ORDER BY authorization_model_id DESC  -- 如果未指定，取最新
LIMIT 1
```
**執行時機**: 每個 Check 請求開始時
**執行次數**: 1 次（有快取）
**代碼位置**: [pkg/server/server.go#L942](pkg/server/server.go#L942)

### SQL #2: 檢查直接用戶關係
```sql
SELECT object_type, object_id, relation,
       user_object_type, user_object_id, user_relation,
       condition_name, condition_context
FROM tuple
WHERE store = ?
  AND object_type = ?
  AND object_id = ?
  AND relation = ?
  AND user_object_type = ?
  AND user_object_id = ?
  AND user_relation = ?
  AND user_type = ?
```
**執行時機**: checkDirectUserTuple - 檢查直接關係時
**執行次數**: 視關係定義和遞迴深度而定
**代碼位置**: [pkg/storage/sqlite/sqlite.go#L687](pkg/storage/sqlite/sqlite.go#L687)

### SQL #3: 檢查公開可訪問（萬用字元）
```sql
SELECT store, object_type, object_id, relation,
       user_object_type, user_object_id, user_relation,
       condition_name, condition_context, ulid, inserted_at
FROM tuple
WHERE store = ?
  AND user_type = 'userset'
  AND object_type = ?
  AND object_id = ?
  AND relation = ?
  AND user_object_type = ?
  AND user_object_id = '*'
```
**執行時機**: checkPublicAssignable - 檢查萬用字元關係時
**執行次數**: 視關係定義而定
**代碼位置**: [pkg/storage/sqlite/sqlite.go#L753](pkg/storage/sqlite/sqlite.go#L753)

### SQL #4: 檢查用戶集關係
```sql
SELECT store, object_type, object_id, relation,
       user_object_type, user_object_id, user_relation,
       condition_name, condition_context, ulid, inserted_at
FROM tuple
WHERE store = ?
  AND user_type = 'userset'
  AND object_type = ?
  AND object_id = ?
  AND relation = ?
  AND (user_object_type = ? AND user_relation = ? OR ...)
```
**執行時機**: checkDirectUsersetTuples - 檢查 userset 關係時
**執行次數**: 視關係定義和遞迴深度而定
**代碼位置**: [pkg/storage/sqlite/sqlite.go#L753](pkg/storage/sqlite/sqlite.go#L753)

### SQL #5: TTU 查詢元組集
```sql
SELECT store, object_type, object_id, relation,
       user_object_type, user_object_id, user_relation,
       condition_name, condition_context, ulid, inserted_at
FROM tuple
WHERE store = ?
  AND object_type = ?
  AND object_id = ?
  AND relation = ?  -- tupleset relation
```
**執行時機**: checkTTU - 查詢 TTU 的 tupleset 關係時
**執行次數**: 每個 TTU 定義 1 次，但會遞迴觸發更多查詢
**代碼位置**: [pkg/storage/sqlite/sqlite.go#L158](pkg/storage/sqlite/sqlite.go#L158)

### SQL #6: 從用戶開始查詢（ListObjects/ListUsers 場景）
```sql
SELECT store, object_type, object_id, relation,
       user_object_type, user_object_id, user_relation,
       condition_name, condition_context, ulid, inserted_at
FROM tuple
WHERE store = ?
  AND object_type = ?
  AND relation = ?
  AND (user_object_type = ? AND user_object_id = ? [AND user_relation = ?])
ORDER BY object_id
```
**執行時機**: ReadStartingWithUser - 反向查詢時使用
**執行次數**: 取決於查詢策略
**代碼位置**: [pkg/storage/sqlite/sqlite.go#L807](pkg/storage/sqlite/sqlite.go#L807)

### SQL 執行次數估算

一個簡單的 Check 請求：
- **最少**: 2 次（1 次模型 + 1 次直接關係查詢）
- **典型**: 3-10 次（包含遞迴和多個分支）
- **複雜**: 可能數十次（深層 TTU、多層嵌套、複雜 union/intersection）

範例分析：
```
Model:
  type folder
    relations
      define viewer: [user]
  type document
    relations
      define parent: [folder]
      define viewer: [user] or viewer from parent

Check(document:1#viewer@user:alice):
  SQL #1: 讀取模型 (1 次)
  SQL #2: 檢查 document:1#viewer@user:alice (1 次)
  SQL #5: 查詢 document:1#parent (1 次) → 返回 [folder:x]
  SQL #2: 檢查 folder:x#viewer@user:alice (1 次)
  總計: 4 次 SQL 查詢
```

---

## 4. 核心資料結構

### 4.1 ResolveCheckRequest

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

### 4.2 ResolveCheckResponse

```go
type ResolveCheckResponse struct {
    Allowed                 bool
    ResolutionMetadata      ResolveCheckResponseMetadata
}

type ResolveCheckResponseMetadata struct {
    DatastoreQueryCount     uint32  // 資料庫查詢次數
    DatastoreItemCount      uint32  // 返回的資料項數
    CycleDetected           bool    // 是否檢測到環
    Duration                time.Duration
}
```

---

## 5. 關鍵優化與效能特性

### 5.1 並行執行

```go
// Union 和 Intersection 中的所有子任務並行執行
pool := concurrency.NewPool(ctx, concurrencyLimit)
for _, handler := range handlers {
    pool.Go(func(ctx context.Context) error {
        result := handler(ctx)  // 並行執行 SQL 查詢
        return nil
    })
}
```

**優點**: 多個分支同時執行 SQL 查詢，減少總延遲

### 5.2 短路求值（Short-circuit Evaluation）

- **Union**: 找到第一個 true，立即返回 true，取消其他查詢
- **Intersection**: 找到第一個 false，立即返回 false，取消其他查詢
- **Exclusion**: base=false 或 subtract=true，立即返回 false

**優點**: 減少不必要的 SQL 查詢

### 5.3 環檢測（Cycle Detection）

```go
func (c *LocalChecker) hasCycle(req *ResolveCheckRequest) bool {
    key := tuple.TupleKeyToString(req.GetTupleKey())
    _, cycleDetected := req.VisitedPaths[key]
    if cycleDetected {
        return true  // 檢測到環，無需執行 SQL
    }
    req.VisitedPaths[key] = struct{}{}
    return false
}
```

當檢測到環時，返回 `{allowed: false, cycleDetected: true}`，無需執行 SQL。

### 5.4 深度限制（Resolution Depth Limit）

```go
if req.GetRequestMetadata().Depth == c.maxResolutionDepth {
    return nil, ErrResolutionDepthExceeded
}
```

防止無限遞迴和過多的 SQL 查詢，預設深度限制為 25。

### 5.5 快取機制

多層快取策略可減少 SQL 查詢：

1. **授權模型快取**: 避免重複查詢 authorization_model 表
2. **請求級快取**: 在單個 Check 請求內快取相同的子問題結果
3. **跨請求快取**: CachedCheckResolver 快取常見的查詢結果
4. **Contextual Tuples 快取**: 內存中快取臨時關係，無需查詢數據庫

### 5.6 資料存儲層優化

```go
// RequestStorageWrapper 提供：
// 1. Contextual tuples 的內存快取
// 2. 並發控制（maxConcurrentReads）
// 3. Throttling（限流保護數據庫）
datastoreWithTupleCache := storagewrappers.NewRequestStorageWrapperWithCache(
    c.datastore,
    params.ContextualTuples,     // 臨時關係
    &operation,                   // 並行設定
    configuration,                // 快取設定
)
```

---

## 6. 執行流程完整示例

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
