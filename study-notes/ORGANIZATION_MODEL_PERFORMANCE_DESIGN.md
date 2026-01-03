# OpenFGA 深層組織架構效能優化設計指南

## 情境說明

假設你的組織有 **14 層階層結構**，每一層都有員工（employee），需要設計一個高效能的授權模型。

```
組織結構範例:
Level 1: Company (CEO, employees)
Level 2: Division (VP, employees)
Level 3: Department (Director, employees)
Level 4: Sub-Department (Manager, employees)
...
Level 14: Team Unit (Team Lead, employees)
```

**挑戰**:

- OpenFGA 預設遞迴深度限制：**25 層**
- 14 層結構接近限制，需要謹慎設計
- 每次 Check 可能需要多次 SQL 查詢和遞迴呼叫
- 需要在準確性和效能之間取得平衡

---

## 設計方案比較

### 方案 1: 純層次化設計（最差效能）❌

**重要概念澄清**:
在組織架構中，**上層（Level 1）應該能看到所有下層（Level 2-14）的員工**。因此：

- Level 1（公司）包含 Level 1-14 的所有員工
- Level 5（部門）包含 Level 5-14 的所有員工

**模型定義**:

```
type organization
  relations
    define sub_org: [organization]  # 下屬組織（不是 parent！）
    define member: [employee] or member from sub_org
```

**資料結構**:

```
# 層級關係：上層指向下層（包含關係）
# Level 1 (CEO) 包含 Level 2 (VP)，Level 2 包含 Level 3，依此類推
# 數字越小 = 層級越高 = 包含範圍越大
organization:level1#sub_org@organization:level2
organization:level2#sub_org@organization:level3
...
organization:level13#sub_org@organization:level14

# 員工在最底層（Level 14 = Section）
organization:level14#member@employee:kevin
```

**效能分析**:

執行 `Check(organization:level1#member@employee:kevin)`:

```
深度 0: Check(level1#member@employee:kevin)
  ├─ [SQL #2] 檢查直接關係 → 無
  └─ [SQL #5] 查詢 level1#sub_org → [level2]
      ├─ dispatch → Check(level2#member@employee:kevin)
      深度 1:
        ├─ [SQL #2] 檢查直接關係 → 無
        └─ [SQL #5] 查詢 level2#sub_org → [level3]
            └─ dispatch → Check(level3#member@employee:kevin)
            深度 2:
              ... (繼續遞迴到深度 13)
              深度 13: Check(level14#member@employee:kevin)
                └─ [SQL #2] 找到！✓

# 查詢路徑: Level 1 → Level 2 → ... → Level 14 ✓
# 結果: Level 1 確實包含 Level 14 的員工 kevin
```

**效能指標**:

- **SQL 查詢次數**: 28 次（14 次檢查直接關係 + 14 次 TTU 查詢）
- **遞迴深度**: 14 層
- **總延遲**: ~300-500ms（假設每次 SQL 20-30ms）
- **資料庫負載**: 非常高

**優點**:

- ✅ 資料結構清晰
- ✅ 易於理解

**缺點**:

- ❌ 效能極差
- ❌ 深度接近限制
- ❌ 無法利用快速路徑優化
- ❌ 每次查詢都要遍歷完整路徑

---

### 方案 2: 扁平化設計（最佳效能）✅

**設計邏輯**:

- Level 1 包含 Level 1-14 所有員工 → `level1_member` 繼承所有下層
- Level 5 包含 Level 5-14 員工 → `level5_member` 繼承 level6-14
- 因此：`level1_member` ⊃ `level2_member` ⊃ ... ⊃ `level14_member`

**模型定義**:

```
type organization
  relations
    # Level 1 包含自己及所有下層（Level 2-14）
    define level1_member: [employee] or level2_member
    define level2_member: [employee] or level3_member
    define level3_member: [employee] or level4_member
    ...
    define level13_member: [employee] or level14_member
    define level14_member: [employee]  # 最底層，沒有下層

    # 別名，用於外部 API
    define member: level1_member  # 指向最上層，包含所有人
```

**資料結構**:

```
# Kevin 在 level 14（最底層）
organization:company#level14_member@employee:kevin


# 自動繼承：level14 → level13 → ... → level1
# 查詢 level1_member 會自動包含 kevin！
```

**效能分析**:

執行 `Check(organization:company#member@employee:kevin)`:

```

深度 0: Check(company#member@employee:kevin)
└─ 改寫為 Check(company#level1_member@employee:kevin)
深度 1: Check(company#level1_member@employee:kevin)
├─ [SQL #2] 檢查 level1 直接關係 → 無
└─ 改寫為 Check(company#level2_member@employee:kevin)
深度 2: Check(company#level2_member@employee:kevin)
├─ [SQL #2] → 無
└─ ... (繼續改寫，但這是計算關係，不是 TTU)
深度 14: Check(company#level14_member@employee:kevin)
└─ [SQL #2] 找到！✓

# 雖然看起來有 14 層，但都是 computed userset（改寫），

# 不是 TTU，所以執行極快！只需要最後一次 SQL 查詢。

```

**效能指標**:

- **SQL 查詢次數**: 2 次（1 次模型 + 1 次直接關係）
- **遞迴深度**: 2 層
- **總延遲**: ~20-40ms
- **資料庫負載**: 極低

**優點**:

- ✅ **效能極佳**（最快方案）
- ✅ 深度極淺（僅 2 層）
- ✅ 可使用快速路徑優化
- ✅ 資料庫查詢最少

**缺點**:

- ⚠️ 模型定義較長（需要 14 個關係定義）
- ⚠️ 新增員工時需要寫入正確的 level 關係
- ⚠️ 組織結構變更時需要更新資料

**最佳實踐**:

```python
# 新增員工時，寫入最精確的層級
def add_employee(org_id, employee_id, level):
    fga.write([
        {
            "object": f"organization:{org_id}",
            "relation": f"level{level}_member",
            "user": f"employee:{employee_id}"
        }
    ])
    # Kevin 在 level 14 (Section) → 自動被 level1-13（上層）包含
```

---

### 方案 3: 分組層次化設計（平衡方案）⚖️

**模型定義**:

```
type organization
  relations
    # 每 3-4 層為一組
    define exec_sub_org: [organization]        # Level 1-4 的下屬組織
    define senior_sub_org: [organization]      # Level 5-8 的下屬組織
    define mid_sub_org: [organization]         # Level 9-12 的下屬組織
    define junior_sub_org: [organization]      # Level 13-14 的下屬組織

    define exec_member: [employee] or member from exec_sub_org
    define senior_member: [employee] or exec_member or member from senior_sub_org
    define mid_member: [employee] or senior_member or member from mid_sub_org
    define member: [employee] or mid_member or member from junior_sub_org
```

**資料結構**:

```
# 組織層級關係（上層指向下層）
organization:company#junior_sub_org@organization:level13
organization:level13#junior_sub_org@organization:level14

organization:company#mid_sub_org@organization:level9
organization:level9#mid_sub_org@organization:level10

```

執行 `Check(organization:company#member@employee:kevin)`:

```


深度 0: Check(company#member@employee:kevin)
├─ [SQL #2] 檢查直接 employee → 無
├─ checkComputedUserset → Check(company#mid_member@employee:kevin)
│ 深度 1:
│ ├─ [SQL #2] → 無
│ ├─ checkComputedUserset → Check(company#senior_member@employee:kevin)
│ │ 深度 2: → 無
│ └─ [SQL #5] TTU 查詢 mid_sub_org → [level9, level10, level11, level12]
│ └─ Union 並行:
│ ├─ Check(level9#member@kevin) → 無
│ ├─ Check(level10#member@kevin) → 無
│ ...
└─ [SQL #5] TTU 查詢 junior_sub_org → [level13, level14]
└─ Union 並行:
├─ Check(level13#member@kevin) → 無
└─ Check(level14#member@kevin)
└─ [SQL #2] 找到！✓

```

**效能指標**:

- **SQL 查詢次數**: 8-12 次
- **遞迴深度**: 4-5 層
- **總延遲**: ~80-150ms
- **資料庫負載**: 中等

**優點**:

- ✅ 效能良好（比純層次化快 3-5 倍）
- ✅ 模型相對簡潔
- ✅ 靈活性高，易於調整分組
- ✅ 深度遠低於限制

**缺點**:

- ⚠️ 需要維護分組關係
- ⚠️ 比扁平化設計慢

---

### 方案 4: 遞迴優化設計（最智慧）🚀

**模型定義**:

```
type organization
  relations
    define sub_org: [organization]  # 下屬組織（上層指向下層）
    define member: [employee, organization#member] or member from sub_org
```

**關鍵點**:

- 使用 `sub_org` 關係表示「上層包含哪些下層組織」
- `member from sub_org` 表示「從下屬組織繼承 member」
- 允許 `organization#member` 作為直接成員（userset 快取）
- 形成遞迴結構，自動觸發 Recursive Resolver

**TTU 語義說明**：

```
當執行 Check(level1#member@kevin) 時：
1. 查找 level1#sub_org@X（level1 的下屬組織）
2. 對每個 X，檢查 X#member@kevin
3. 如果 X 也有 sub_org，遞迴檢查
4. 最終在 level14#member@kevin 找到 ✓
```

**資料結構**:

```
# 層級關係（上層指向下層 - sub_org 關係）
# Level 1 (CEO) 包含 Level 2 (VP)
# Level 2 包含 Level 3，依此類推
# Level 13 包含 Level 14 (Section)
organization:level1#sub_org@organization:level2
organization:level2#sub_org@organization:level3
organization:level3#sub_org@organization:level4
...
organization:level12#sub_org@organization:level13
organization:level13#sub_org@organization:level14

# 員工在最底層（Level 14 = Section）
organization:level14#member@employee:kevin

# 優化：將下層的 member 直接關聯到上層（userset 快取）
# 表示「上層包含下層的所有 member」
organization:level1#member@organization:level14#member  # CEO 層包含 Section 成員
organization:level2#member@organization:level14#member  # VP 層包含 Section 成員
organization:level3#member@organization:level14#member
...
organization:level13#member@organization:level14#member
```

**OpenFGA 檢測到遞迴結構時會自動使用 Recursive Resolver**!

**效能分析**:

執行 `Check(organization:level1#member@employee:kevin)`:

**情境 1: 有 userset 快取（使用 recursiveUserset）**

```
使用 recursiveUserset:

深度 0: Check(level1#member@employee:kevin)
  └─ 檢測到遞迴 userset 結構

# 階段 1: 左側通道 - 從 object 側收集所有 userset
[SQL #1] Read(level1, member, organization#member)
→ 返回 userset 元組:
   - level1#member@organization:level14#member
   - level1#member@organization:level10#member
   - ...

建立 objectToUserset 集合 = {level14#member, level10#member, ...}

# 階段 2: 右側通道 - 從 user 側反向查詢
[SQL #2] ReadStartingWithUser(employee:kevin, member)
→ 查找所有包含 kevin 的 member 關係:
   - level14#member@employee:kevin
   - (可能還有其他層級)

建立 userToUserset 集合 = {level14#member, ...}

# 階段 3: 雙向掃描並檢查交集（使用 sync.Map 追蹤已訪問）
visited := sync.Map{}  # 環路檢測
並行處理左右通道，查找交集:
→ 找到共同的 userset: level14#member ✓

返回 {allowed: true}
```

**情境 2: 無 userset 快取（使用 recursiveTTU 或 defaultTTU）**

**如果滿足 recursiveTTU 條件**（使用 BFS 優化）:

```
使用 recursiveTTU (BFS 迭代):

深度 0: Check(level1#member@employee:kevin)
  └─ 檢測到遞迴 TTU 結構

# 階段 1: 右側通道 - 從 user 側開始
[SQL #1] ReadStartingWithUser(employee:kevin, member)
→ 找到: level14#member@employee:kevin
→ userObjectSet = {level14}

# 階段 2: 左側通道 - 從 object 側 BFS 展開
[SQL #2] Read(level1, sub_org, *)
→ 找到: level1#sub_org@level2
→ objectSet = {level2}

# 階段 3: BFS 廣度優先展開 (批次查詢)
[SQL #3-4] 批次查詢多層 sub_org
→ {level2, level3, level4, ..., level14}

# 階段 4: 檢查交集（使用 hashset）
intersection = objectSet ∩ userObjectSet
→ 找到: level14 ✓

返回 {allowed: true}
效能: 5-8 次 SQL，~80-120ms
```

**如果不滿足 recursiveTTU 條件**（回退到 defaultTTU）:

```
使用 defaultTTU (逐層遞迴):

深度 0: Check(level1#member@kevin)
[SQL #1] Read(level1, sub_org, *) → [level2]
  → dispatch Check(level2#member@kevin)

  深度 1: Check(level2#member@kevin)
  [SQL #2] Read(level2, sub_org, *) → [level3]
    → dispatch Check(level3#member@kevin)

    深度 2-13: 繼續遞迴...

    深度 13: Check(level14#member@kevin)
    [SQL #14] 找到: level14#member@employee:kevin ✓

返回 {allowed: true}
效能: 28+ 次 SQL，~300-500ms
```

**效能指標**:

| 情境                | 策略               | SQL 查詢 | 深度   | 延遲      |
| ------------------- | ------------------ | -------- | ------ | --------- |
| 有 userset 快取     | recursiveUserset   | 2-3 次   | 1-2 層 | 20-40ms   |
| 無快取 + 滿足條件   | recursiveTTU (BFS) | 5-8 次   | 2-3 層 | 80-120ms  |
| 無快取 + 不滿足條件 | defaultTTU (DFS)   | 28+ 次   | 14 層  | 300-500ms |

**recursiveTTU 觸發條件**（來自 TypeSystem）:

滿足以下**所有**條件才會使用 recursiveTTU（否則使用 defaultTTU）:

1. `weight[userType] = infinite`（無限權重，表示遞迴）
2. `RecursiveRelation = objectType#relation`（自我引用，如 `organization#member`）
3. `IsPartOfTupleCycle == false`（非環狀結構）
4. 有 TTU 邊指向自己（如 `organization#member from sub_org`）
5. 其他 union 成員（如直接的 `[employee]`）的權重 = 1
6. OR 節點只有一個 TTU 邊是遞迴的

**recursiveUserset 觸發條件**（針對 userset 關係）:

滿足以下**所有**條件才會使用 recursiveUserset:

1. `weight[userType] = infinite`（無限權重）
2. 關係定義允許 `organization#member` 作為直接關係
3. 存在 userset 元組（如 `level1#member@level14#member`）
4. 不是 tuple cycle 的一部分
5. 檢測到遞迴 userset 模式

**關鍵差異**:

- **recursiveTTU**: 處理 `member from sub_org`（TTU 關係），使用 BFS 展開 sub_org 鏈
- **recursiveUserset**: 處理 `organization#member`（userset 關係），使用雙向掃描找交集

**優點**:

- ✅ **自動優化**（OpenFGA 根據條件選擇最佳策略）
- ✅ **有快取時效能極佳**（recursiveUserset: 20-40ms，接近扁平化）
- ✅ **無快取時仍可用**（recursiveTTU: 80-120ms，比 defaultTTU 快 3-5 倍）
- ✅ 資料結構靈活，支援動態組織結構變更
- ✅ 使用 BFS（recursiveTTU）避免深度問題
- ✅ 使用 sync.Map（recursiveUserset）避免環路
- ✅ 可增量建立快取（不需一次全部建立）

**版本要求**:

| 版本範圍        | 狀態              | 備註                                                    |
| --------------- | ----------------- | ------------------------------------------------------- |
| < v1.8.0        | ❌ 不支援         | 無 Recursive Resolver 實現                              |
| v1.8.0 - v1.9.2 | ⚠️ 支援（需啟用） | 需要環境變數: `OPENFGA_ENABLE_CHECK_OPTIMIZATIONS=true` |
| v1.9.3+         | ✅ 完全支援       | Check fast path v2 預設啟用，無需旗標                   |
| **v1.10.0+**    | **✅✅ 推薦**     | **最新版本，Recursive Resolver 完全成熟優化**           |

**版本升級建議**:

```bash
# 最低要求: v1.8.0 + 啟用旗標
docker run -e OPENFGA_ENABLE_CHECK_OPTIMIZATIONS=true openfga/openfga:v1.8.15

# 推薦: v1.9.3+ (無需旗標)
docker run openfga/openfga:v1.9.3

# 最佳: v1.10.0+ (最新最穩定)
docker run openfga/openfga:latest
```

**缺點**:

- ⚠️ 需要維護 userset 關係（可以自動化）
- ⚠️ 初始資料遷移較複雜

**資料維護策略**:

```python
# 當員工加入 level 14 時
def add_employee_optimized(employee_id, level):
    writes = [
        # 直接關係
        {
            "object": f"organization:level{level}",
            "relation": "member",
            "user": f"employee:{employee_id}"
        }
    ]

    # 為上層組織新增 userset 關聯（優化查詢）
    for parent_level in range(1, level):
        writes.append({
            "object": f"organization:level{parent_level}",
            "relation": "member",
            "user": f"organization:level{level}#member"
        })

    fga.write(writes)
```

**自動化維護**（推薦）:

```python
# 使用背景任務定期同步 userset 關係
async def sync_organization_userset_relations():
    # 查詢所有組織層級關係
    parent_relations = await fga.read(filter={
        "type": "organization",
        "relation": "parent"
    })

    # 為每個父子關係建立 member userset
    for rel in parent_relations:
        parent = rel.object
        child = rel.user

        # 新增: parent#member@child#member
        await fga.write([{
            "object": parent,
            "relation": "member",
            "user": f"{child}#member"
        }])
```

---

## 效能對比總結

| 方案       | SQL 查詢 | 遞迴深度 | 延遲 (ms) | 複雜度 | 推薦度        |
| ---------- | -------- | -------- | --------- | ------ | ------------- |
| 純層次化   | 28+      | 14       | 300-500   | 低     | ❌ 不推薦     |
| 扁平化     | 2        | 2        | 20-40     | 中     | ✅✅✅ 最佳   |
| 分組層次化 | 8-12     | 4-5      | 80-150    | 中     | ✅✅ 良好     |
| 遞迴優化   | 3-4      | 1-2      | 40-80     | 高     | ✅✅✅ 最智慧 |

---

## 推薦方案

### 🥇 首選：方案 2（扁平化設計）

**適用情境**:

- 組織結構**相對穩定**
- 追求**極致效能**
- 願意在新增員工時多寫一點程式碼

**實作範例**:

````typescript
// authorization_model.fga
model
  schema 1.1

type employee

type organization
  relations
    // 定義 14 層：上層包含下層
    define level1_member: [employee] or level2_member
    define level2_member: [employee] or level3_member
    define level3_member: [employee] or level4_member
    define level4_member: [employee] or level5_member
    define level5_member: [employee] or level6_member
    define level6_member: [employee] or level7_member
    define level7_member: [employee] or level8_member
    define level8_member: [employee] or level9_member
    define level9_member: [employee] or level10_member
    define level10_member: [employee] or level11_member
    define level11_member: [employee] or level12_member
    define level12_member: [employee] or level13_member
    define level13_member: [employee] or level14_member
    define level14_member: [employee]  // 最底層

    // 通用介面：指向最上層（包含所有人）
    define member: level1_member
```typescript
// 新增員工
async function addEmployee(orgId: string, employeeId: string, level: number) {
  await fga.write([
    {
      object: `organization:${orgId}`,
      relation: `level${level}_member`,
      user: `employee:${employeeId}`,
    },
  ]);
}

// 檢查權限（超快！）
const result = await fga.check({
  object: 'organization:company',
  relation: 'member',
  user: 'employee:kevin',
});
// SQL 查詢: 2 次
// 延遲: ~30ms
````

### 🥈 次選：方案 4（遞迴優化設計）

**適用情境**:

- 組織結構**經常變動**
- 需要**靈活性**
- 有資源維護 userset 關係

**實作範例**:

```typescript
// authorization_model.fga
model
  schema 1.1

type employee

type organization
  relations
    define sub_org: [organization]
    define member: [employee, organization#member] or member from sub_org

type document
  relations
    define parent: [organization]
    define viewer: member from parent
```

**資料操作**:

```typescript
// 新增員工（含優化）
async function addEmployeeWithOptimization(
  employeeId: string,
  organizationPath: string[] // ['level1', 'level2', ..., 'level14']
) {
  const writes = [
    // 員工直接關係
    {
      object: `organization:${organizationPath[organizationPath.length - 1]}`,
      relation: 'member',
      user: `employee:${employeeId}`,
    },
  ];

  // 建立層級關係（上層指向下層）
  // level1 (CEO) -> level2 (VP) -> ... -> level13 -> level14 (Section)
  for (let i = 0; i < organizationPath.length - 1; i++) {
    writes.push({
      object: `organization:${organizationPath[i]}`, // 上層
      relation: 'sub_org',
      user: `organization:${organizationPath[i + 1]}`, // 下層
    });
  }

  // 優化：為上層新增 userset 快取（可選，但能大幅提升效能）
  // 表示「上層包含下層的所有 member」
  const bottomLevel = organizationPath[organizationPath.length - 1]; // level14
  for (let i = 0; i < organizationPath.length - 1; i++) {
    writes.push({
      object: `organization:${organizationPath[i]}`, // level1, level2, ...
      relation: 'member',
      user: `organization:${bottomLevel}#member`, // level14#member
    });
  }

  await fga.write(writes);
}

// 檢查權限（使用 Recursive Resolver）
const result = await fga.check({
  object: 'organization:level1',
  relation: 'member',
  user: 'employee:kevin',
});
// SQL 查詢: 3-4 次（BFS 迭代）
// 延遲: ~60ms
```

---

## 進階優化技巧

### 1. 混合策略

結合扁平化和分組：

```
type organization
  relations
    // 前 10 層使用扁平化（上層包含下層）
    define level1_member: [employee] or level2_member
    define level2_member: [employee] or level3_member
    ...
    define level9_member: [employee] or level10_member
    define level10_member: [employee] or member from junior_sub_org

    // 後 4 層使用層次化
    define junior_sub_org: [organization]
    define member: level1_member  // 最上層包含所有人
```

在應用層維護常用查詢結果：

```typescript
const cache = new Map<string, boolean>();

async function checkWithCache(object: string, relation: string, user: string): Promise<boolean> {
  const key = `${object}#${relation}@${user}`;

  if (cache.has(key)) {
    return cache.get(key)!;
  }

  const result = await fga.check({ object, relation, user });
  cache.set(key, result.allowed);

  return result.allowed;
}
```

### 3. 批次預載

對於已知的查詢模式，預先建立 userset 關係：

```typescript
// 每日批次任務
async function prebuildUsersetRelations() {
  // 為所有組織建立完整的 member userset 圖
  const orgs = await getAllOrganizations();

  for (const org of orgs) {
    const descendants = await getDescendantOrgs(org.id);

    for (const desc of descendants) {
      await fga.write([
        {
          object: `organization:${org.id}`,
          relation: 'member',
          user: `organization:${desc.id}#member`,
        },
      ]);
    }
  }
}
```

### 4. 監控與調優

```typescript
// 追蹤查詢效能
async function checkWithMetrics(object: string, relation: string, user: string) {
  const start = Date.now();

  const result = await fga.check({ object, relation, user });

  const duration = Date.now() - start;

  // 記錄慢查詢
  if (duration > 100) {
    logger.warn('Slow Check query', {
      object,
      relation,
      user,
      duration,
      datastoreQueryCount: result.resolutionMetadata?.datastoreQueryCount,
    });
  }

  return result;
}
```

---

## 常見陷阱與解決方案

### ❌ 陷阱 1: 過度使用 TTU

```
❌ 錯誤設計:
define member: member from parent  // 每層都遞迴 TTU

✅ 正確設計:
define member: [employee] or member from parent  // 加上直接關係
```

### ❌ 陷阱 2: 忽略 userset 快取

```
❌ 只寫底層關係:
organization:level14#member@employee:kevin
# 查詢 level1 時的行為取決於是否滿足 recursiveTTU 條件：
# - 滿足條件：使用 recursiveTTU (BFS)，5-8次SQL，80-120ms
# - 不滿足條件：使用 defaultTTU (DFS)，28+次SQL，300-500ms

✅ 同時寫 userset 快取:
organization:level14#member@employee:kevin
organization:level1#member@organization:level14#member  // 加速查詢
organization:level2#member@organization:level14#member
# 查詢 level1 時：
# - 觸發 recursiveUserset（雙向掃描 + 環路檢測）
# - 2-3次SQL，20-40ms
# - 效能接近扁平化設計！
```

### ❌ 陷阱 3: 沒有監控深度

```typescript
✅ 加上深度檢查:
if (organizationDepth > 20) {
  logger.error('Organization depth exceeds recommended limit');
  // 考慮重構為扁平化設計
}
```

---

## 總結

對於 **14 層組織結構**：

1. **最佳效能**: 使用**扁平化設計**（方案 2）

   - SQL 查詢: 2 次
   - 延遲: 20-40ms
   - 適合穩定組織結構

2. **最佳靈活性**: 使用**遞迴優化設計**（方案 4）

   - SQL 查詢:
     - 有 userset 快取：2-3 次（recursiveUserset）
     - 無快取但滿足條件：5-8 次（recursiveTTU, BFS）
     - 無快取且不滿足條件：28+ 次（defaultTTU, DFS）
   - 延遲:
     - 有快取：20-40ms
     - 無快取但滿足條件：80-120ms
     - 無快取且不滿足條件：300-500ms
   - 自動選擇最佳策略（recursiveUserset > recursiveTTU > defaultTTU）
   - 適合動態組織結構

3. **避免**: 純層次化設計（方案 1）
   - SQL 查詢: 28+ 次
   - 延遲: 300-500ms
   - 接近遞迴深度限制

**關鍵建議**:

- 📊 監控查詢效能和深度
- 🔄 使用 userset 關係加速查詢
- ⚡ 利用 OpenFGA 的 Recursive Resolver（**v1.8.0+ 需要，v1.9.3+ 推薦**）
- 🎯 根據組織變動頻率選擇方案
- 📈 定期評估並優化模型設計
- 🔧 如果遇到 TTU 效能問題，確保 OpenFGA >= v1.9.3 且使用方案 4

---

## 版本要求說明

### Recursive Resolver 支援時間表

| OpenFGA 版本     | Recursive Resolver | 狀態                      | 建議          |
| ---------------- | ------------------ | ------------------------- | ------------- |
| < v1.8.0         | ❌ 無              | 過時                      | ❌ 不建議     |
| v1.8.0 - v1.8.14 | ✅ 有（實驗性）    | 需手動啟用旗標            | ⚠️ 可用       |
| v1.8.15          | ✅ 有（改善）      | 需手動啟用旗標 + 性能修復 | ✅ 可接受     |
| v1.9.0 - v1.9.2  | ✅ 有              | 實驗性旗標，需啟用        | ✅ 良好       |
| **v1.9.3+**      | **✅ 有**          | **預設啟用，無需旗標**    | **✅ 推薦**   |
| **v1.10.0+**     | **✅ 有**          | **完整優化，最穩定**      | **✅✅ 最佳** |

### 升級路線

**如果你遇到 TTU 效能問題**：

1. 檢查版本: `openfga version`
2. 如果 < v1.9.3，立即升級到 v1.9.3+
3. 使用**方案 4**（遞迴優化設計）
4. 確保模型包含 `organization#member`
5. 執行背景優化任務生成 userset 關係
