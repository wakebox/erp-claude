# PRD｜採購管理 — 廠商報價維護作業

> 來源：逆向自 `kingmaker-module-pmm` 後端程式碼（`controller/admin/vqm/`、`service/vqm/VendorQuoteMaintenanceServiceImpl.java`、`dal/dataobject/vqm/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **採購人員 / 採購助理**。前面已經建好「廠商資料」（PRD #27）— 那是廠商身分。現在我要為已建檔的廠商，**逐品號（食材或包材）建立報價單**：

- 這家廠商賣什麼品號？
- 每樣品號的廠商品名是什麼（廠商自己的命名）？
- 採用什麼包裝（一包多少、什麼單位）？
- 最新報價是多少（NTD/包裝）？
- 換算成 NTD/kg 或 NTD/l 是多少？
- 換算成 NTD/件 是多少？
- 適用於哪些門店、用什麼物流類型、採購前置幾天、MOQ 最少訂幾包？
- 有效日期區間？

建好後送簽核，核准後這份「廠商-品號-價格」對應就可被「採購單」「需求預測（#24 用 prodCode 撈最新報價）」「物料需求行事曆（#25 / #30）」引用。

### 1.2 我要做什麼

- 為某家廠商建立報價單（單頭 + 多筆品號明細）
- 編輯既有報價（含明細）
- 軟刪除報價單
- 變更單據狀態（給 BPM 用）
- 分頁查詢、待簽分頁、單筆查詢
- 取下拉：單據編號清單、本表內已維護廠商代號、廠商主檔內全部廠商代號
- 根據品號查報價（給包材維護的「貨源明細」用）
- **三個自動計算 API**：
  - 最新報價 NTD/kg.l（包裝報價 ÷ 包裝計數）
  - 單一計數報價 NTD（包裝報價 ÷ 包裝計數）
  - 單一計數計量 g/ml（包裝計量 × 單位換算比率 ÷ 包裝計數）
- Excel 模板匯出 / 匯入

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 一張單能放多筆品號 | 同一家廠商通常一次更新十幾甚至上百品項 |
| 系統幫我自動算單位換算 | 包裝報價 4500 元 / 一箱 15 公斤 → 我不要每筆都自己算 NTD/kg |
| 報價有效日期區間 | 不同時段可有不同報價（漲價、優惠） |
| 適用門店範圍 | 同一品號不同門店可能用不同物流類型、不同 MOQ |
| 預設物流類型 | 下游採購單自動帶 |
| 採購前置日、保存日、MOQ | 採購要知道下單到收貨要幾天、商品幾天會過期、最少要訂幾包 |
| 走簽核 | 與廠商相關的金額異動需審核 |
| Excel 匯入 | 大批量初始化 / 廠商統一漲價時批量更新 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 報價單 CRUD（單頭 + 明細） | 一站式維護 |
| 廠商代號下拉（從 #27 撈） | 防止輸入不存在的廠商 |
| 自動計算（3 個 API） | 減少人工錯誤 |
| 簽核流程整合 | 金額異動審核 |
| 已歸檔保護 | 鎖定定案 |
| 依品號查報價 | 包材 / 食材維護引用 |
| Excel 匯出 / 匯入 | 大量資料遷移 / 批量更新 |
| 給 #24（需求預測）用的查詢方法 | 自動取最新報價 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 廠商報價維護作業 |
| 所屬模組 | PMM（採購管理） |
| 兄弟功能 | 廠商資料維護作業（#27）、請購計劃管理（#29）、原料物需求行事曆（#30）、請購單管理（#31）、報價管理（#32）、採購單管理（#33）、結轉驗收（#34）、驗收確認（#35） |
| 主要頁面 | 報價單編輯頁、單頭分頁、待簽分頁、Excel 匯入 |
| 簽核流程 | 有：BPM 流程綁定 |

---

## 2. 功能目的

廠商報價維護作業是「廠商主檔（#27）」與「品號級採購活動」之間的**價格橋樑**：

1. **記錄歷次報價** — 每張報價單獨立一份，可保留歷史
2. **以「廠商-品號-有效日期」為核心** — 下游用這三維度撈「當下最新報價」
3. **自動計算 3 種單位轉換** — 因為下游有不同需求：採購單看包裝、需求預測看 kg/l、配方分析看件 / g
4. **支援「適用門市」「物流類型」「採購前置日」「保存日」「MOQ」** — 不只是價格，連物流條件都一起記
5. **簽核流程** — 金額類異動高風險

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `pmm_vendor_quote_maintenance`（單頭 / `PmmVendorQuoteMaintenanceDO`） | 報價單頭：單據編號、單據狀態、廠商代號、廠商名稱、主旨、幣別、報價有效起訖、流程實例 ID |
| `pmm_vendor_quote_maintenance_detail`（明細 / `PmmVendorQuoteMaintenanceDetailDO`） | 每品號的：項次、類別、品號、廠商品名、廠商包裝單位 ID、最新報價(NTD/包裝)、最新報價(NTD/單位)、單一包裝量、單位 ID、單一規格、單一規格單位、狀態、建立人員部門、適用門市 ID、適用門市、預設物流類型、採購前置日期、保存日期、MOQ |

### 3.2 「最新報價」的三層換算

明細表記錄三組數值（同一品號，不同呈現方式）：

| 欄位 | 含義 | 計算公式 |
|---|---|---|
| `latestQuotePerPack` | 最新報價 NTD/包裝 | 人工輸入 |
| `latestQuotePerKgL` | 最新報價 NTD/kg 或 NTD/l | `latestQuotePerPack ÷ singlePackCount` |
| `singleCountQuote`（已被註解掉） | 單一計數報價 NTD/件 | `latestQuotePerPack ÷ singlePackCount` |
| `singleCountMeasure` | 單一規格 g/ml | `singlePackQuantity × ratio ÷ singlePackCount` |

> ⚠️ 觀察：`latestQuotePerKgL` 與 `singleCountQuote` 用**完全相同的公式**（`latestQuotePerPack ÷ singlePackCount`） — 程式碼上 `calculateUnitQuote` 與 `calculateSingleCountQuote` 兩個方法做一樣的事（來源：`VendorQuoteMaintenanceServiceImpl.java:526-544`）。差別應該是**輸入語意**（前者 singlePackCount 是 kg/l、後者是件），但程式不區分（見 §11）。

> ⚠️ `singleCountQuote` 欄位本身**被註解掉**（`PmmVendorQuoteMaintenanceDetailDO.java:70-71`） — DB 沒這欄但 Service 有計算端點。前端拿到計算結果只能放在 RespVO 或前端 state，無法持久化（見 §11）。

### 3.3 單位轉換的查詢

`calculateSingleCountMeasure(singlePackQuantity, singlePackUnit, singlePackCount)`：

1. 查 `pdm_unit_conv` 的 `selectByBaseAndTarget(singlePackUnit, "g")`
2. 查不到 g → 查 `selectByBaseAndTarget(singlePackUnit, "ml")`
3. 都查不到 → 拋 `UNIT_CONVERSION_RATIO_NOT_FOUND`
4. 公式：`(singlePackQuantity × ratio) ÷ singlePackCount`，scale=2 HALF_UP

來源：`VendorQuoteMaintenanceServiceImpl.java:547-570`。

注意：

- **依賴 #21 單位轉換維護表**，需先建好 unit → g / ml 的換算關係
- 因為 #21 的查詢方法 `selectByBaseAndTarget` 未過濾 deleted，可能撈到已軟刪除的換算規則（已在 #21 §11 列出）
- 'g' 與 'ml' 大小寫硬編

### 3.4 適用門市範圍

`useStoreRegionId` 為字串欄位，儲存「適用門市 ID 清單」（推測逗號分隔）；`useStoreRegion` 為對應的中文名稱。下游採購單依此判斷某店是否能用此報價。

**問題點**：

- 純字串無格式約束
- 沒有跨表 join 保證 ID 真存在
- 多個 ID 的儲存方式未文件化

### 3.5 簽核流程與已歸檔保護

與 #27 類似：

- 表單路徑：可能是 `FormPathUniqueEnum.VENDOR_QUOTE`（未列出，但 import 有 `FormPathUniqueEnum`）
- 建立時啟動 BPM 流程
- 變更狀態用獨立端點 `/update-status/{id}`，**body 是 `UpdateStatusReqVO`**（與 #27 的 PathVariable 不一致）
- 已歸檔保護：`VENDOR_ARCHIVED_CANNOT_UPDATE`（推測同樣常數，見 §11）

### 3.6 給 #24 用的最新報價查詢

#24（食材需求預測 BOM）會用 `selectLatestVendorQuotesByProdCodesAndStoreId(prodCodes, storeId, demandWeekStartTime)` 拉最新報價，邏輯應該是：

- 同一 prodCode 可能有多筆報價（不同有效期）
- 同一 prodCode 在同 storeId 上可能有多筆（不同廠商）
- 取「有效期 ≤ demandWeekStartTime ≤ 有效期結束」且「最新」的一筆

具體 SQL 邏輯在 `pdm` 模組（`PdmProductRecipeRelMapper`），不在本功能 Mapper。

### 3.7 與框架慣例的偏離

| 項目 | 偏離點 |
|---|---|
| 路徑 `/pmm/vqm` | 短碼，與其他模組不一致 |
| 權限名 `pmm:vendor-quote-maintenance:*` | 比 `pmm:mfr-basic-final:*` 更可讀，但仍是英文表名變形 |
| 更新採 body 帶 id（`PUT /update`） | 與 #27 的 PathVariable 不一致 |
| 變更狀態用 body | 與 #27 的 PathVariable 不一致 |
| 主表 `@NotNull` 註解掉 | 與 #27 相同問題 |

### 3.8 跨模組依賴

- 廠商代號 `mfrId`：對應 `pmm_mfr_basic_final.mfrId`（#27）
- 品號 `prodCode`：對應 `pdm_ingredient_specs` / `pdm_packing_materials_dtl`（PDM 模組）
- 單位 ID：對應 `pdm_unit_def`（#20）
- 單位換算：依賴 `pdm_unit_conv`（#21）
- 物流類型：依賴 `pdm_logistics_type`（#23）
- 門市範圍：依賴中繼 API（`BurgerKingStoreClient`、區域層級）

報價維護幾乎是 PMM 內**最依賴 PDM 主檔**的功能。

---

## 4. 情境說明

### 4.1 正常流程 — 為「冷凍肉商」建立報價單

採購人員王小姐要為「FROZEN-MEAT-001」建立新季度報價單（有效期 2026-06-01 ~ 2026-08-31）：

1. 進入報價維護編輯頁
2. 主表：
   - 廠商代號：FROZEN-MEAT-001（下拉，來源：/basic-mfr-ids）
   - 廠商名稱：自動帶
   - 主旨：2026 Q3 牛肉類報價
   - 幣別：TWD
   - 報價有效起訖：2026-06-01 ~ 2026-08-31
3. 明細第 1 行（牛肉餅）：
   - 品號：LB-04
   - 廠商品名：BK 牛肉餅 LB-04
   - 包裝單位：箱（unitDef ID）
   - 最新報價(NTD/包裝)：4500
   - 單一包裝量：15（公斤 / 箱）
   - 單位 ID：kg
   - 單一規格：100
   - 單一規格單位：g
   - 點「自動計算」按鈕 →
     - calculateUnitQuote(4500, 15) = 300（NTD/kg）→ 寫入 `latestQuotePerKgL`
     - calculateSingleCountMeasure(15, "kg", 150) 需要件數，前端動態
   - 適用門市：北一區所有店、台北市
   - 預設物流類型：週一三五直送
   - 採購前置日：3 天
   - 保存日：14 天
   - MOQ：5 箱
   - 狀態：啟用
4. 明細第 2 行（雞肉塊）：略
5. POST /create
6. 系統：
   - 主表 `@NotNull` 已被註解，不檢查（NPE 風險）
   - signCode = generateSignCode
   - processStatus = 「待處理」
   - insert 主表 → vqmId
   - 批次 insert 明細（setVendorQuoteId(vqmId)）
   - 啟動 BPM 流程

### 4.2 典型業務 — 廠商統一漲價，批量更新

冷凍肉商 7 月漲價 5%。王小姐：

1. 匯出現有報價（前端取明細，前端做漲價計算）
2. 進入編輯頁，點「更新報價」
3. PUT /update（body 帶單頭 + 全部明細，價格已 ×1.05）
4. 系統：
   - 檢查存在 + 未歸檔
   - 軟刪除舊明細
   - 插入新明細
5. 進簽核流程

或者使用「匯入」批次更新：

1. 下載匯入模板
2. 在 Excel 中編輯價格
3. POST /import 上傳
4. 系統解析、創建新報價單（並非更新舊單；新單視為新版本）

### 4.3 異常情境 — 找不到單位換算

某品號的包裝單位是「自訂的 BK 桶」，但 #21 單位轉換維護表沒建立「BK 桶 → g / ml」的換算關係。

呼叫 `/calculate-single-count-measure`：

- `selectByBaseAndTarget("BK桶", "g")` → null
- `selectByBaseAndTarget("BK桶", "ml")` → null
- 拋 `UNIT_CONVERSION_RATIO_NOT_FOUND`，訊息：「找不到單位換算比率」

使用者必須先到 #21 建立換算規則，再回來計算。

### 4.4 異常情境 — 單一包裝量為 0

`calculateSingleCountQuote(latestQuotePerPack, 0)`：

- 偵測 `singlePackCount.compareTo(BigDecimal.ZERO) == 0` → 拋 `SINGLE_PACK_COUNT_CANNOT_BE_ZERO`
- 訊息：「單一包裝計數不能為零」

避免除零異常。

### 4.5 規則分流 — 給包材維護的查詢

包材維護作業（PDM #14）的「貨源明細」要顯示「此包材有哪些廠商報價」：

1. GET /vendor-quote-by-product-page?prodCode=PKG-001
2. 系統撈所有 status=啟用 的 prodCode=PKG-001 的明細
3. 回 `List<PmmVendorQuoteMaintenanceForPmVO>`（明細含廠商資訊）

### 4.6 規則分流 — 用品號查報價（需求預測用）

#24 在試算時拿到品號清單後，呼叫 PDM 端的 Mapper 方法（`selectLatestVendorQuotesByProdCodesAndStoreId`）取最新有效報價：

- 過濾 demandWeekStartTime 落在有效期內
- 同品號取最新
- 同店優先

實際 SQL 邏輯在 PDM 而非本功能，但**資料來源是本表**。

---

## 5. 操作流程

```
[使用者進入「廠商報價維護作業」]
  │
  ├─ 1. 建立 POST /pmm/vqm/create
  │    ├─ 權限：pmm:vendor-quote-maintenance:create
  │    ├─ signCode + processStatus 系統填
  │    ├─ insert 主表 → vqmId
  │    ├─ 批次 insert 明細
  │    └─ 啟動 BPM 流程
  │
  ├─ 2. 更新 PUT /pmm/vqm/update
  │    ├─ body 帶 id
  │    ├─ 檢查存在 + 未歸檔
  │    ├─ 更新主表
  │    ├─ 軟刪除舊明細
  │    └─ 插入新明細
  │
  ├─ 3. 變更狀態 PUT /pmm/vqm/update-status/{id}  body: {processStatus}
  │    └─ 給 BPM 用
  │
  ├─ 4. 批次刪除 DELETE /pmm/vqm/delete  body: List<Long>
  │
  ├─ 5. 取單筆 GET /pmm/vqm/get/{id}
  │    └─ 回主表 + 明細
  │
  ├─ 6. 分頁 / 待簽分頁 GET /pmm/vqm/page、/todo-page
  │
  ├─ 7. 下拉 / 列表 API
  │    ├─ GET /sign-codes（單據編號清單）
  │    ├─ GET /mfr-ids（本表已維護的廠商代號）
  │    └─ GET /basic-mfr-ids（廠商主檔的全部廠商代號）
  │
  ├─ 8. 依品號查 GET /vendor-quote-by-product-page?prodCode=
  │    └─ 給包材維護作業
  │
  ├─ 9. 自動計算 API
  │    ├─ POST /calculate-unit-quote
  │    │   └─ latestQuotePerPack ÷ singlePackCount → NTD/kg.l
  │    ├─ POST /calculate-single-count-quote
  │    │   └─ latestQuotePerPack ÷ singlePackCount → NTD/件
  │    └─ POST /calculate-single-count-measure
  │       └─ singlePackQuantity × ratio(unit→g或ml) ÷ singlePackCount → g/ml
  │
  ├─ 10. 匯出模板 GET /get-import-template
  │
  └─ 11. 匯入 POST /import?file=
       └─ 解析 Excel → 解析主表 + 明細 → 寫入
```

---

## 6. 欄位規格

### 6.1 主表（`pmm_vendor_quote_maintenance`）

| 欄位 | 中文業務語 | 型別 |
|---|---|---|
| id | 主鍵 ID | Long |
| signCode | 單據編號 | 字串 |
| processStatus | 單據狀態 | 字串 |
| mfrId | 廠商代號 | 字串 |
| mfrName | 廠商名稱 | 字串 |
| subject | 主旨 | 字串 |
| moneyType | 幣別 | 字串 |
| quoteEffectDateSt / Ed | 報價有效日期起 / 訖 | LocalDateTime |
| processInstanceId | 流程實例 ID | 字串 |

### 6.2 明細（`pmm_vendor_quote_maintenance_detail`）

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| vendorQuoteId | 主表 ID |
| item | 項次 |
| category | 類別 |
| prodCode | 品號 |
| mfrProductName | 廠商品名 |
| mfrPackUnit | 廠商包裝單位 ID |
| latestQuotePerPack | 最新報價 NTD/包裝 |
| latestQuotePerKgL | 最新報價 NTD/kg 或 NTD/l |
| singlePackCount | 單一包裝量 |
| singlePackCountUnit | 單位 ID |
| singleCountMeasure | 單一規格 |
| singleCountMeasureUnit | 單一規格單位 |
| status | 狀態（停用 0 / 啟用 1） |
| createDepartment | 建立人員部門 |
| useStoreRegionId / useStoreRegion | 適用門市 ID / 名稱 |
| useDeliveryType | 預設物流類型 |
| beforePurchaseDate | 採購前置日期（天） |
| saveDate | 保存日期（天） |
| moq | 最小報價數 |

### 6.3 查詢條件

queryCategory（his/current）、processStatus、signCode IN、createTime 區間、mfrId、processInstanceStatus、taskIds。

### 6.4 自動計算 API 輸入

| API | 輸入 |
|---|---|
| /calculate-unit-quote | `latestQuotePerPack`, `singlePackCount` |
| /calculate-single-count-quote | `latestQuotePerPack`, `singlePackCount` |
| /calculate-single-count-measure | `singlePackQuantity`, `singlePackUnitName`, `singlePackCount` |

---

## 7. 商業邏輯

### 7.1 三個計算公式

```
NTD/kg.l = latestQuotePerPack / singlePackCount        (scale=2 HALF_UP)
NTD/件   = latestQuotePerPack / singlePackCount        (scale=2 HALF_UP)
g/ml    = (singlePackQuantity × ratio) / singlePackCount (scale=2 HALF_UP)

其中 ratio 來自 pdm_unit_conv (singlePackUnit→g 優先、否則→ml)
```

### 7.2 邊界檢查

- 必填參數空 → REQUIRED_PARAM_EMPTY
- singlePackCount = 0 → SINGLE_PACK_COUNT_CANNOT_BE_ZERO
- 找不到單位換算 → UNIT_CONVERSION_RATIO_NOT_FOUND

### 7.3 編輯刪舊插新

與 #27 同樣的策略：軟刪除明細 → 插入新明細。子表 id 變動。

### 7.4 BPM 整合

建立時啟動流程；變更狀態獨立端點。

---

## 8. 使用角色與權限

| 角色 | 可操作 | 對應權限字串 |
|---|---|---|
| 採購人員 | 建立、編輯、刪除、查詢、匯入匯出、變更狀態 | `pmm:vendor-quote-maintenance:create`、`update`、`delete`、`query` |
| 簽核主管 | 待簽分頁 + 簽核 | `query` + BPM 角色 |
| 包材 / 食材維護人員 | 查詢（依品號） | `query` |
| 需求預測 / 採購單 | 透過 Mapper 內部查詢 | — |

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節。建議：

### 9.1 編輯頁

- 主表段：廠商代號（下拉，來源 /basic-mfr-ids）、廠商名稱（自動帶）、主旨、幣別、有效起訖
- 明細表格：每行品號、廠商品名、包裝單位、包裝報價、包裝量、計算按鈕（觸發自動計算）、適用門市（多選下拉）、物流類型（下拉）、前置日、保存日、MOQ、狀態
- 自動計算 widget：填三個值就秀出三個換算結果

### 9.2 分頁

- 條件：單據狀態、單據編號（多選）、建立時間區間、廠商代號（下拉，來源 /mfr-ids 已維護的）
- 表格：單據編號、廠商、主旨、有效起訖、狀態、操作

---

## 10. 功能範圍

### 10.1 包含的功能

- 報價單 CRUD（含明細）
- 三個自動計算 API
- BPM 流程整合
- 已歸檔保護
- 多種下拉 API
- 依品號查報價（給包材維護）
- Excel 模板匯出 / 匯入

### 10.2 預留但尚未實作

- **`singleCountQuote` 欄位被註解**：計算結果無法落 DB
- **`previousQuotePerPack` 被註解**：歷次報價追溯不能直接看「上次價」
- **`singlePackQuantity` / `singlePackUnit` 在 DO 被註解**：但計算 API 仍接受參數
- **計算公式語意混淆**：calculateUnitQuote 與 calculateSingleCountQuote 公式相同
- **適用門市 ID 解析規則**：純字串無格式約束
- **匯入是否走 BPM**：推測不走

### 10.3 不包含

- 廠商主檔（屬於 #27）
- 採購單建立（屬於 #33）
- 報價管理（屬於 #32，疑似不同子模組）
- 單位轉換維護（屬於 #21）
- 物流類型維護（屬於 #23）
- 包材 / 食材本身的維護（屬於 PDM）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| `calculateUnitQuote` 與 `calculateSingleCountQuote` 公式完全相同 | 兩個端點做一樣的事，業務語意應分開（前者單位是 kg/l、後者是件） | `VendorQuoteMaintenanceServiceImpl.java:526-544` |
| `singleCountQuote` 欄位被註解掉 | 計算結果無法持久化，下游撈不到 | `PmmVendorQuoteMaintenanceDetailDO.java:70-71` |
| `previousQuotePerPack` 欄位被註解掉 | 無法追溯「上次價」 | 同上 |
| `singlePackQuantity` / `singlePackUnit` 欄位被註解但 API 仍用 | 計算結果無法落 DB；只能在前端使用 | 同上 |
| `selectByBaseAndTarget` 未過濾 deleted（依賴 #21 的 bug） | 可能撈到軟刪除的單位換算 | `VendorQuoteMaintenanceServiceImpl.java:557-560` |
| 'g' 與 'ml' 大小寫硬編，與 #20 單位定義代碼可能不一致 | 若單位定義為 `mL` 大寫會撈不到 | 同上 |
| `useStoreRegionId` 純字串儲存多個 ID，格式未文件化 | 前端 / 下游解析易錯 | `PmmVendorQuoteMaintenanceDetailDO.java:80` |
| `category` 為 Integer 但無 enum 化 | 業務語意未說明 | 同上 |
| `mfrPackUnit` / `singlePackCountUnit` 等是 Long ID，但 RespVO 可能要顯示中文名 | 需 join 或前端二次查詢 | DO 欄位 |
| 主表 `@NotNull` 註解掉 | NPE 風險（同 #27） | `PmmVendorQuoteMaintenanceSaveReqVO.java` |
| 編輯刪舊插新導致明細 id 變動 | 同 #27 | `updateVendorQuoteMaintenance` |
| 變更狀態端點是否檢查歸檔 | 與 #27 不一致（#27 不檢查），需確認 | `/update-status` 未完整列出 |
| 匯入流程是否走 BPM | 大量匯入若都跑簽核會卡，但若不跑可能繞過審核 | `importVqms` 未完整讀 |
| 「適用門市」與下游「採購單」的對應檢查 | 採購單下單時是否會 enforce「該店在 useStoreRegion 內」？ | 跨模組對齊 |
| 同品號重疊有效期的多筆報價是否該擋 | 例：兩家廠商同品號同期 / 同廠商同品號同期，下游撈不到唯一最新 | 程式邏輯無檢查 |
| 「最新報價(NTD/kg.l)」字面標為 `kg.l` — 業務語意是哪個？ | 應為「NTD/kg 或 NTD/L」二擇一，欄位命名混淆 | `PmmVendorQuoteMaintenanceDetailDO.java:57` |
| `singleCountMeasureUnit` 為 Long ID，但 calculateSingleCountMeasure 接受字串單位代碼 | DO 與計算 API 型別不一致 | DO vs Service |
| `moq`（最小訂購量）的單位是「包」還是「件」？ | 業務語意未明 | DO 欄位 |
| `beforePurchaseDate` / `saveDate` 都是 Integer 天數 | 是否該允許小時 / 分鐘？ | DO 欄位 |
| 報價有效起訖是 LocalDateTime（含時分秒），業務通常以日為粒度 | 是否該改 LocalDate？ | 主表欄位 |
| 1092 行的 Service 含大量 Excel / 換算邏輯，是否該拆 | 同 #27 | 全檔 |
| 同 #27 一樣有 inline ErrorCode 與 hardcoded message 風險 | 一致性與可維護性 | Service 多處 |
