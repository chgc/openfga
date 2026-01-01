# OpenFGA Authorization Model 最佳實踐指南

## 概述

本文檔基於 OpenFGA Check API 的實現原理和 SQL 執行特性，提供授權模型設計的最佳實踐建議。遵循這些原則可以幫助你設計出高效能、易維護、可擴展的授權模型。

**核心原則**: 好的授權模型應該在滿足業務需求的同時，最小化 Check 請求的 SQL 查詢次數和遞迴深度。

---

## 目錄

1. [模型設計基本原則](#1-模型設計基本原則)
2. [性能優化策略](#2-性能優化策略)
3. [關係定義最佳實踐](#3-關係定義最佳實踐)
4. [常見設計模式](#4-常見設計模式)
5. [常見陷阱與反模式](#5-常見陷阱與反模式)
6. [進階優化技巧](#6-進階優化技巧)
7. [模型演化與遷移](#7-模型演化與遷移)

---

## 1. 模型設計基本原則

### 1.1 最小化遞迴深度

**原則**: 將關係定義的層級保持在最少，避免過深的遞迴調用。

**為什麼**: 
- 每層遞迴都會觸發新的 SQL 查詢
- 預設深度限制為 25 層，過深會導致錯誤
- 深度越深，延遲越高

**❌ 不良範例**:
```dsl
type organization
  relations
    define member: [user]

type team
  relations
    define parent_org: [organization]
    define member: member from parent_org

type project
  relations
    define parent_team: [team]
    define member: member from parent_team

type document
  relations
    define parent_project: [project]
    define viewer: member from parent_project  # 4 層深度！
```

**✅ 良好範例**:
```dsl
type organization
  relations
    define member: [user]

type document
  relations
    define org: [organization]
    define viewer: [user] or member from org  # 只有 2 層深度
```

**SQL 查詢對比**:
- 不良設計: 可能需要 6+ 次查詢 (model + 4 層 TTU 查詢)
- 良好設計: 只需 3-4 次查詢 (model + direct + TTU)

---

### 1.2 優先使用直接關係

**原則**: 能用直接關係就不用計算關係或 TTU。

**為什麼**: 
- 直接關係查詢最快 (單次 SQL `SELECT ... WHERE` 精確匹配)
- 計算關係和 TTU 會增加遞迴層級
- 直接關係可以充分利用數據庫索引

**❌ 不良範例**:
```dsl
type document
  relations
    define owner: [user]
    define admin: owner  # 不必要的計算關係
    define can_delete: admin
```

**✅ 良好範例**:
```dsl
type document
  relations
    define owner: [user]
    define can_delete: owner  # 直接引用
```

**SQL 影響**:
```
不良設計 Check(document:1#can_delete@user:alice):
  SQL #1: 讀取模型
  SQL #2: 遞迴到 admin
  SQL #3: 遞迴到 owner
  SQL #4: 查詢 owner 關係
  總計: 4 次

良好設計 Check(document:1#can_delete@user:alice):
  SQL #1: 讀取模型
  SQL #2: 遞迴到 owner
  SQL #3: 查詢 owner 關係
  總計: 3 次
```

---

### 1.3 合理使用 Union（OR）避免過度使用

**原則**: Union 會並行執行所有分支，但過多分支會增加數據庫負載。

**為什麼**: 
- 每個 Union 分支都會執行獨立的 SQL 查詢
- 雖然並行執行，但數據庫連接和資源有限
- 過多分支會導致連接池耗盡

**❌ 不良範例**:
```dsl
type document
  relations
    define owner: [user]
    define editor: [user]
    define contributor: [user]
    define reviewer: [user]
    define commenter: [user]
    # 7 個並行 SQL 查詢！
    define viewer: owner or editor or contributor or reviewer or commenter or [user] or [user:*]
```

**✅ 良好範例**:
```dsl
type document
  relations
    define owner: [user]
    define editor: [user] or owner
    define contributor: [user] or editor
    # 使用層級繼承減少並行查詢
    define viewer: [user] or contributor
```

**優化建議**:
- Union 分支控制在 3-5 個以內
- 使用層級繼承代替平行 Union
- 考慮合併相似的關係

---

### 1.4 謹慎使用 Intersection（AND）

**原則**: Intersection 必須等待所有條件完成，是最慢的集合操作。

**為什麼**: 
- 所有分支必須都返回 true
- 無法短路優化（必須等所有查詢完成）
- 每個分支都是獨立的 SQL 查詢

**❌ 不良範例**:
```dsl
type document
  relations
    define org_member: [user] or member from org
    define team_member: [user] or member from team
    define project_member: [user] or member from project
    # 必須檢查所有 3 個複雜條件！
    define viewer: org_member and team_member and project_member
```

**✅ 良好範例**:
```dsl
type document
  relations
    define owner: [user]
    define active: [user]  # 簡單的直接關係
    define viewer: owner and active  # 一個複雜 + 一個簡單
```

**優化策略**:
1. **將最可能失敗的條件放在前面** (雖然並行執行，但可以提早短路)
2. **將最簡單的檢查放在前面** (快速失敗)
3. **避免多個 TTU 在 Intersection 中**

**SQL 查詢分析**:
```
Check(document:1#viewer@user:alice)  # viewer: owner and active

並行執行:
  分支 1: checkDirect(document:1#owner@user:alice) → SQL #2
  分支 2: checkDirect(document:1#active@user:alice) → SQL #2

如果任一返回 false，立即返回 false
兩者都為 true 才返回 true
```

---

### 1.5 限制 TTU 的鏈式使用

**原則**: 避免 TTU 套 TTU，每個 TTU 都會增加一層查詢和遞迴。

**為什麼**: 
- 每個 TTU 需要先查詢 tupleset 關係 (SQL)
- 然後對每個結果執行遞迴 Check (更多 SQL)
- 鏈式 TTU 會導致指數級的查詢增長

**❌ 不良範例**:
```dsl
type organization
  relations
    define member: [user]

type department
  relations
    define org: [organization]
    define member: member from org  # TTU 第 1 層

type team
  relations
    define dept: [department]
    define member: member from dept  # TTU 第 2 層

type project
  relations
    define team: [team]
    define member: member from team  # TTU 第 3 層

type document
  relations
    define project: [project]
    define viewer: member from project  # TTU 第 4 層
```

**SQL 執行分析**:
```
Check(document:1#viewer@user:alice):
  1. SQL: 查詢 document:1 的 project
  2. 對每個 project，遞迴檢查 member
     3. SQL: 查詢 project:x 的 team
     4. 對每個 team，遞迴檢查 member
        5. SQL: 查詢 team:y 的 dept
        6. 對每個 dept，遞迴檢查 member
           7. SQL: 查詢 dept:z 的 org
           8. 對每個 org，遞迴檢查 member
              9. SQL: 查詢 org:w 的 member

如果每層有 2 個關係，可能需要 2^4 = 16 次查詢！
```

**✅ 良好範例 - 扁平化設計**:
```dsl
type organization
  relations
    define member: [user]

type document
  relations
    define org: [organization]
    define team: [team]  # 直接關聯，不通過層級
    define project: [project]
    # 只用一層 TTU
    define org_viewer: member from org
    define viewer: [user] or org_viewer
```

**✅ 良好範例 - 使用直接關係替代**:
```dsl
# 在寫入時展開關係
# 當 document 關聯到 project 時，自動寫入：
# document:1#viewer@user:alice (直接寫入所有有權限的用戶)
# 而不是依賴 TTU 遞迴查詢

type document
  relations
    define viewer: [user, group#member]  # 直接關係，查詢最快
```

**優化建議**:
- **TTU 深度限制在 1-2 層**
- **考慮在寫入時展開關係** (Write-time expansion)
- **使用定期的後台任務同步權限**

---

## 2. 性能優化策略

### 2.1 利用短路求值優化 Union

**原則**: 將最可能為 true 的條件放在 Union 的前面。

**為什麼**: 
- Union 找到第一個 true 就立即返回
- 前面的條件先執行並可能短路
- 減少不必要的 SQL 查詢

**❌ 次優範例**:
```dsl
type document
  relations
    define parent: [folder]
    define owner: [user]
    # parent 關係少見，但放在前面
    define viewer: viewer from parent or owner or [user]
```

**✅ 優化範例**:
```dsl
type document
  relations
    define parent: [folder]
    define owner: [user]
    # 直接關係最常見，放在最前面
    define viewer: [user] or owner or viewer from parent
```

**實際影響**:
```
次優設計:
  80% 的請求需要執行所有 3 個分支的 SQL
  
優化設計:
  如果 70% 的用戶有直接 viewer 關係
  → 70% 的請求只需 2 次 SQL (model + direct)
  → 平均 SQL 次數顯著減少
```

---

### 2.2 使用 Computed Userset 減少重複定義

**原則**: 當多個關係需要相同的權限邏輯時，使用 computed userset 復用。

**為什麼**: 
- 減少模型複雜度
- 統一權限邏輯
- 更容易維護

**❌ 不良範例**:
```dsl
type document
  relations
    define owner: [user]
    define editor: [user] or owner
    # 重複定義相同的邏輯
    define can_write: [user] or owner
    define can_delete: [user] or owner
    define can_share: [user] or owner
```

**✅ 良好範例**:
```dsl
type document
  relations
    define owner: [user]
    define editor: [user] or owner
    # 使用 computed userset 復用邏輯
    define can_write: editor
    define can_delete: owner
    define can_share: owner
```

**注意**: 雖然增加一層間接性，但模型更清晰，維護成本更低。

---

### 2.3 索引優化考量

**原則**: 設計模型時考慮數據庫索引的使用。

**為什麼**: 
- OpenFGA 的 SQL 查詢依賴複合索引
- 良好的關係設計可以充分利用索引
- 避免全表掃描

**數據庫索引結構**:
```sql
-- tuple 表的主要索引
CREATE INDEX idx_tuple_partial ON tuple (
    store, object_type, object_id, relation,
    user_object_type, user_object_id, user_relation, user_type
);
```

**✅ 索引友好的查詢模式**:
```dsl
type document
  relations
    # 這些查詢都能有效使用索引
    define owner: [user]              # 精確匹配所有索引列
    define editor: [user, group#member]  # 精確匹配
    define viewer: editor             # 通過遞迴最終使用索引
```

**⚠️ 索引不友好的模式**:
- 過度使用萬用字元 (wildcard) 關係
- 大量的 userset 關係沒有類型限制
- 不指定 object_type 的查詢

---

### 2.4 批量檢查優化

**原則**: 當需要檢查多個權限時，使用 BatchCheck API。

**為什麼**: 
- 共享授權模型查詢
- 共享連接池和快取
- 可能的查詢合併

**❌ 不良做法**:
```javascript
// 多次獨立調用 Check
const canRead = await client.check({object: 'doc:1', relation: 'viewer', user: 'user:alice'});
const canWrite = await client.check({object: 'doc:1', relation: 'editor', user: 'user:alice'});
const canDelete = await client.check({object: 'doc:1', relation: 'owner', user: 'user:alice'});

// 3 次獨立的模型查詢 + 各自的關係查詢
```

**✅ 良好做法**:
```javascript
// 使用 BatchCheck
const results = await client.batchCheck([
  {object: 'doc:1', relation: 'viewer', user: 'user:alice'},
  {object: 'doc:1', relation: 'editor', user: 'user:alice'},
  {object: 'doc:1', relation: 'owner', user: 'user:alice'}
]);

// 1 次模型查詢 + 優化的關係查詢
```

---

### 2.5 使用 Contextual Tuples 減少寫入

**原則**: 對於臨時或會話級的權限，使用 contextual tuples 而不是寫入數據庫。

**為什麼**: 
- 避免數據庫寫入開銷
- 不需要清理過期權限
- 在內存中直接檢查，更快

**使用場景**:
- 臨時分享鏈接
- 會話級權限
- 短期授權

**✅ 範例**:
```javascript
// 檢查時傳入臨時權限，不寫入數據庫
const result = await client.check({
  object: 'document:1',
  relation: 'viewer',
  user: 'user:alice',
  contextualTuples: [
    // 臨時授予的權限
    {object: 'document:1', relation: 'viewer', user: 'user:alice'}
  ]
});

// 這個臨時權限只在此次檢查中有效，無需寫入和清理
```

---

## 3. 關係定義最佳實踐

### 3.1 命名規範

**原則**: 使用清晰、一致的命名約定。

**推薦命名模式**:

```dsl
type document
  relations
    # 實體關係: 名詞
    define owner: [user]
    define parent: [folder]
    define org: [organization]
    
    # 角色: 名詞
    define editor: [user]
    define viewer: [user]
    define admin: [user]
    
    # 權限: can_* 或 動詞
    define can_read: viewer
    define can_write: editor
    define can_delete: owner
    define can_share: owner
```

**避免的命名**:
- 過於抽象: `relation1`, `perm`, `rel`
- 不一致: 混用 `can_read` 和 `reader`
- 過長: `can_read_and_write_and_delete_document`

---

### 3.2 用戶類型定義

**原則**: 明確定義可以被賦予關係的用戶類型。

**❌ 過於寬鬆**:
```dsl
type document
  relations
    # 任何類型都可以，難以維護
    define viewer: [user, group#member, team#member, org#member, role#assignee]
```

**✅ 精確定義**:
```dsl
type document
  relations
    # 只允許必要的類型
    define viewer: [user, group#member]
    # 通過組織關係間接授權
    define org: [organization]
    define org_viewer: member from org
    define effective_viewer: viewer or org_viewer
```

**優點**:
- 更容易理解和維護
- 更好的類型安全
- SQL 查詢更高效（減少 OR 條件）

---

### 3.3 萬用字元的使用

**原則**: 謹慎使用萬用字元 (wildcard)，只用於真正的公開訪問場景。

**為什麼**: 
- 萬用字元查詢需要額外的 SQL 檢查
- 可能導致安全問題
- 難以追蹤和審計

**✅ 適當使用**:
```dsl
type document
  relations
    define viewer: [user, user:*]  # 公開文檔
```

**使用時機**:
- 公開訪問的資源
- 所有認證用戶都可訪問的資源

**避免**:
- 將萬用字元作為默認權限
- 在敏感資源上使用萬用字元
- 過度依賴萬用字元做權限管理

---

### 3.4 條件關係 (ABAC) 的使用

**原則**: 條件關係很強大但有性能成本，適度使用。

**為什麼**: 
- 條件評估發生在應用層，不在數據庫層
- 每個可能匹配的 tuple 都需要評估條件
- 增加 CPU 使用和延遲

**✅ 適當使用**:
```dsl
type document
  relations
    define viewer: [user with valid_subscription]

# Check 時提供 context
{
  "user": "user:alice",
  "context": {
    "valid_subscription": true,
    "subscription_end_date": "2024-12-31"
  }
}
```

**使用建議**:
- 用於業務規則而非靜態權限
- 條件邏輯保持簡單
- 避免在高頻路徑使用複雜條件
- 考慮預計算條件並使用直接關係

**性能對比**:
```
無條件檢查:
  SQL 查詢 → 直接返回結果
  延遲: ~5ms

帶條件檢查:
  SQL 查詢 → 獲取候選 tuples → 逐個評估條件 → 返回結果
  延遲: ~15ms (如果有 10 個候選)
```

---

## 4. 常見設計模式

### 4.1 層級權限繼承模式

**場景**: 父對象的權限應該自動適用於子對象。

**模式**:
```dsl
type organization
  relations
    define member: [user]
    define admin: [user]

type folder
  relations
    define org: [organization]
    define owner: [user]
    # 從組織繼承成員權限
    define org_member: member from org
    define viewer: [user] or owner or org_member

type document
  relations
    define parent: [folder]
    define owner: [user]
    # 從文件夾繼承權限
    define parent_viewer: viewer from parent
    define viewer: [user] or owner or parent_viewer
```

**使用場景**:
- 文件系統（folder → document）
- 組織結構（organization → team → project）
- 嵌套資源（workspace → board → card）

**SQL 影響**:
```
Check(document:1#viewer@user:alice):
  1. SQL: 檢查直接 viewer 關係
  2. SQL: 檢查 owner 關係
  3. SQL: 查詢 parent 關係 → folder:x
  4. 遞迴: Check(folder:x#viewer@user:alice)
     5. SQL: 檢查 folder 的 viewer
     6. SQL: 查詢 org 關係 → org:y
     7. 遞迴: Check(org:y#member@user:alice)
        8. SQL: 檢查 org member

總計約 6-8 次 SQL
```

**優化技巧**:
- 限制層級深度（最多 2-3 層）
- 在高頻路徑使用直接關係
- 考慮定期同步權限到子對象

---

### 4.2 角色繼承模式

**場景**: 高級角色自動擁有低級角色的所有權限。

**模式**:
```dsl
type document
  relations
    define owner: [user, group#member]
    # editor 繼承 owner 的所有權限
    define editor: [user, group#member] or owner
    # viewer 繼承 editor 的所有權限
    define viewer: [user, group#member] or editor
    
    # 權限基於角色
    define can_delete: owner
    define can_write: editor
    define can_read: viewer
```

**權限金字塔**:
```
       owner (最高權限)
         ↓
      editor (可寫)
         ↓  
      viewer (可讀)
```

**優點**:
- 符合直覺
- 易於管理
- SQL 查詢可以利用短路優化

**注意事項**:
- 確保繼承鏈清晰
- 避免循環繼承
- 文檔化角色層級

---

### 4.3 團隊/群組權限模式

**場景**: 通過團隊成員身份授予權限。

**模式**:
```dsl
type group
  relations
    define member: [user]
    define admin: [user]

type document
  relations
    define owner: [user]
    # 團隊整體的訪問權限
    define viewer_group: [group]
    define editor_group: [group]
    
    # 展開團隊成員
    define viewer_from_group: member from viewer_group
    define editor_from_group: member from editor_group
    
    # 合併所有權限來源
    define viewer: [user] or viewer_from_group
    define editor: [user] or editor_from_group or owner
```

**Tuple 範例**:
```
group:engineering#member@user:alice
group:engineering#member@user:bob
document:1#viewer_group@group:engineering

→ alice 和 bob 都能訪問 document:1
```

**SQL 執行**:
```
Check(document:1#viewer@user:alice):
  1. SQL: 檢查直接 viewer
  2. SQL: 查詢 viewer_group → group:engineering
  3. SQL: 檢查 group:engineering#member@user:alice ✓

約 3 次 SQL
```

---

### 4.4 條件訪問模式

**場景**: 基於動態條件授予訪問權限。

**模式**:
```dsl
type document
  relations
    define owner: [user]
    # 需要滿足 IP 限制的查看者
    define restricted_viewer: [user with ip_allowed]
    # 需要有效訂閱的查看者
    define subscriber_viewer: [user with valid_subscription]
    
    define viewer: owner or restricted_viewer or subscriber_viewer
```

**Check 請求**:
```javascript
await client.check({
  object: 'document:1',
  relation: 'viewer',
  user: 'user:alice',
  context: {
    ip_address: '192.168.1.1',
    valid_subscription: true,
    ip_allowed: true
  }
});
```

**使用場景**:
- IP 白名單
- 時間限制（工作時間訪問）
- 訂閱狀態
- 多因素認證

**注意**: 條件越複雜，性能影響越大。

---

### 4.5 委派模式

**場景**: 用戶可以將自己的權限委派給其他用戶。

**模式**:
```dsl
type document
  relations
    define owner: [user]
    # 被委派的編輯者
    define delegated_editor: [user]
    # 委派關係：誰委派給誰
    define delegator: [user]
    
    define editor: owner or delegated_editor
    # 只有 owner 可以委派
    define can_delegate: owner
```

**應用邏輯**:
```javascript
// 檢查 alice 是否可以委派權限
const canDelegate = await client.check({
  object: 'document:1',
  relation: 'can_delegate',
  user: 'user:alice'
});

if (canDelegate) {
  // 寫入委派關係
  await client.write({
    writes: [{
      object: 'document:1',
      relation: 'delegated_editor',
      user: 'user:bob'
    }]
  });
}
```

---

### 4.6 時間限制訪問模式

**場景**: 授予臨時訪問權限。

**方案 1: 使用條件**
```dsl
type document
  relations
    define temporary_viewer: [user with not_expired]

# Check with context
{
  "context": {
    "current_time": "2024-01-15T10:00:00Z",
    "expiry_time": "2024-01-20T10:00:00Z",
    "not_expired": true  // 由應用層計算
  }
}
```

**方案 2: 使用過期機制**
```javascript
// 寫入時設置 TTL (如果存儲支持)
await client.write({
  writes: [{
    object: 'document:1',
    relation: 'viewer',
    user: 'user:alice'
  }],
  // 配合後台任務清理過期關係
});

// 後台任務定期清理
async function cleanupExpiredTuples() {
  // 查詢過期的 tuples
  // 執行刪除操作
}
```

**方案 3: 使用 Contextual Tuples**
```javascript
// 最簡單的方案：不寫入數據庫
const result = await client.check({
  object: 'document:1',
  relation: 'viewer',
  user: 'user:alice',
  contextualTuples: [
    // 臨時權限，由應用層管理過期
    {object: 'document:1', relation: 'viewer', user: 'user:alice'}
  ]
});
```

**推薦**: 方案 3 最簡單且性能最好。

---

## 5. 常見陷阱與反模式

### 5.1 ❌ 過度細化權限

**問題**: 定義過多細粒度的權限關係。

**反模式**:
```dsl
type document
  relations
    define can_read_title: [user]
    define can_read_content: [user]
    define can_read_metadata: [user]
    define can_read_comments: [user]
    define can_write_title: [user]
    define can_write_content: [user]
    define can_write_metadata: [user]
    define can_add_comment: [user]
    define can_delete_comment: [user]
    define can_edit_comment: [user]
    # 太多細粒度的權限！
```

**問題**:
- 管理複雜度高
- 每個權限檢查都需要 SQL 查詢
- 難以維護和理解
- 性能差

**✅ 改進方案**:
```dsl
type document
  relations
    define owner: [user]
    define editor: [user] or owner
    define viewer: [user] or editor
    
    # 在應用層處理細粒度邏輯
    define can_read: viewer
    define can_write: editor
    define can_delete: owner
```

**原則**: 權限粒度應該與業務需求匹配，不要過度設計。

---

### 5.2 ❌ 循環依賴

**問題**: 關係定義相互引用，形成循環。

**反模式**:
```dsl
type document
  relations
    define editor: viewer  # editor 依賴 viewer
    define viewer: editor  # viewer 依賴 editor - 循環！
```

**結果**:
- Check 會檢測到循環並返回 `{allowed: false, cycleDetected: true}`
- 浪費 SQL 查詢
- 邏輯錯誤

**✅ 正確設計**:
```dsl
type document
  relations
    define owner: [user]
    define editor: [user] or owner  # 單向依賴
    define viewer: [user] or editor # 單向依賴
```

**檢測循環**: OpenFGA 會自動檢測並返回錯誤，但應該在設計階段避免。

---

### 5.3 ❌ 過度使用 TTU 導致性能問題

**問題**: 過多或過深的 TTU 導致大量 SQL 查詢。

**反模式**:
```dsl
type document
  relations
    define parent1: [folder]
    define parent2: [workspace]
    define parent3: [organization]
    define parent4: [tenant]
    
    # 4 個並行的 TTU！
    define viewer: viewer from parent1 or 
                   viewer from parent2 or 
                   viewer from parent3 or 
                   viewer from parent4
```

**SQL 影響**:
```
Check(document:1#viewer@user:alice):
  並行執行 4 個 TTU 分支:
  1. 查詢 parent1 → 遞迴 Check → 多次 SQL
  2. 查詢 parent2 → 遞迴 Check → 多次 SQL
  3. 查詢 parent3 → 遞迴 Check → 多次 SQL
  4. 查詢 parent4 → 遞迴 Check → 多次 SQL
  
  可能產生 10+ 次 SQL 查詢
```

**✅ 改進方案**:
```dsl
type document
  relations
    # 只保留一個主要的層級關係
    define parent: [folder]
    define org: [organization]
    
    # 直接關係 + 一層 TTU
    define viewer: [user] or viewer from parent or member from org
```

---

### 5.4 ❌ 忽略索引優化

**問題**: 設計的查詢模式無法有效使用數據庫索引。

**反模式**:
```dsl
type document
  relations
    # 不指定具體類型，查詢時需要掃描更多數據
    define viewer: [user, group#member, team#member, org#member, role#assignee, ...]
```

**問題**:
- SQL 查詢需要 OR 多個條件
- 索引利用率降低
- 查詢變慢

**✅ 改進**:
```dsl
type document
  relations
    # 限制類型，提高索引效率
    define viewer: [user, group#member]
    
    # 其他類型通過其他機制處理
    define org: [organization]
    define org_viewer: member from org
    define all_viewer: viewer or org_viewer
```

---

### 5.5 ❌ 混淆直接關係和計算關係

**問題**: 不清楚什麼時候該用直接關係，什麼時候用計算關係。

**反模式**:
```dsl
type document
  relations
    define owner: [user]
    # 不必要的計算關係
    define super_owner: owner
    define mega_owner: super_owner
    define ultra_owner: mega_owner
```

**原則**:
- **直接關係**: 需要顯式寫入 tuple 的關係
- **計算關係**: 從其他關係派生的關係

**✅ 正確使用**:
```dsl
type document
  relations
    define owner: [user]           # 直接關係
    define editor: [user] or owner # 計算關係（從 owner 派生）
    define viewer: editor          # 計算關係（從 editor 派生）
```

---

### 5.6 ❌ 不考慮寫入性能

**問題**: 只關注讀取（Check）性能，忽略寫入操作的影響。

**反模式**:
```dsl
# 設計需要寫入大量 tuple 的模型
type document
  relations
    define viewer: [user]

# 當一個組有 10000 個成員時
# 需要寫入 10000 個 tuple：
# document:1#viewer@user:1
# document:1#viewer@user:2
# ...
# document:1#viewer@user:10000
```

**問題**:
- 寫入慢
- 數據庫空間大
- 刪除/更新困難

**✅ 改進**:
```dsl
type group
  relations
    define member: [user]

type document
  relations
    define viewer_group: [group]
    define viewer: member from viewer_group

# 只需要寫入 1 個 tuple：
# document:1#viewer_group@group:engineering
# 查詢時動態展開 group 的 member
```

---

### 5.7 ❌ 過度使用萬用字元

**問題**: 將所有公開資源都用萬用字元表示。

**反模式**:
```dsl
type document
  relations
    define viewer: [user:*]  # 所有文檔都是公開的？

# 所有文檔都寫入：
# document:*#viewer@user:*
```

**問題**:
- 無法區分真正需要保護的資源
- 安全風險
- 難以審計

**✅ 改進**:
```dsl
type document
  relations
    define public: [user:*]   # 明確標記為公開
    define viewer: [user] or public  # 分離公開和私有邏輯

# 只有公開文檔才寫入：
# document:public-doc-1#public@user:*
# 私有文檔寫入：
# document:private-doc-1#viewer@user:alice
```

---

## 6. 進階優化技巧

### 6.1 預計算權限

**概念**: 在寫入時計算並存儲權限，而不是在檢查時計算。

**傳統方式** (Read-time expansion):
```dsl
type document
  relations
    define parent: [folder]
    define viewer: viewer from parent  # Check 時遞迴查詢
```

**優化方式** (Write-time expansion):
```javascript
// 當文檔關聯到 folder 時
async function addDocumentToFolder(docId, folderId) {
  // 1. 查詢 folder 的所有 viewer
  const folderViewers = await listUsers({
    object: `folder:${folderId}`,
    relation: 'viewer'
  });
  
  // 2. 直接將這些 viewer 寫入到 document
  await client.write({
    writes: [
      {object: `document:${docId}`, relation: 'parent', user: `folder:${folderId}`},
      ...folderViewers.map(user => ({
        object: `document:${docId}`,
        relation: 'viewer',
        user: user
      }))
    ]
  });
}
```

**優缺點**:

**優點**:
- Check 極快（單次 SQL 查詢）
- 無需遞迴
- 預測性能好

**缺點**:
- 寫入更復雜
- 需要更多存儲空間
- 權限變更時需要級聯更新

**使用場景**:
- 高讀低寫的場景
- 權限結構相對穩定
- 需要極致查詢性能

---

### 6.2 權限快照

**概念**: 定期為常用查詢創建快照，減少實時計算。

**實現**:
```javascript
// 後台任務：每小時計算一次
async function snapshotUserPermissions(userId) {
  // 查詢用戶的所有權限
  const objects = await listObjects({
    user: `user:${userId}`,
    relation: 'viewer',
    type: 'document'
  });
  
  // 存儲快照
  await redis.set(`perm_snapshot:${userId}`, JSON.stringify(objects), 'EX', 3600);
}

// 使用快照加速檢查
async function fastCheck(object, relation, user) {
  // 1. 嘗試從快照讀取
  const snapshot = await redis.get(`perm_snapshot:${user}`);
  if (snapshot) {
    const objects = JSON.parse(snapshot);
    if (objects.includes(object)) {
      return {allowed: true, fromCache: true};
    }
  }
  
  // 2. Fallback 到實時檢查
  return await client.check({object, relation, user});
}
```

**適用場景**:
- 用戶權限變化不頻繁
- 可以容忍短暫的不一致
- 極高 QPS 要求

---

### 6.3 分層快取策略

**概念**: 在不同層級使用不同的快取策略。

**實現**:
```
第 1 層: 應用內存快取 (最快，最短 TTL)
  ↓
第 2 層: Redis 分布式快取 (快，中等 TTL)
  ↓
第 3 層: OpenFGA 內建快取 (中等速度)
  ↓
第 4 層: 數據庫查詢 (最慢，最準確)
```

**配置範例**:
```javascript
// 應用層快取
const localCache = new LRU({
  max: 10000,
  maxAge: 60000  // 1 分鐘
});

async function cachedCheck(object, relation, user) {
  const key = `${object}:${relation}:${user}`;
  
  // L1: 內存快取
  let result = localCache.get(key);
  if (result) return result;
  
  // L2: Redis 快取
  result = await redis.get(key);
  if (result) {
    localCache.set(key, result);
    return JSON.parse(result);
  }
  
  // L3 & L4: OpenFGA 檢查 (含內建快取和數據庫)
  result = await client.check({object, relation, user});
  
  // 寫回快取
  redis.set(key, JSON.stringify(result), 'EX', 300);  // 5 分鐘
  localCache.set(key, result);
  
  return result;
}
```

---

### 6.4 批量讀取優化

**問題**: 需要檢查用戶對多個資源的權限。

**❌ 低效方式**:
```javascript
// N 次 Check 調用
for (const doc of documents) {
  const canView = await client.check({
    object: `document:${doc.id}`,
    relation: 'viewer',
    user: 'user:alice'
  });
  if (canView.allowed) {
    results.push(doc);
  }
}
```

**✅ 優化方式 1: BatchCheck**:
```javascript
// 單次批量檢查
const checks = documents.map(doc => ({
  object: `document:${doc.id}`,
  relation: 'viewer',
  user: 'user:alice'
}));

const results = await client.batchCheck(checks);
```

**✅ 優化方式 2: ListObjects**:
```javascript
// 直接列出用戶可訪問的所有文檔
const allowedDocs = await client.listObjects({
  user: 'user:alice',
  relation: 'viewer',
  type: 'document'
});

// 過濾結果
const results = documents.filter(doc => 
  allowedDocs.includes(`document:${doc.id}`)
);
```

---

### 6.5 智能查詢規劃

**概念**: 根據統計信息選擇最優的查詢策略。

**實現思路**:
```javascript
class SmartChecker {
  async check(object, relation, user) {
    // 查詢統計信息
    const stats = await this.getStats(object, relation);
    
    if (stats.directTuples < 100) {
      // 直接關係少，直接查詢快
      return this.directCheck(object, relation, user);
    } else if (stats.hasWildcard) {
      // 有萬用字元，優先檢查
      return this.wildcardCheck(object, relation, user);
    } else {
      // 使用標準檢查
      return this.standardCheck(object, relation, user);
    }
  }
}
```

---

### 6.6 非正規化權限數據

**概念**: 犧牲部分正規化，換取查詢性能。

**範例**:
```dsl
type document
  relations
    # 正規化方式
    define folder: [folder]
    define viewer: viewer from folder
    
    # 非正規化方式：同時存儲直接權限
    define direct_viewer: [user]  # 從 folder 繼承時也寫入這裡
    define computed_viewer: viewer from folder
    define all_viewer: direct_viewer or computed_viewer
```

**寫入邏輯**:
```javascript
async function grantFolderAccess(folderId, userId) {
  // 1. 授予 folder 權限
  await client.write({
    writes: [{
      object: `folder:${folderId}`,
      relation: 'viewer',
      user: `user:${userId}`
    }]
  });
  
  // 2. 同時更新所有子文檔（非正規化）
  const docs = await getDocumentsInFolder(folderId);
  await client.write({
    writes: docs.map(doc => ({
      object: `document:${doc.id}`,
      relation: 'direct_viewer',
      user: `user:${userId}`
    }))
  });
}
```

**權衡**:
- **優點**: Check 速度快，無需遞迴
- **缺點**: 寫入更復雜，數據冗餘，一致性維護困難

---

## 7. 模型演化與遷移

### 7.1 版本控制

**原則**: 授權模型應該像代碼一樣進行版本控制。

**實踐**:
```
models/
  v1_initial_model.fga
  v2_add_groups.fga
  v3_add_conditions.fga
  current.fga → v3_add_conditions.fga
```

**文檔化變更**:
```markdown
# Authorization Model Changelog

## v3 (2024-01-15)
- Added conditional relationships for IP-based access
- Breaking change: Renamed `can_view` to `viewer`

## v2 (2024-01-01)
- Added group support
- Added organization hierarchy

## v1 (2023-12-01)
- Initial model with basic document permissions
```

---

### 7.2 向後兼容的遷移

**問題**: 如何在不影響現有 tuples 的情況下更新模型？

**策略 1: 添加新關係，漸進遷移**
```dsl
# 舊模型
type document
  relations
    define can_view: [user]

# 新模型 (v2)
type document
  relations
    define can_view: [user]     # 保留舊關係
    define viewer: [user] or can_view  # 新關係，兼容舊數據
```

**遷移步驟**:
```javascript
// 1. 部署新模型
await client.writeAuthorizationModel(newModel);

// 2. 更新應用代碼使用新關係
// Old: check({relation: 'can_view'})
// New: check({relation: 'viewer'})

// 3. 後台任務遷移數據
async function migrateOldTuples() {
  const oldTuples = await client.read({relation: 'can_view'});
  await client.write({
    writes: oldTuples.map(t => ({
      object: t.object,
      relation: 'viewer',
      user: t.user
    }))
  });
}

// 4. 確認遷移完成後，移除舊關係
```

---

### 7.3 破壞性變更處理

**場景**: 需要重命名或重構關係。

**步驟**:

**第 1 階段: 雙寫**
```javascript
// 同時寫入新舊關係
async function grantAccess(docId, userId) {
  await client.write({
    writes: [
      {object: `document:${docId}`, relation: 'can_view', user: userId},  // 舊
      {object: `document:${docId}`, relation: 'viewer', user: userId}     // 新
    ]
  });
}
```

**第 2 階段: 雙讀**
```javascript
// 檢查時優先使用新關係，fallback 到舊關係
async function checkAccess(docId, userId) {
  const newCheck = await client.check({
    object: `document:${docId}`,
    relation: 'viewer',
    user: userId
  });
  
  if (newCheck.allowed) return true;
  
  // Fallback 到舊關係
  const oldCheck = await client.check({
    object: `document:${docId}`,
    relation: 'can_view',
    user: userId
  });
  
  return oldCheck.allowed;
}
```

**第 3 階段: 遷移數據**
```javascript
// 批量遷移
async function migrateTuples() {
  let continuationToken = '';
  
  do {
    const {tuples, token} = await client.read({
      relation: 'can_view',
      pageSize: 100,
      continuationToken
    });
    
    // 寫入新關係
    await client.write({
      writes: tuples.map(t => ({
        object: t.object,
        relation: 'viewer',
        user: t.user
      }))
    });
    
    continuationToken = token;
  } while (continuationToken);
}
```

**第 4 階段: 清理**
```javascript
// 刪除舊關係的 tuples
async function cleanup() {
  await client.write({
    deletes: await getAllOldTuples('can_view')
  });
}

// 部署移除舊關係的新模型
```

---

### 7.4 測試策略

**單元測試**:
```javascript
describe('Document permissions', () => {
  beforeEach(async () => {
    // 設置測試環境
    await client.writeAuthorizationModel(testModel);
  });

  it('owner can delete document', async () => {
    await client.write({
      writes: [{
        object: 'document:1',
        relation: 'owner',
        user: 'user:alice'
      }]
    });
    
    const result = await client.check({
      object: 'document:1',
      relation: 'can_delete',
      user: 'user:alice'
    });
    
    expect(result.allowed).toBe(true);
  });

  it('viewer cannot delete document', async () => {
    await client.write({
      writes: [{
        object: 'document:1',
        relation: 'viewer',
        user: 'user:bob'
      }]
    });
    
    const result = await client.check({
      object: 'document:1',
      relation: 'can_delete',
      user: 'user:bob'
    });
    
    expect(result.allowed).toBe(false);
  });
});
```

**性能測試**:
```javascript
describe('Performance tests', () => {
  it('check should complete within 50ms', async () => {
    const start = Date.now();
    
    await client.check({
      object: 'document:1',
      relation: 'viewer',
      user: 'user:alice'
    });
    
    const duration = Date.now() - start;
    expect(duration).toBeLessThan(50);
  });

  it('should handle concurrent checks', async () => {
    const checks = Array(100).fill(null).map((_, i) => 
      client.check({
        object: `document:${i}`,
        relation: 'viewer',
        user: 'user:alice'
      })
    );
    
    const results = await Promise.all(checks);
    expect(results).toHaveLength(100);
  });
});
```

---

### 7.5 監控與可觀測性

**關鍵指標**:

```javascript
// 追蹤 Check 延遲
const checkDuration = new Histogram({
  name: 'openfga_check_duration_ms',
  help: 'Check request duration',
  labelNames: ['relation', 'result']
});

async function monitoredCheck(params) {
  const start = Date.now();
  
  try {
    const result = await client.check(params);
    const duration = Date.now() - start;
    
    checkDuration.observe({
      relation: params.relation,
      result: result.allowed ? 'allowed' : 'denied'
    }, duration);
    
    return result;
  } catch (error) {
    checkDuration.observe({
      relation: params.relation,
      result: 'error'
    }, Date.now() - start);
    
    throw error;
  }
}

// 追蹤 SQL 查詢次數
const datastoreQueries = new Counter({
  name: 'openfga_datastore_queries_total',
  help: 'Total datastore queries',
  labelNames: ['operation']
});
```

**告警規則**:
```yaml
# Prometheus alerts
groups:
  - name: openfga
    rules:
      - alert: HighCheckLatency
        expr: histogram_quantile(0.99, openfga_check_duration_ms) > 100
        for: 5m
        annotations:
          summary: "Check latency is high"
          
      - alert: HighSQLQueryCount
        expr: rate(openfga_datastore_queries_total[5m]) > 1000
        annotations:
          summary: "Too many SQL queries"
```

---

## 8. 總結與檢查清單

### 設計檢查清單

在設計授權模型時，確認以下幾點：

- [ ] **遞迴深度** < 3 層
- [ ] **Union 分支** < 5 個
- [ ] **TTU 使用** 合理，避免鏈式
- [ ] **直接關係優先** 於計算關係
- [ ] **命名清晰一致**
- [ ] **避免循環依賴**
- [ ] **用戶類型明確定義**
- [ ] **萬用字元使用謹慎**
- [ ] **條件關係必要時才用**
- [ ] **考慮寫入性能**
- [ ] **有版本控制和文檔**
- [ ] **有測試覆蓋**
- [ ] **有監控和告警**

### 性能優化檢查清單

- [ ] 利用短路求值優化 Union
- [ ] 批量操作使用 BatchCheck
- [ ] 高頻路徑使用直接關係
- [ ] 考慮預計算權限（write-time expansion）
- [ ] 使用 Contextual Tuples 處理臨時權限
- [ ] 配置適當的快取策略
- [ ] 監控 SQL 查詢次數和延遲
- [ ] 定期審查慢查詢

### 快速參考

**SQL 查詢次數估算**:
```
最簡單: 2 次 (模型 + 直接關係)
典型: 3-5 次 (模型 + 1-2 層遞迴)
複雜: 5-15 次 (多層 TTU + Union)
過度複雜: 15+ 次 (需要優化)
```

**延遲目標**:
```
優秀: < 10ms (單次直接關係查詢)
良好: < 50ms (1-2 層遞迴)
可接受: < 100ms (複雜權限檢查)
需優化: > 100ms
```

**關係類型選擇**:
```
直接關係 → 最快，首選
計算關係 (computed userset) → 代碼復用
TTU (1 層) → 層級權限，可接受
TTU (2+ 層) → 謹慎使用
Union (< 5 分支) → 靈活性
Intersection → 必要時才用
```

---

## 參考資源

- [OpenFGA Documentation](https://openfga.dev/docs)
- [Check API Implementation Guide](./CHECK_API_IMPLEMENTATION_GUIDE.md)
- [OpenFGA Playground](https://play.fga.dev)
- [Community Examples](https://github.com/openfga/sample-stores)

---

**最後更新**: 2026-01-01
**版本**: 1.0
**維護者**: Based on OpenFGA Check API source code analysis
