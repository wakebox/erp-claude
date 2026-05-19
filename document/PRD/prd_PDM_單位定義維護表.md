# PRD｜PDM — 單位定義維護表

> 來源：逆向自 `kingmaker-module-pdm` 後端程式碼（`controller/admin/unitdef/`、`service/unitdef/`、`dal/dataobject/unitdef/`、`dal/mysql/unitdef/`，以及與其相依的 `unitconv` 模組）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣總部的 **PDM（產品資料管理）人員**，負責維護「整套 ERP 計量單位字典」。倉儲、採購、營養成分、食譜這些模組裡只要出現「公斤」「公升」「片」「盒」「大卡」，背後都對應到我在這張表上建立的單位。

### 1.2 我要做什麼

- 維護整個 ERP 內可被引用的計量單位清單（公斤 kg、公克 g、公升 L、毫升 mL、片 pc、盒 box、大卡 kcal、毫克 mg…）
- 為每個單位指定「精算位數」，告訴下游模組這個單位在計算／顯示時最多保留幾位小數
- 用「狀態」（啟用 / 停用）控制單位是否能被新建檔的單據選用
- 變更或刪除已被「單位轉換維護表」使用的單位時，系統會擋下並提示先處理轉換關係
- 必要時管理單位代碼唯一性（同一套單位代碼如 `kg` 只能存在一筆）

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 用統一的計量單位字典 | 採購寫 KG、倉儲寫 公斤、營養成分寫 kg 會無法彙整與換算 |
| 每個單位有固定的小數精度 | 「片」不需要小數、「公升」常用到第 3 位；下游報表才能一致顯示 |
| 已被「單位轉換維護表」用到的單位要被保護 | 改了單位代碼 `kg` 為 `Kg`，所有轉換關係（kg ↔ g、kg ↔ 磅）就會失聯 |
| 不再使用的單位可以下架但不破壞歷史 | 例如試辦過的「打」想停用但保留歷史單據 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 單位定義分頁查詢（依代碼、名稱、狀態過濾） | 快速找到要編輯的單位 |
| 新增單位定義（含唯一性檢查） | 擴充單位字典 |
| 編輯單位定義（被轉換表用到時擋下） | 修改名稱、精算位數、狀態 |
| 批次刪除（被轉換表用到時擋下） | 移除誤建或不再使用的單位 |
| 「單位被使用」的友善錯誤訊息 | 引導使用者先處理單位轉換維護表的關聯資料 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 單位定義維護表 |
| 所屬模組 | PDM（產品資料管理） |
| 兄弟功能 | 編碼類別維護、編碼項目維護、編碼原則維護、營養成分定義維護表、餐食類型維護表、單位轉換維護表（強耦合）、門市分群維護表、物流類型維護表 |
| 主要頁面 | 單位定義清單頁（含查詢／新增／編輯／批次刪除） |
| 簽核流程 | 無（純基礎資料維護） |

---

## 2. 功能目的

單位定義是 PDM 模組的根級字典，作為所有與「量」相關欄位的下拉選項來源。其設計目的：

1. **建立 ERP 全域的計量單位語彙**：採購單、請購單、入出庫、營養成分定義、單位轉換都引用同一份清單
2. **承載精算位數**：每個單位自帶顯示／計算的小數位數限制，下游不需要各自硬編
3. **與單位轉換維護表強耦合保護**：本表為「單位」、單位轉換維護表為「單位間的換算係數」；本表的代碼一旦被換算表使用，就被視為「鎖定」狀態，連改名都不允許 — 強制使用者先處理換算表（來源：`PdmUnitDefServiceImpl.java:58、85-93`）
4. **以狀態做軟啟停**：試辦或不再使用的單位下架不必刪除，歷史資料仍可顯示

---

## 3. 業務邏輯背景

### 3.1 為什麼用「單位代碼」當對外鍵而不是 ID？

「單位轉換維護表」的 `baseUnit`、`targetUnit` 欄位儲存的是**單位代碼字串**（如 `kg`、`g`），不是單位定義表的 ID。這是個關鍵的設計決策：

- 優點：換算表的查詢可以不 join、直接讀字串
- 缺點：本表編輯時必須鎖住代碼欄位，否則換算表會孤兒。**這就是為什麼 update 行為這麼嚴格**（連改名都會被擋）

來源：`PdmUnitDefServiceImpl.java:84-88`、`PdmUnitDefServiceImpl.java:134-139`。

### 3.2 「精算位數」（precisionPlaces）

`precisionPlaces` 為整數，表示「以此單位計算時最多保留幾位小數」。常見對應：

| 單位 | 建議精算位數 |
|---|---|
| 公斤、公升、磅 | 3（如 12.345 kg） |
| 公克、毫升 | 1 或 2 |
| 片、盒、個（不可分割計數單位） | 0 |
| 千卡（熱量） | 0 或 1 |

本表只儲存此值，**實際在計算／顯示時是否套用，由下游模組（食材維護、採購單、入出庫量）自行讀取後決定**。後端不會對 `precisionPlaces` 的數值做合理範圍檢查（例如 0–10），任何整數都可寫入（見 §11）。

### 3.3 「狀態」是 Boolean，與餐食類型的 String 不一致

`status` 在本 DO 是 `Boolean`（true=啟用 / false=停用），不透過字典轉換。這與 [餐食類型維護表] 的 String + DictFormat 設計不同 — 同為「狀態」概念，PDM 內部沒有統一。下游引用本表時要直接用 boolean 判斷（見 §11）。

### 3.4 與框架慣例的偏離

本功能多處不符合 PDM 其他模組（與框架）的慣例：

1. **路徑短碼**：`/pdm/udf` 而非 `/pdm/unit-def`（其他模組 URL 都用 hyphen 完整字）
2. **拋例外方式**：唯一性檢查用 `throw new RuntimeException(...)`，而非框架的 `ServiceExceptionUtil.exception(ErrorCode)`（來源：`PdmUnitDefServiceImpl.java:125`） — 不會回傳結構化錯誤碼
3. **錯誤回傳混合**：更新／批次刪除用 `return false` 加 Controller 端的 `CommonResult.error(1, "字串訊息")` 回傳（來源：`PdmUnitDefController.java:52、63`） — 錯誤碼 `1` 是 magic number，與系統其他錯誤碼撞號
4. **更新採 PathVariable**：`PUT /update/{id}`，其他模組用 RequestBody 帶 id
5. **批次刪除用 RequestBody + List**：`DELETE /delete` 帶 body，其他模組用 `?ids=1,2,3` query string
6. **查詢權限被註解**：`@PreAuthorize('pdm:unit-def:query')` 在程式碼裡是註解狀態，目前查詢無權限保護（來源：`PdmUnitDefController.java:70`）
7. **沒有單筆 get、沒有 export-excel**：與其他基礎資料維護不一致

這些都列入 §11 待確認，未來重構時應對齊。

### 3.5 update 行為的隱性陷阱

更新邏輯的順序是：

1. 用「新代碼」檢查唯一性
2. 取出舊資料，用「**舊代碼**」檢查是否被單位轉換表使用
3. 若被使用 → 整筆更新都被拒絕（不論你改的是什麼欄位）
4. 否則執行 `updateById`

這代表：**只要單位已被換算表引用，連改「精算位數」「狀態」「名稱」這些不會影響換算關係的欄位也不行**（來源：`PdmUnitDefServiceImpl.java:57-60`）。從業務角度這通常太嚴格 — 例如想把 `kg` 停用，但因為 `kg ↔ g` 還在換算表，就無法停用。詳見 §11。

---

## 4. 情境說明

### 4.1 正常流程 — 新增單位「片」

PDM 人員小李要為新進的「起司片」食材建立單位。他進入「PDM > 單位定義維護表」，點「新增」，填入：

- 單位代碼：pc
- 單位名稱：片
- 精算位數：0
- 狀態：啟用

送出後系統先檢查 `pc` 是否已存在，未重複則建立成功，回傳新 ID。之後在食材維護作業選擇「起司片」的計量單位下拉，「片（pc）」就會出現。

### 4.2 典型業務 — 編輯「公升」的精算位數

主管反映報表上「飲料公升數」顯示到第 5 位太細，要改成第 3 位。小李在清單頁搜尋代碼 `L`，點編輯，把精算位數從 5 改為 3，狀態維持啟用。

**前提**：`L` 必須**沒有**出現在單位轉換維護表的任何一筆 `baseUnit` 或 `targetUnit`；否則系統會以「該單位已被使用，請先刪除轉化表相關數據後再更新」拒絕（來源：`PdmUnitDefController.java:52`）。

### 4.3 異常情境 — 試圖刪除被換算表使用的單位

小李想刪除「磅 lb」單位，但換算表中有「lb ↔ kg」一筆轉換規則。他在清單頁勾選 lb 後點批次刪除，系統檢查到 `lb` 仍出現在換算表的 `baseUnit` 或 `targetUnit`，回傳：

> 「部分單位已被使用，請先刪除轉化表相關數據後再刪除」

刪除動作整批回滾，不會發生「部分成功」。小李必須先到「單位轉換維護表」刪除 `lb ↔ kg` 那筆規則，再回來刪除 `lb`（來源：`PdmUnitDefServiceImpl.java:71-98`、`PdmUnitDefController.java:62-65`）。

### 4.4 使用者鍵入錯誤 — 重複的單位代碼

小李想新增單位 `kg`，但系統中已有「公斤 kg」。送出後系統拋出 `RuntimeException("單位代碼 'kg' 已存在")`，由全域例外處理器回傳給前端。**注意**：此處用 RuntimeException 而非框架的 ServiceException，前端可能拿不到結構化錯誤碼（來源：`PdmUnitDefServiceImpl.java:124-126`）。

### 4.5 查詢情境 — 看所有啟用中的單位

採購主管想看現在能用的單位有哪些。前端傳入 `status=true`，系統用 `eq` 過濾，回傳所有啟用且未軟刪除的單位。

### 4.6 規則分流 — 查詢權限未啟用

目前 `/pdm/udf/page` 端點的 `@PreAuthorize('pdm:unit-def:query')` 被註解掉，**任何登入使用者都能查詢**單位定義。新增 / 更新 / 刪除 仍受權限保護（來源：`PdmUnitDefController.java:70`）。詳見 §11。

---

## 5. 操作流程

```
[PDM 人員進入「單位定義維護表」]
  │
  ├─ 分頁查詢 GET /pdm/udf/page
  │    ├─ 權限檢查：未啟用（程式碼已註解）
  │    ├─ 過濾：單位代碼 =、單位名稱 =、狀態 = (deleted=0)
  │    ├─ 選擇欄位：id、unit、unitName、precisionPlaces、status、creator、createTime、updater、updateTime
  │    └─ 回傳分頁結果
  │
  ├─ 新增 POST /pdm/udf/create
  │    ├─ 權限檢查：pdm:unit-def:create
  │    ├─ 唯一性檢查：unit 代碼在未刪除資料中不重複（重複 → RuntimeException）
  │    └─ insert，回傳新 ID
  │
  ├─ 更新 PUT /pdm/udf/update/{id}
  │    ├─ 權限檢查：pdm:unit-def:update
  │    ├─ 唯一性檢查：新 unit 代碼（排除自己）不可重複
  │    ├─ 取舊資料 → 若 ID 不存在 → 回傳 false → Controller 回 error "該單位已被使用..."
  │    ├─ 檢查舊 unit 是否被換算表使用
  │    │    └─ 是 → 回傳 false → Controller 回 error
  │    └─ 否 → updateById，回傳 true
  │
  └─ 批次刪除 DELETE /pdm/udf/delete  (body: [1,2,3])
       ├─ 權限檢查：pdm:unit-def:delete
       ├─ 取所有 ids 對應的 unit 代碼
       ├─ 若無記錄 → 回 true（視為成功）
       ├─ 在換算表查任何一個 unit 是否出現在 baseUnit / targetUnit
       │    └─ 是 → 回 false → Controller 回 error "部分單位已被使用..."
       └─ 否 → deleteBatchIds（軟刪除），回 true
```

### 跨表保護關係圖

```
       [單位定義維護表]                 [單位轉換維護表]
       pdm_unit_def                    pdm_unit_conv
       ┌──────────────┐                ┌────────────────────┐
       │ unit (kg)    │ ←─────────────│ baseUnit  (kg)     │
       │ unitName     │                │ targetUnit (g)     │
       │ precisionPl. │ ←─────────────│  ratio = 1000      │
       │ status       │                └────────────────────┘
       └──────────────┘
            │
            ├─ 編輯：若 unit 出現在 conv 任一筆 → 整筆禁止
            └─ 刪除：若任一被刪 unit 出現在 conv → 整批禁止
```

---

## 6. 欄位規格

### 6.1 主資料欄位（對應 `pdm_unit_def` 資料表）

| 欄位 | 中文業務語 | 型別 | 必填 | 說明 |
|---|---|---|---|---|
| id | 單位 ID | Long | 系統產生 | 主鍵（PostgreSQL sequence） |
| unit | 單位代碼 | 字串 | （建議必填） | 例：kg、g、L、pc。系統檢查未刪除資料內不重複；本欄位作為單位轉換表的對外鍵 |
| unitName | 單位名稱 | 字串 | （建議必填） | 例：公斤、公克、公升、片 |
| precisionPlaces | 精算位數 | Integer | ✕ | 此單位計算 / 顯示時最多小數位數，由下游引用模組自行套用 |
| status | 狀態 | Boolean | ✕ | true=啟用 / false=停用 |

> ⚠️ **必填強度問題**：`PdmUnitDefReqVO` 上**沒有任何 `@NotEmpty` / `@NotNull` 註解**（來源：`PdmUnitDefReqVO.java:17-52`），代表後端可以接受任意欄位為空。`unit` 雖然唯一性檢查時只在「非空」情況下執行，但空字串仍可寫入。實務上應依賴前端表單做必填。詳見 §11。

### 6.2 系統欄位（繼承自 BaseDO）

建立時間、建立人員、修改時間、修改人員、軟刪除旗標（`deleted`，明確用於過濾）、租戶 ID。

### 6.3 查詢條件（PageReqVO）

| 條件 | 比對方式 |
|---|---|
| 單位代碼 | 等於 |
| 單位名稱 | 等於 |
| 狀態 | 等於 |

> 注意：**單位代碼 / 名稱都是等於比對，不是模糊比對**（與其他基礎資料模組的 like 不同）（來源：`PdmUnitDefServiceImpl.java:105-107`）。詳見 §11。

### 6.4 驗證規則摘要

| 欄位 | 規則 |
|---|---|
| unit | 未刪除資料中唯一（程式邏輯，非 DB unique constraint） |
| 其他 | 後端不做必填／格式驗證 |

### 6.5 跨表保護規則

| 行為 | 觸發條件 | 動作 |
|---|---|---|
| 更新 | 舊 unit 代碼出現在 `pdm_unit_conv` 任一未刪除記錄的 baseUnit 或 targetUnit | 整筆更新被拒絕，回友善訊息 |
| 批次刪除 | 任一待刪除 unit 出現在 `pdm_unit_conv` 任一未刪除記錄的 baseUnit 或 targetUnit | 整批刪除被拒絕，回友善訊息 |

---

## 7. 商業邏輯

### 7.1 唯一性檢查

`validateUnitUnique(unit, excludeId)`：

- 條件：`unit = ?` AND `deleted = 0`
- 更新時排除自身 ID
- 若存在符合條件的記錄，拋 `RuntimeException("單位代碼 'xxx' 已存在")`

**問題點**：

1. 使用 `RuntimeException` 而非框架的 `ServiceException` — 前端無結構化錯誤碼可比對
2. 訊息字面含使用者輸入的單位代碼字串 — 若代碼包含特殊字元，可能被前端誤渲染（XSS 風險低，但需注意）

### 7.2 更新流程的「鎖定」邏輯

```
1. 新代碼唯一性檢查
2. 查舊資料 → 不存在 return false
3. 用舊代碼查換算表 → 有使用 return false
4. 否則 updateById（連同欄位 status / precisionPlaces / unitName / unit 都更新）
```

**業務語意上的問題**：

- 若單位已被換算表使用，連停用（status=false）都不行，這通常不是預期行為（停用不應影響歷史換算規則）
- 若想改名稱或精算位數，這些都不會影響換算規則（baseUnit 用的是 unit 代碼），但仍會被擋

詳見 §11。

### 7.3 批次刪除流程

```
1. 取所有 ids 對應的 unit 代碼
2. 若 ids 全不存在 → return true（視為成功，不報錯）
3. 在換算表用 in (units) 條件查 baseUnit 或 targetUnit
4. 有匹配 → return false（整批失敗）
5. 否則 deleteBatchIds（軟刪除）
```

**問題點**：

- 「全不存在 → return true」與「部分被使用 → return false」的回傳語意不對稱，前端難以判斷實際結果
- LambdaQueryWrapper 的 `.eq(...).or().in(...)` 寫法在 MyBatis-Plus 上**很容易產生非預期的 SQL**（or 結合律），需驗證實際 SQL 是否如預期（見 §11）

### 7.4 查詢

- 過濾條件：unit、unitName、status 三個欄位都用 `eq`
- 強制條件：`deleted = 0`（過濾軟刪除）
- 選擇欄位：明確 select 出 9 個欄位，**不回傳 deleted、tenantId**
- 沒有排序語句 — 順序由資料庫實作決定

---

## 8. 使用角色與權限

| 角色 | 可看資料 | 可操作 | 對應權限字串 |
|---|---|---|---|
| PDM 維護人員（基礎資料維護角色） | 全部 | 查詢、新增、編輯、刪除 | `pdm:unit-def:create`、`update`、`delete`（`query` 目前未啟用） |
| 其他所有登入使用者 | 全部（因 query 權限被註解） | 僅查詢 | 任何已登入 |
| 一般使用者（透過下拉引用） | 透過食材維護等模組的單位下拉 | 無編輯權 | — |

> ⚠️ **查詢權限被註解** — 任何登入使用者都能讀取單位定義清單。這對基礎資料而言通常無敏感性，但需與 PM 確認是刻意還是疏漏（見 §11）。

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節，**待前端對照**。從 API 與欄位可推得的最小頁面組成：

- 上方查詢列：單位代碼（文字 / 等值）、單位名稱（文字 / 等值）、狀態（啟用 / 停用 / 全部）、查詢／重置按鈕
- 工具列：新增、批次刪除（多選後啟用）
- 表格：ID、單位代碼、單位名稱、精算位數、狀態（啟用 / 停用）、建立人員、建立時間、修改人員、修改時間、操作（編輯）
- 編輯／新增 Modal：單位代碼（必，前端做必填）、單位名稱（必，前端做必填）、精算位數（數字，建議限制 0–10）、狀態（switch）
- 刪除 / 編輯被擋下時：直接顯示後端回傳的中文訊息，並引導使用者去「單位轉換維護表」處理

> 注意：無「匯出 Excel」端點，前端若要匯出需自行打包前端表格資料。

---

## 10. 功能範圍

### 10.1 包含的功能

- 單位定義的 C、U、D（建立、更新、批次刪除）
- 分頁查詢（含 unit、unitName、status 過濾）
- 單位代碼唯一性檢查
- 更新／刪除時的「被單位轉換表使用」跨表保護

### 10.2 預留但尚未實作

- **單筆 get-by-id 端點**：其他模組常見的 `/get?id=` 在本功能不存在
- **匯出 Excel**：其他基礎資料維護都有，本功能沒有
- **查詢權限**：`@PreAuthorize` 已寫好但被註解，未啟用
- **VO 必填驗證**：ReqVO 上沒有 `@NotEmpty` / `@NotNull`，全靠前端
- **錯誤碼結構化**：唯一性檢查用 RuntimeException，更新／刪除用 magic number `1`，未對應 `ErrorCodeConstants`

### 10.3 不包含

- 單位之間的換算係數（屬於 [單位轉換維護表]）
- 食材 / 食譜 / 採購單上的單位選擇與儲存（屬於各自模組）
- 精算位數的實際套用（由下游引用此單位的模組自行讀取後決定）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| update 邏輯是否過嚴？被換算表使用的單位連停用 / 改名稱 / 改精算位數都不行 | 業務上停用不會破壞歷史換算規則；改名稱在當前設計會破壞（因為 conv 表存的是代碼字串）；但改精算位數 / 狀態應該無關 | `PdmUnitDefServiceImpl.java:57-60` |
| 更新時是否應限制只能改 unitName / precisionPlaces / status，禁止改 unit 代碼？ | 若 unit 代碼是換算表的對外鍵，改名就會孤兒；當前設計是「整筆禁止」而非「鎖定欄位」 | `PdmUnitDefServiceImpl.java:62-67` |
| 為何用 RuntimeException 而非框架 ServiceException？ | 與框架慣例不符，前端拿不到結構化錯誤碼；應改為 `exception(UNIT_DEF_CODE_DUPLICATE)` 形式 | `PdmUnitDefServiceImpl.java:125` |
| 為何 Controller 用 `CommonResult.error(1, "...")` 的 magic number 1？ | 錯誤碼 1 可能與其他模組撞號，且訊息硬編碼難多語化 | `PdmUnitDefController.java:52、63` |
| 為何查詢權限被註解？ | 是疏漏還是刻意？基礎資料若供下拉使用，可能想對全使用者開放 | `PdmUnitDefController.java:70` |
| 是否需 `unit` 與 `unitName` 必填（後端強制）？ | 目前 ReqVO 無 `@NotEmpty`，可寫入空字串導致髒資料 | `PdmUnitDefReqVO.java:17-52`（無驗證註解） |
| 查詢為何用 `eq` 而非 `like`？其他基礎資料模組都是 like | 使用者要找代碼含 `g` 的單位（g、mg、kg）無法做到 | `PdmUnitDefServiceImpl.java:105-106` |
| 是否需單筆 get-by-id 端點？ | 編輯前的「載入單筆」前端用 page 結果做不易，通常會有 get | Controller 無此端點 |
| 是否需匯出 Excel？ | 其他基礎資料維護都有 | Controller 無此端點 |
| 批次刪除「全不存在 → return true」是否合理？ | 使用者可能會誤以為刪除成功，但實際什麼都沒發生 | `PdmUnitDefServiceImpl.java:74-75` |
| 換算表的 or 條件 SQL 是否正確？ | `.eq(...).or().in(...)` 在 MyBatis-Plus 容易與其他條件結合錯誤；本程式碼有同時放 `.in baseUnit` `.or()` `.in targetUnit`，但前面還有 `.eq deleted=0`，可能變成 `deleted=0 AND in(base) OR in(target)`（targetUnit 跳過 deleted 過濾） | `PdmUnitDefServiceImpl.java:84-88、134-137`，需手動跑一次驗證 SQL |
| 精算位數是否需要合理範圍（0–10）約束？ | 目前可寫入任意整數甚至負數 | `PdmUnitDefDO.java:30`（無 @Min/@Max） |
| 「狀態」型別與餐食類型不一致（Boolean vs String + Dict） | PDM 內基礎資料無統一狀態表達 | `PdmUnitDefDO.java:33` vs `MealTypeDO.java:47` |
| URL 路徑 `/pdm/udf` 與其他模組命名不一致 | 短碼 udf 不直觀；長期應對齊為 `/pdm/unit-def` | `PdmUnitDefController.java:31` |
| 是否要把「單位代碼鎖定編輯」做成 DB unique constraint？ | 程式邏輯檢查可能在高併發下失靈 | `PdmUnitDefServiceImpl.java:116-128`（純應用層） |
