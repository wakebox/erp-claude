# PRD｜PDM — 單位轉換維護表

> 來源：逆向自 `kingmaker-module-pdm` 後端程式碼（`controller/admin/unitconv/`、`service/unitconv/`、`dal/dataobject/unitconv/`、`dal/mysql/unitconv/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣總部的 **PDM 人員**。採購用「箱」「公斤」下單，倉儲用「公斤」「公克」收料，營養成分標示用「公克」「毫克」。一桶 4.5 公升的油等於 4500 毫升、一箱 12 罐汽水等於 12 個單位 — 這些「同一物理量在兩種單位間如何換算」的對應規則由我在此表維護。

### 1.2 我要做什麼

- 為任意兩個已建在「單位定義維護表」的單位建立換算關係（例：kg → g 比率 1000、L → mL 比率 1000、box → pc 比率 12）
- 為每筆換算關係加註備註（例「公斤到克的轉換」）
- 確保同一組合 (baseUnit, targetUnit) 不被重複建立
- 批次刪除已不需要的換算規則
- 提供下游模組查詢換算比率的捷徑（例如：營養成分模組用「該食材的基準單位」查到該基準單位對應到 `g` 或 `mL` 的比率，以做成分含量換算）

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 一組單位對只能有一筆換算規則 | 若 kg→g 同時有 1000 與 1024 兩筆，下游不知該用哪個 |
| 換算比率要支援高精度 | 「磅→公斤」是 0.45359237，整數無法表達 |
| 一改換算比率就要影響所有使用此規則的計算 | 例如修正了「打→個」比率為 12（曾錯填 10），所有歷史顯示應跟著更新 |
| 已建立的換算規則不允許隨意改基準／目標單位字串 | 否則「kg→g 比率 1000」改成「公斤→公克」會找不到對應 |
| 需提供下游程式可呼叫的查詢入口 | 營養成分計算、採購量轉倉儲量需要直接撈比率 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 單位轉換的 CRUD + 分頁查詢 | 維護所有換算關係 |
| (baseUnit, targetUnit) 組合唯一性檢查 | 避免重複規則造成歧義 |
| 內部查詢方法：`selectByBaseAndTarget` | 給其他模組以「基準 + 目標單位」字串查比率 |
| 內部查詢方法：`selectRatioToGOrMl` | 給營養成分換算使用：把任意基準單位換到 `g` 或 `mL` 的比率 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 單位轉換維護表 |
| 所屬模組 | PDM（產品資料管理） |
| 兄弟功能 | 單位定義維護表（強耦合）、營養成分定義維護表、編碼類別維護、編碼項目維護、編碼原則維護、餐食類型維護表、門市分群維護表、物流類型維護表 |
| 主要頁面 | 單位轉換清單頁（含查詢／新增／編輯／批次刪除） |
| 簽核流程 | 無 |

---

## 2. 功能目的

單位轉換是 PDM 的「關係型」基礎資料，搭配 [單位定義維護表] 一起構成 ERP 內所有量綱換算的依據：

1. **量綱跨模組換算**：採購單以「箱」下單，倉儲收貨後以「公斤」紀錄，營養標示以「公克」呈現，沒有換算表就只能下游各自硬編
2. **下游程式的直接查詢入口**：除了維護用的 CRUD 外，Mapper 上有兩支 `@Select` 方法供其他 Service 直接呼叫，最常見的用途是「把任意基準單位的數量換算成公克或毫升」以計算營養成分含量
3. **(baseUnit, targetUnit) 字串對作為主索引概念**：本表的對外鍵不是 ID，而是字串對；這也是為什麼 [單位定義維護表] 的單位代碼一旦被本表引用就被鎖定

---

## 3. 業務邏輯背景

### 3.1 為什麼用單位代碼字串而非單位 ID？

`baseUnit`、`targetUnit` 是字串（如 `kg`、`g`、`mL`），不是指向 `pdm_unit_def.id` 的外鍵。

- 優：下游程式拿到「kg」字串就能直接查比率，不需 join
- 缺：[單位定義維護表] 的單位代碼必須鎖住，否則本表變孤兒（這個保護由單位定義維護表那端的 update / delete 邏輯實作，本表自己不檢查單位是否存在）

來源：`PdmUnitConvDO.java:30-33`、`PdmUnitConvMapper.java:12-13`。

### 3.2 換算的方向性

每筆換算規則只描述「baseUnit → targetUnit」單向關係（`1 baseUnit = ratio × targetUnit`），例如：

- baseUnit=kg, targetUnit=g, ratio=1000 → 表「1 公斤 = 1000 公克」
- baseUnit=L, targetUnit=mL, ratio=1000 → 表「1 公升 = 1000 毫升」

若下游要反向換算（g → kg），由程式自行做 `1/ratio`，**系統不會自動建立反向規則**，也不阻止使用者額外建立反向方向（baseUnit=g, targetUnit=kg, ratio=0.001）— 兩者組合 (baseUnit, targetUnit) 不同，唯一性檢查不會擋。

### 3.3 唯一性約束

唯一性鍵 = (baseUnit, targetUnit) 組合（在未刪除資料中）。

- (kg, g) 第一筆建立後，第二筆 (kg, g) 會被拒絕
- (kg, g) 與 (g, kg) 視為兩個不同組合，皆可建
- (kg, g) 與 (KG, G) 因字串大小寫不同，目前**會被視為兩筆**（程式碼用 `eq` 比對，PostgreSQL 預設區分大小寫）

### 3.4 ratio 用 BigDecimal

`ratio` 是 `BigDecimal`，無位數限制，可表達高精度（例：磅→公斤 0.45359237）。**但 VO 上沒有 `@Digits` 或 `@DecimalMin` 約束**，可寫入 0、負數、極大值（見 §11）。

### 3.5 Mapper 上的兩支 @Select 是給「誰」用的？

`PdmUnitConvMapper.java` 有兩支 raw SQL 方法：

| 方法 | 用途推測 |
|---|---|
| `selectByBaseAndTarget(baseUnit, targetUnit)` | 給呼叫端用兩個字串查比率；典型用例：採購量 → 倉儲量、倉儲量 → 食譜用量 |
| `selectRatioToGOrMl(baseUnit)` | 給營養成分計算用：傳入食材的基準單位，回傳此單位轉到 `g` 優先、否則 `mL` 的比率（SQL 內 ORDER BY `(target_unit = 'g') DESC` 表優先選 g） |

注意 `selectByBaseAndTarget` **不過濾 deleted**，可能撈到已刪除的記錄；`selectRatioToGOrMl` 也沒過濾 deleted（見 §11）。

### 3.6 與框架慣例的偏離

與 [單位定義維護表] 類似，本功能有幾處不對齊慣例：

1. 唯一性檢查拋 `RuntimeException("基準單位和換算單位組合已存在")` 而非 `ServiceException` + ErrorCode（`PdmUnitConvServiceImpl.java:79`）
2. 沒有 `@Transactional`（與 [單位定義維護表] 有不同；本表更新只動一張表，可接受）
3. URL 與 Controller 路徑用 hyphen 完整字（`/pdm/unit-conv`），與 [單位定義維護表] 的 `/pdm/udf` 短碼不一致
4. 刪除完全沒有「被使用即鎖定」檢查 — 反向（單位定義 → 單位轉換）有跨表保護，本表 → 下游使用者並沒有
5. 沒有單筆 get 端點，沒有匯出 Excel

### 3.7 同套件下還有一個 `UnitConversionDO`

`dal/dataobject/unitconv/` 內除了 `PdmUnitConvDO` 還有一個 `UnitConversionDO` 類別，是給 Mapper 那兩支 `@Select` 用的結果接收 POJO（猜測只有 ratio 欄位）。功能上等同於 DTO，不對應實體表。

---

## 4. 情境說明

### 4.1 正常流程 — 新增「箱→片」換算

採購用「箱」下單某款起司片（一箱 144 片），倉儲入庫後要轉成「片」。PDM 人員小李進入「PDM > 單位轉換維護表」，點「新增」，填入：

- 基準單位：box
- 換算單位：pc
- 轉換比率：144
- 備註：起司片一箱裝 144 片

送出後系統檢查 (box, pc) 在未刪除資料中不存在，建立成功。之後採購單收料時系統可呼叫 `selectByBaseAndTarget('box', 'pc')` 拿到 144 做數量換算。

### 4.2 典型業務 — 修正換算比率

主管發現「磅→公斤」原本錯填為 0.5，正確應為 0.45359237。小李在清單頁搜尋 baseUnit=lb，編輯該筆，把 ratio 改為 0.45359237 後送出。系統檢查 (lb, kg) 唯一性（排除自己 ID），通過後更新。**之後所有透過 Mapper 撈這筆比率的計算結果都會跟著修正**，但已寫入歷史單據的數量不會自動回填（見 §11）。

### 4.3 異常情境 — 重複的單位對

新進人員不知「kg→g」已存在，又新增 baseUnit=kg、targetUnit=g、ratio=1000。系統拋出 `RuntimeException("基準單位和換算單位組合已存在")`，由全域例外處理器回前端。**注意**：此處未用框架 ServiceException，前端拿到的可能是通用 500 錯誤而非結構化錯誤碼。

### 4.4 使用者鍵入錯誤 — 漏填 ratio

新增時若忘了填轉換比率，系統回「轉換比率不能為空」（`PdmUnitConvReqVO.java:34` `@NotNull`）。其他欄位（baseUnit、targetUnit、備註）**後端無必填驗證**，理論上可以送出空 baseUnit 配 ratio，建出一筆「空字串對任何字串」的髒資料（見 §11）。

### 4.5 規則分流 — 批次刪除完全無保護

批次刪除直接呼叫 `deleteBatchIds`，**不檢查存在性、不檢查下游有沒有在用**。即使這筆 (kg, g) 換算正在被某營養成分計算依賴，刪除後該計算下次就會撈不到比率回傳 null。系統需評估是否要加保護（見 §11）。

### 4.6 查詢情境

主管要看所有跟「公斤」相關的換算規則。前端傳 baseUnit=kg，系統用 `eq` 過濾（**注意是等於，不是 like**），回傳所有以 kg 為基準的換算。若要查 kg 是否也作為 targetUnit（例如 lb→kg），需另外查一次。

---

## 5. 操作流程

```
[PDM 人員進入「單位轉換維護表」]
  │
  ├─ 分頁查詢 GET /pdm/unit-conv/page
  │    ├─ 權限檢查：pdm:unit-conv:query
  │    ├─ 過濾：baseUnit =、targetUnit =、remarks like（deleted=0）
  │    ├─ 選擇欄位：id, baseUnit, targetUnit, remarks, ratio, creator/createTime/updater/updateTime
  │    └─ 回傳分頁
  │
  ├─ 新增 POST /pdm/unit-conv/create
  │    ├─ 權限檢查：pdm:unit-conv:create
  │    ├─ 必填驗證：ratio（其他欄位無驗證）
  │    ├─ 唯一性檢查：(baseUnit, targetUnit) 在未刪除資料中不存在
  │    └─ insert，回傳新 ID
  │
  ├─ 更新 PUT /pdm/unit-conv/update/{id}
  │    ├─ 權限檢查：pdm:unit-conv:update
  │    ├─ 必填驗證：ratio
  │    ├─ 唯一性檢查：(新 baseUnit, 新 targetUnit) 排除自己 ID 不重複
  │    └─ updateById（會更新所有欄位，含 baseUnit / targetUnit / ratio / remarks）
  │
  └─ 批次刪除 DELETE /pdm/unit-conv/delete  (body: [1,2,3])
       ├─ 權限檢查：pdm:unit-conv:delete
       └─ deleteBatchIds（無存在性、無下游使用檢查）

[其他模組透過 Mapper 直接呼叫]
  │
  ├─ selectByBaseAndTarget(baseUnit, targetUnit)
  │    └─ SELECT ratio FROM pdm_unit_conv WHERE base_unit=? AND target_unit=?
  │       （注意：未過濾 deleted）
  │
  └─ selectRatioToGOrMl(baseUnit)
       └─ SELECT ratio
          FROM pdm_unit_conv
          WHERE base_unit=? AND target_unit IN ('g','ml')
          ORDER BY (target_unit='g') DESC, target_unit
          LIMIT 1
          （注意：未過濾 deleted；'ml' 為小寫，與業界常用 mL 大小寫不同）
```

---

## 6. 欄位規格

### 6.1 主資料欄位（對應 `pdm_unit_conv` 資料表）

| 欄位 | 中文業務語 | 型別 | 必填 | 說明 |
|---|---|---|---|---|
| id | 換算規則 ID | Long | 系統產生 | 主鍵（PostgreSQL sequence） |
| baseUnit | 基準單位 | 字串 | （建議必填） | 對應 [單位定義] 的 unit 代碼字串 |
| targetUnit | 換算單位 | 字串 | （建議必填） | 對應 [單位定義] 的 unit 代碼字串 |
| ratio | 轉換比率 | BigDecimal | ✅ | 1 baseUnit = ratio × targetUnit |
| remarks | 備註 | 字串 | ✕ | 說明此換算的用途 |

### 6.2 系統欄位（繼承自 BaseDO）

建立時間、建立人員、修改時間、修改人員、軟刪除旗標 `deleted`、租戶 ID。

### 6.3 查詢條件（PageReqVO）

| 條件 | 比對方式 |
|---|---|
| 基準單位 | 等於 |
| 換算單位 | 等於 |
| 備註 | 模糊比對 |

### 6.4 唯一性約束

(baseUnit, targetUnit) 組合在未刪除資料中唯一。

### 6.5 驗證規則摘要

| 欄位 | 規則 | 錯誤訊息 |
|---|---|---|
| ratio | 不可為 null | 「轉換比率不能為空」 |
| 其他 | 後端無驗證 | — |

---

## 7. 商業邏輯

### 7.1 新增 / 更新

1. 必填驗證：ratio
2. 唯一性檢查：(baseUnit, targetUnit) 排除自己 ID 在未刪除資料中不存在
3. 重複 → 拋 `RuntimeException("基準單位和換算單位組合已存在")`
4. 否則 insert / updateById

**沒有的檢查**：

- baseUnit / targetUnit 是否真存在於 [單位定義維護表]（後端不檢查；可建立指向不存在單位的孤兒換算）
- ratio 是否為正（可寫入 0 或負數）
- baseUnit ≠ targetUnit（可建立 kg→kg 的怪異換算）

### 7.2 批次刪除

直接呼叫 `deleteBatchIds`，無任何前置檢查。

### 7.3 查詢

- 過濾：baseUnit / targetUnit 等值、remarks 模糊
- 強制：`deleted = 0`
- 明確 select 9 個欄位，不回 deleted / tenantId
- 無排序語句

### 7.4 給下游使用的查詢方法

| 方法 | SQL 行為 | 風險 |
|---|---|---|
| `selectByBaseAndTarget` | `WHERE base_unit=? AND target_unit=?` | 未過濾 deleted；若兩個都軟刪了仍可能撈到 |
| `selectRatioToGOrMl` | `WHERE base_unit=? AND target_unit IN ('g','ml') ORDER BY (='g') DESC LIMIT 1` | 未過濾 deleted；`'ml'` 硬編小寫（業界與 [單位定義] 可能用 `mL` 大小寫不同會撈不到） |

兩支方法都用原生 `@Select`，沒有用 MyBatis-Plus 的 wrapper 加上 deleted 過濾。

---

## 8. 使用角色與權限

| 角色 | 可看資料 | 可操作 | 對應權限字串 |
|---|---|---|---|
| PDM 維護人員 | 全部 | 查詢、新增、編輯、批次刪除 | `pdm:unit-conv:query`、`create`、`update`、`delete` |
| 一般使用者 / 下游程式 | 透過 Mapper 內部呼叫，無端點權限 | 呼叫換算 | — |

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節，**待前端對照**。建議：

- 上方查詢列：基準單位（下拉，來源：單位定義）、換算單位（下拉）、備註（文字 / like）
- 工具列：新增、批次刪除
- 表格：ID、基準單位、換算單位、轉換比率（建議顯示「1 kg = 1000 g」這種人類可讀格式）、備註、建立人 / 時間、修改人 / 時間、操作（編輯）
- 編輯 / 新增 Modal：
  - 基準單位（下拉，從單位定義抓啟用中的）
  - 換算單位（下拉，從單位定義抓啟用中的）
  - 轉換比率（必，數字，建議限制正數）
  - 備註

> 「baseUnit / targetUnit 是否真存在於單位定義」**前端應強制下拉選擇**以代替後端缺失的檢查。

---

## 10. 功能範圍

### 10.1 包含的功能

- 換算規則的 C、U、D（建立、更新、批次刪除）
- 分頁查詢（baseUnit / targetUnit 等值、remarks 模糊）
- (baseUnit, targetUnit) 組合唯一性檢查
- 兩支內部查詢方法供下游使用

### 10.2 預留但尚未實作

- **單筆 get-by-id 端點**
- **匯出 Excel**
- **錯誤碼結構化**：用 RuntimeException 而非 ServiceException
- **baseUnit / targetUnit 必填驗證**
- **指向有效單位的檢查**
- **下游使用保護**：刪除時不檢查是否仍被使用
- **內部查詢方法的 deleted 過濾**

### 10.3 不包含

- 單位本身的維護（屬於 [單位定義維護表]）
- 食材 / 食譜上的單位欄位（屬於各自模組）
- 採購量轉倉儲量、營養成分含量計算（屬於各業務模組，會呼叫本表的 Mapper 取比率）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| baseUnit / targetUnit 是否需檢查存在於 [單位定義維護表]？ | 目前可建指向不存在單位的孤兒換算 | `PdmUnitConvServiceImpl.java:22-30`（無檢查） |
| ratio 是否需限制為正數？ | 目前可寫入 0 / 負數 | `PdmUnitConvReqVO.java:34`（只 @NotNull） |
| 是否禁止 baseUnit == targetUnit？ | 目前可建立 kg→kg ratio=1 的無意義規則 | 無檢查 |
| 大小寫差異是否要正規化？ | (kg, g) 與 (KG, G) 目前視為兩筆 | `PdmUnitConvServiceImpl.java:70-81` |
| 為何用 RuntimeException 而非框架 ServiceException？ | 與框架慣例不符 | `PdmUnitConvServiceImpl.java:79` |
| 批次刪除是否需「下游引用即禁止」？ | 目前無保護，刪掉常用換算後下游計算會 null | `PdmUnitConvServiceImpl.java:44-48` |
| `selectByBaseAndTarget` 是否該過濾 deleted？ | 未過濾，可能撈到軟刪除記錄 | `PdmUnitConvMapper.java:12-13` |
| `selectRatioToGOrMl` 是否該過濾 deleted？ | 同上 | `PdmUnitConvMapper.java:15-23` |
| `selectRatioToGOrMl` 中 `target_unit IN ('g', 'ml')` 大小寫硬編是否會與 [單位定義] 的代碼大小寫不一致？ | 業界常見 mL 大寫；若單位定義建為 `mL` 會撈不到 | `PdmUnitConvMapper.java:19` |
| 反向換算（g→kg）是否需自動建立或允許獨立建立？ | 目前完全靠人工，且兩個方向獨立維護易不一致 | 程式邏輯無關聯 |
| 修改既有 ratio 是否該留歷史版本？ | 目前覆蓋寫入，無法追溯「上個月 kg→g 是 1000，這個月改成 1024」 | `PdmUnitConvServiceImpl.java:33-42` |
| Mapper 上的 `UnitConversionDO` 用途為何？是否應改為共用 DTO？ | 與 PdmUnitConvDO 並存令人困惑 | `PdmUnitConvMapper.java:5` import |
| 「換算比率」是否需「適用日期區間」？ | 例如匯率型換算可能會隨日期變動，目前無此欄位 | DO 欄位列表 |
| 是否需單筆 get-by-id？ | 編輯前的載入單筆 | Controller 無此端點 |
| `creator` / `updater` 欄位在 VO 中宣告但未由前端傳入 — 是 BaseDO 自動填？ | 需確認框架行為 | `PdmUnitConvReqVO.java:43、50` |
