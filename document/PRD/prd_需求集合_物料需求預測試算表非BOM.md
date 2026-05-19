# PRD｜需求集合 — 物料需求預測試算表（非 BOM）

> 來源：逆向自 `kingmaker-module-pdm` 後端程式碼（`controller/admin/rawmaterial1/RawMaterialDemandHeadController.java`、`service/rawmaterial1/RawMaterialDemandHeadServiceImpl.java`、`dal/dataobject/rawmaterial1/`、相依的 `demand` 與 `tempreq` Mapper）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **總部採購／需求預測規劃人員**（或 **區經理**、**店長**）。完成「食材需求預測試算表（BOM）」（PRD #24）後，下游採購／物流需要的不是「華堡需要 1 片牛肉餅」，而是「**這個品號（如牛肉餅 LB-04）這週實際要進多少公斤、從哪家廠商、何時送達**」。

「物料需求預測試算表（非 BOM）」就是把 #24 的食材級結果，再加上 #26「臨時需求審核」的人工臨時加單，**依品號合併**，**綁定廠商**，**算出預計配送日**，最後落地成可以給採購用的物料需求清單。

「非 BOM」的含義是：BOM 展開已經在 #24 做完，本表只在「物料／品號」這一層運作，不再展開食譜。

### 1.2 我要做什麼

- 指定要試算的範圍：區域（必填）、門店（可選）、食材中類 / 小類（可選過濾）、日期區間（必填）
- 系統依日期區間逐日跑：每天取該日的「需求預測單」（BOM 結果）+「臨時需求單」，合併 prodCode 級需求量
- 系統自動補上廠商：依品號 + 門店查最新的廠商報價，過濾掉沒廠商的食材
- 系統自動算「預計配送日」：依物流類型（週配 / 月配、物流週期）反推
- 平日 / 假日分流：週一至四取平日需求量、週五至日取假日需求量
- 結果儲存為「原物料需求行事曆單」三層結構：單頭 → 需求日 → 食材明細
- 可分頁查詢、單筆檢視

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 把 BOM 結果加上臨時需求合併 | 試算 #24 之後還有行銷臨時加碼，採購需要兩者合計 |
| 自動綁定廠商 | 同一品號不同門店可能不同廠商，採購要看的是「對哪家廠商下單」 |
| 自動算預計配送日 | 廠商有自己的物流週期（週一三五配 / 月配 1 號）；我不要每筆都自己算 |
| 平日 / 假日分流套用對應的需求量 | 銷量有差，配送量也要差 |
| 沒在廠商報價的食材自動過濾 | 沒對到報價就無法下採購單，留著反而干擾 |
| 區域層級或單店層級都能跑 | 區經理跟店長使用情境不同 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 建立物料需求行事曆單（POST /create） | 一次跑完整段日期區間，三層全建好 |
| 取得單頭 / 分頁查詢 | 找回過去跑過的單 |
| 需求日列表（/list） | 主頁面呈現「某區某段時間每天的需求預測單號 + 臨時需求單號 + 預計銷售額」 |
| 食材明細查詢（/detail） | 點某天進去看細項：哪些品號、需求量、廠商、預計配送日 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 物料需求預測試算表（非 BOM） |
| 所屬模組 | 需求集合（程式碼路徑 `pdm/rawmaterial1`，資料表前綴 `pdm_raw_material_demand_*`） |
| 兄弟功能 | 食材需求預測試算表（BOM）（#24）、臨時需求審核（#26） |
| 主要頁面 | 物料需求試算頁、單頭分頁、需求日列表、食材明細查詢 |
| 簽核流程 | 程式碼中**未見** BPM 流程綁定（與 #24 不同，#24 有走 Flowable） |
| 與物流管理重疊 | 同 Controller 內還有 `/query-details-by-month`、`/query-group-by-delivery-date`、`/query-details-by-delivery-date`、`/generateCsv` 等屬於物流管理模組（#48–52）的端點 |

---

## 2. 功能目的

「物料需求預測試算表（非 BOM）」承上啟下：

1. **承上**：把「食材需求預測（BOM 展開後）」+「臨時需求」彙整為品號級需求量
2. **啟下**：給採購單建立（#33）、原料物需求行事曆（#30）、物流配送排程（#48–52）使用
3. **以「日」為粒度**：每天獨立成一筆需求日記錄；下游可依日彙整或依配送日彙整
4. **平日 / 假日分流**：與 #24 同樣 weekday vs weekend，這裡是直接套用而非重新計算
5. **過濾無報價食材**：沒對應廠商的食材不寫入明細，避免無法下單的孤兒

---

## 3. 業務邏輯背景

### 3.1 三張表

| 表 | 用途 |
|---|---|
| `pdm_raw_material_demand_head`（單頭 / `RawMaterialDemandHeadDO`） | 一次試算的標頭：區域 / 門店、食材中類 / 小類、日期區間起訖 |
| `pdm_raw_material_demand_date_list`（需求日 / `RawMaterialDemandDateListDO`） | 日期區間內每一天的一筆記錄：需求日、門店、預估銷售量（萬元）、關聯的需求預測單號（demandRelationDoc）、關聯的臨時需求單號（tempRelationDoc） |
| `pdm_raw_material_demand_detail`（食材明細 / `RawMaterialDemandDetailDO`） | 每個需求日下的食材清單：品號、需求數量、廠商代號、預計配送日、實際到店日 / 數量、入庫單號 |

設計理念：

- 單頭 = 一次試算
- 需求日 = 試算範圍內每天的「來源單號彙整」（指向 #24 的單與 #26 的單）
- 食材明細 = 各品號的實際補貨量與配送計畫

### 3.2 兩個來源的合併規則

對範圍內每一天、每個門店：

1. **找需求預測單**（從 `crg_demand_forecast_detail` 撈該日該店的食材清單 by `selectDemandIngredientDetailList1(demandRelationDoc)`）
2. **找臨時需求單**（從臨時需求表撈該日該店的食材清單 by `selectTempIngredientDetailList1(tempRelationDocList)`）
3. **以 prodCode 為 key 做 Map**
4. 臨時需求逐筆比對：
   - 同 prodCode → 把臨時的 demandAmount 加到需求預測那筆上
   - 不同 prodCode → 新增進需求預測清單
5. **算臨時需求的 demandAmount** = `standardAmount × appliTempNum`，scale=2 HALF_UP

合併後得到「品號 → 數量」清單。

### 3.3 廠商綁定（jointVendorMaterialDetail）

合併後，逐筆對 prodCode + storeId 查「歸檔且未過期」的廠商報價，補上：

- mfrId / mfrName（廠商代號 / 名稱）
- cycleType / logisticsCycle（從廠商配送的物流類型取得）
- 其他配送相關資訊

**過濾**：`mfrName` 為 null 的記錄被剔除，不寫入明細表。**沒有廠商的食材就是無法下單，直接捨棄**。

### 3.4 預計配送日計算（calculateExpectDeliveryDate）

按「週配 / 月配 + 物流週期」分組計算每筆食材的預計配送日：

- 週配（cycleType=週）：依物流週期（如 `1,3,5` 表週一三五）反推需求日前最近一次配送日
- 月配（cycleType=月）：依物流週期（如 `1,15` 表每月 1 號、15 號）反推
- 計算公式涉及 DayOfWeek、LocalDate 跳算，邏輯較長未完整列出（程式碼 `RawMaterialDemandHeadServiceImpl.java:413+`）

### 3.5 平日 / 假日分流

`isFridaySaturdayOrSunday(demandDate)`：

- 需求日是週五六日（假日） → 取 `holidaySum` 為 demandAmount
- 需求日是週一至週四（平日） → 取 `weekDaySum` 為 demandAmount

**與 #24 一致**：兩個功能對「平日 / 假日」的定義相同。

### 3.6 區域 vs 單店模式

| 模式 | 觸發條件 | 行為 |
|---|---|---|
| 單店 | storeId 不為 null | 直接逐日跑該店 |
| 區域 | storeId 為 null | 從中繼 API 拉該區域下所有門店，逐店逐日跑 |

區域模式遇到中繼 API 錯誤 → 拋 `RAW_MATERIAL_GROUP_STORE_ERROR`（來源：`RawMaterialDemandHeadServiceImpl.java:170-172`）。

### 3.7 必填條件

- `regionId` 必填 → 否則拋 `RAW_MATERIAL_REGION_EMPTY`
- `startDate`、`endDate` 必填 → 否則拋 `RAW_MATERIAL_DATE_EMPTY`

兩個檢查在 Service 層做（VO 上沒有 `@NotNull`）。

### 3.8 資料權限自動過濾

`getRawMaterialDemandHeadPage` 依登入者：

- 有區域權限且請求未指定 → 自動加 regionId 過濾
- 有門店權限且請求未指定 → 自動加 storeId 過濾

與 #24 一致的設計。

### 3.9 並存的另一個 Controller

`controller/admin/rawmaterial/RawMaterialDemandController.java`（注意是 `rawmaterial`，不是 `rawmaterial1`）提供兩個查詢端點 `/list`、`/detail`，**功能與 `rawmaterial1` 的同名端點重複**。判斷：

- `rawmaterial` 是舊版（只查詢）
- `rawmaterial1` 是新版（查詢 + 建立 + 物流相關）

兩者並存表示新舊功能未整理乾淨，前端可能仍引用舊版（見 §11）。

### 3.10 與 #24 的差異

| 比較 | #24（BOM） | #25（非 BOM） |
|---|---|---|
| 粒度 | 食材級（每產品分解到食材） | 品號級（已不再拆解 BOM） |
| 計算方式 | 跑公式（萬元 × 標準用量 × 加成） | 直接 sum / 套用既有結果 |
| 資料來源 | 中繼銷售 + 食譜 | #24 的結果 + #26 的臨時需求 |
| 廠商綁定 | 對 storeId 為空跳過 | 必須有廠商才寫入 |
| 預計配送日 | 不算 | 算 |
| 簽核流程 | 有（Flowable） | **無** |
| 編輯 | 可編輯後重算 | 程式碼未見更新 / 刪除端點 |
| 已歸檔保護 | 有 | 無對應狀態欄位 |

---

## 4. 情境說明

### 4.1 正常流程 — 北一區下週物料需求試算

採購規劃人員小張在 5/19 完成北一區「下週（5/25–5/31）」的食材需求預測（#24，得到 demandRelationDoc=D-2026-0518-001）。另外行銷在 5/20 為下週某活動建了臨時需求單（#26，tempRelationDoc=T-2026-0520-003）。

5/21 小張要彙整成物料需求行事曆：

1. 進入物料需求試算頁
2. 填入：regionId=3（北一）、storeId=（不填，整區）、category=（不填）、startDate=2026-05-25、endDate=2026-05-31
3. POST /create
4. 系統：
   - insert 單頭，取得 headId
   - 從中繼 API 拉北一區所有門店
   - 對每店每天（共 7 天）：
     - 撈當日該店的需求預測單（demandRelationDoc）與臨時需求單（tempRelationDoc）
     - 兩者都沒有 → 跳過
     - 任一有 → 建立一筆需求日記錄
   - 對每筆需求日記錄：
     - 撈兩來源的食材清單
     - 以 prodCode 合併（臨時量加到預測量）
     - 對每品號 join 廠商報價 → 廠商空者捨棄
     - 算預計配送日
     - 依需求日是否為假日，取對應 sum 為 demandAmount
   - 批次 insert 明細
5. 回傳 headId

小張之後在頁面看「2026-05-25（一） 信義店 → 牛肉餅 LB-04 50 公斤 → 冷凍肉商 → 預計 5/22（五）配送」「2026-05-26（二） 信義店 → 美乃滋 30 公斤 → 醬料商 → 預計 5/25（一）配送」…

### 4.2 異常情境 — 範圍內某天兩來源都沒有

5/26（二）信義店那天沒有需求預測單也沒有臨時需求單。系統跳過該天，需求日列表上不會出現這筆。

### 4.3 異常情境 — 某品號沒對應廠商

某新進的「特殊起司 X-99」在 #24 預測時還沒有任何廠商報價。合併後 jointVendorMaterialDetail 查不到廠商，mfrName=null，被 filter 過濾掉，**不寫入明細**。下游採購看不到這筆，會直接漏失。

> 風險：沒有任何警示給使用者，可能造成「明明預測有，但實際下單沒有」。詳見 §11。

### 4.4 規則分流 — 平日 vs 假日

同一筆需求預測單可能同時提供 weekDaySum 與 holidaySum 兩個欄位。系統依該日是平日或假日選擇套用：

- 2026-05-25（一）→ 平日 → 取 weekDaySum
- 2026-05-30（六）→ 假日 → 取 holidaySum

### 4.5 使用者鍵入錯誤 — 缺 regionId 或日期

POST /create 漏了 regionId → 拋 `RAW_MATERIAL_REGION_EMPTY`
漏了起訖日期 → 拋 `RAW_MATERIAL_DATE_EMPTY`

### 4.6 異常情境 — 中繼 API 不可用

storeId 為空時系統會打中繼 API 拉門店清單。若中繼 5xx → 拋 `RAW_MATERIAL_GROUP_STORE_ERROR`，整筆建立失敗，rollback。

### 4.7 規則分流 — 重複建立同範圍

程式碼**沒有檢查**「同 region + 同日期區間是否已有單」 — 同一範圍可重複試算多次，會建出多筆單頭與重複的明細。歷史記錄會混亂。詳見 §11。

---

## 5. 操作流程

```
[使用者進入「物料需求試算」頁]
  │
  ├─ 1. 設定範圍：regionId（必）、storeId（可）、category/subcategory（可）、startDate~endDate（必）
  │
  ├─ 2. POST /pdm/raw-material-demand-head/create
  │    │
  │    ├─ 驗證 regionId / startDate / endDate
  │    ├─ insert 單頭 → headId
  │    │
  │    ├─ 進入 createRawMaterialDemandDateListList
  │    │    ├─ storeId 非空 → 單店模式：逐日跑
  │    │    └─ storeId 空 → 區域模式：
  │    │         ├─ 中繼 API 拉門店清單（失敗則拋例外）
  │    │         └─ 逐店逐日跑
  │    │
  │    ├─ 對每天每店：
  │    │    ├─ 查需求預測單 demandRelationDoc + expectAmount
  │    │    ├─ 查臨時需求單 tempRelationDoc
  │    │    ├─ 兩者皆空 → 跳過
  │    │    └─ 任一有 → 組裝 RawMaterialDemandDateListDO
  │    │
  │    ├─ batch insert 需求日列表
  │    │
  │    ├─ 對每筆需求日記錄處理食材明細：
  │    │    ├─ 撈兩來源的食材清單
  │    │    ├─ 以 prodCode 合併（臨時的 demandAmount = standardAmount × appliTempNum）
  │    │    ├─ join 廠商報價（storeId + prodCode）→ 補 mfrName/物流類型等
  │    │    ├─ 過濾 mfrName=null
  │    │    ├─ 計算預計配送日（依 cycleType + logisticsCycle）
  │    │    ├─ 依需求日是否假日，套對應的 sum 為 demandAmount
  │    │    └─ 填入 headId / regionId / storeId / demandDateId
  │    │
  │    └─ batch insert 食材明細
  │
  ├─ 3. 查詢單頭 GET /get?id= / GET /page
  │    └─ 依登入者區域 / 門店自動過濾
  │
  ├─ 4. 查詢需求日列表 GET /list
  │    參數：regionId（必）、storeId（可）、startDate ~ endDate
  │    └─ 用於頁面主表呈現
  │
  └─ 5. 查詢食材明細 GET /detail
       參數：需求日表的 id
       └─ 用於 drill-down
```

---

## 6. 欄位規格

### 6.1 單頭（`pdm_raw_material_demand_head` / `RawMaterialDemandHeadDO`）

| 欄位 | 中文業務語 | 型別 | 必填 |
|---|---|---|---|
| id | 單頭 ID | Long | 系統 |
| regionId / storeRegion | 區域 ID / 區域名稱 | Integer / 字串 | regionId 必填 |
| storeId / demandStore | 門店 ID / 門店名稱 | Integer / 字串 | 可選 |
| category / subcategory | 食材中類 / 小類（過濾用） | Long | 可選 |
| categoryName / subcategoryName | 上述名稱 | 字串 | 可選 |
| startDate / endDate | 日期區間起訖 | LocalDateTime | 必填 |

### 6.2 需求日（`pdm_raw_material_demand_date_list` / `RawMaterialDemandDateListDO`）

| 欄位 | 中文業務語 |
|---|---|
| id | 需求日 ID |
| headId | 主表 ID |
| demandDate | 需求日（每天一筆） |
| storeId / demandStore | 門店 |
| demandRelationDoc | 來源：需求預測試算單號 |
| tempRelationDoc | 來源：臨時需求單號（可能多個，逗號分隔） |
| expectAmount | 預計銷售量（萬元） |

### 6.3 食材明細（`pdm_raw_material_demand_detail` / `RawMaterialDemandDetailDO`）

| 欄位 | 中文業務語 |
|---|---|
| id | 明細 ID |
| headId | 主表 ID |
| demandDateId | 需求日表 ID |
| prodCode | 品號 |
| demandAmount | 需求數量 |
| mfrId | 廠商代號 |
| expectDeliveryDate | 預計配送日 |
| useDeliveryType | 預設物流類型 ID |
| actualArrivalDate | 實際到店日（後續入庫回填） |
| actualArrivalAmount | 實際到店數量（後續入庫回填） |
| storeId / demandStore / regionId / storeRegion | 區域與門店資訊 |
| demandRelationDoc / tempRelationDoc | 來源單號 |
| stockSignCode | 入庫單號（後續入庫回填） |

> 明細表已預留 `actualArrivalDate`、`actualArrivalAmount`、`stockSignCode` 給後續入庫流程回填（屬於物流配送 / 入庫管理範疇）。

### 6.4 查詢條件（`RawMaterialDemandHeadPageReqVO`）

regionId（自動過濾）、storeId（自動過濾）、storeRegion、demandStore、category、subcategory、categoryName、subcategoryName、startDate、endDate、createTime、demandDate。

**全部用等值比對**，且自動加登入者過濾。

---

## 7. 商業邏輯

### 7.1 建立流程

`createRawMaterialDemandHead`（`@Transactional`）：

1. insert 單頭
2. 跑 `createRawMaterialDemandDateListList`（驗證、逐日生成需求日、生成食材明細）

### 7.2 兩來源合併

- 以 prodCode 為 Map key
- 同品號 → demandAmount 累加
- 不同品號 → 加入清單
- 臨時需求量 = `standardAmount × appliTempNum`（scale=2 HALF_UP）

### 7.3 廠商綁定

- 對 prodCode + storeId 查最新廠商報價
- 補 mfrName、物流類型相關欄位
- mfrName 為 null → filter 掉

### 7.4 預計配送日計算

依物流類型分組後計算（程式碼 `calculateExpectDeliveryDate`，內含 DayOfWeek 跳算與 YearMonth 處理）。詳細邏輯需另外深度閱讀程式碼（屬於物流規劃 §3.4）。

### 7.5 平日 / 假日分流

每筆食材的 demandAmount 取自：

- weekDaySum（平日）
- holidaySum（假日）

### 7.6 區域模式呼叫中繼

storeId 為空時打中繼 API `getGroupWithStoresInnerByGroupId(regionId)` 取門店清單；失敗則整筆失敗。

### 7.7 沒有 update / delete 端點

Controller 只有 create / get / page / list / detail。**沒有更新與刪除**。代表一旦建立就不能修改、不能刪除（除非走 DB 直接刪 — 違反設計）。詳見 §11。

---

## 8. 使用角色與權限

| 角色 | 可看資料 | 可操作 | 對應權限字串 |
|---|---|---|---|
| 總部採購規劃 | 全部 | 建立、查詢 | `pdm:raw-material-demand-head:create`、`pdm:raw-material-demand-head:query` |
| 區經理 | 限自己區域 | 同上 | 同上（自動套 areaId 過濾） |
| 店長 | 限自己門店 | 同上 | 同上（自動套 storeId 過濾） |
| 物流規劃人員（查詢） | 全部 | 查需求日 / 食材明細 / 物流相關端點 | `pdm:raw-material:query` |

> 注意：建立用 `pdm:raw-material-demand-head:create`，但需求日 / 明細查詢用 `pdm:raw-material:query`（命名不一致）。詳見 §11。

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節，**待前端對照**。建議：

### 9.1 試算頁

- 條件區：區域下拉（必）、門店下拉（可選）、食材中類 / 小類（可選）、日期區間（必）
- 試算按鈕：呼叫 POST /create
- 進度條：跑大區域 7 天可能耗時，需有 loading
- 完成後跳轉到該 headId 的明細頁

### 9.2 需求日列表頁

- 表頭：區域、門店、需求日、需求預測單號、臨時需求單號、預計銷售量
- 點某行 drill-down 進食材明細

### 9.3 食材明細頁

- 表頭：品號、需求數量、廠商、預計配送日、實際到店日 / 數量、入庫單號
- 操作：（目前無編輯／刪除按鈕對應的後端）

### 9.4 單頭分頁

- 條件：區域、門店、日期區間
- 表格：建立時間、區域、門店、區間、操作（檢視）

---

## 10. 功能範圍

### 10.1 包含的功能

- 物料需求行事曆單的建立（CREATE only）
- 三層結構（單頭 / 需求日 / 食材明細）的自動生成
- 兩來源（需求預測單 + 臨時需求單）的 prodCode 合併
- 廠商綁定與無廠商過濾
- 平日 / 假日分流
- 預計配送日計算
- 單頭分頁查詢 / 單筆查詢
- 需求日列表查詢、食材明細查詢
- 資料權限自動過濾

### 10.2 預留但尚未實作

- **更新 / 刪除單頭與明細**：Controller 無對應端點
- **錯誤訊息給「無廠商被剔除」**：目前靜默過濾
- **重複試算保護**：同範圍可重複建單
- **編輯預計配送日**：自動算的若不合理無法人工修改
- **回填 actualArrivalDate / Amount / stockSignCode**：欄位已預留但寫入邏輯需走入庫流程（PRD #40 入庫作業管理）
- **簽核流程**：無
- **匯出 Excel**：無（與 #24 不同；只有 `/generateCsv` 給物流 MSS 用）

### 10.3 不包含

- BOM 展開（屬於 #24）
- 臨時需求建立（屬於 #26）
- 採購單建立（屬於 #33 採購單管理；本表是輸入）
- 物流配送排程 / 行事曆（屬於 #48–52，與本 Controller 部分端點共用）
- 入庫回填（屬於 #40 入庫作業管理）
- 廠商報價維護（屬於 #28）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| 為何同時存在 `rawmaterial` 與 `rawmaterial1` 兩個 Controller？ | 命名暗示一新一舊，但兩者功能重疊，需釐清誰是現役 | 兩個 Controller 都活著 |
| 無廠商被靜默過濾，是否需要提示？ | 預測有但下不了採購單會造成漏進貨 | `RawMaterialDemandHeadServiceImpl.java:283、319、362` |
| 同範圍可重複試算 — 是否需檢查 | 多筆單頭重疊，查詢與報表會看到重複資料 | 程式邏輯無檢查 |
| 為何沒有更新 / 刪除端點？ | 試算結果有錯就只能 DB 改 | Controller 缺少 |
| 為何沒有簽核流程？ | 與 #24 不一致；採購來源若沒簽核就少了管控環節 | 程式無 BPM 呼叫 |
| 平日 / 假日的劃分（週五六日為假日） | 與業界 / 業務認知是否一致？連假特殊處理？ | `isFridaySaturdayOrSunday` |
| 預計配送日的具體計算邏輯（calculateExpectDeliveryDate）正確性 | 含 DayOfWeek、YearMonth 跳算，邊界條件多 | `RawMaterialDemandHeadServiceImpl.java:413+` 未完整列出 |
| 同 Controller 內放物流管理（#48–52）的端點，是否要拆分 | `query-details-by-month`、`query-group-by-delivery-date` 等語意上不屬於 #25 | `RawMaterialDemandHeadController.java:102+` |
| 權限字串不一致：建立用 `pdm:raw-material-demand-head:*`，查詢需求日 / 明細用 `pdm:raw-material:query` | 角色設定容易遺漏 | 各端點 `@PreAuthorize` |
| 範圍過大（如跨月）時的效能 | 對每店每天打中繼 + 跑食材合併 + 廠商查詢 + 配送日計算，N×M×K 級複雜度 | 程式無快取無分批 |
| `category` 與 `subcategory` 是過濾用還是儲存用？ | VO 上看似過濾，但 DO 上也儲存 — 若同個 head 對應多個 category 的食材會怎麼處理？ | DO 欄位設計 |
| 區域模式下，門市為空但中繼回傳空清單時的「return」是否符合預期？ | 程式直接 return，不會 insert 任何 date_list 與 detail，但單頭已 insert（變孤兒單頭） | `RawMaterialDemandHeadServiceImpl.java:174-176` |
| 沒有 `processStatus` / 已歸檔的概念 | 試算結果一旦寫入即視為定案？還是會有人工確認步驟？ | DO 無此欄位 |
| `useDeliveryType`（物流類型 ID）是否真有指向 `pdm_logistics_type`？ | 命名上對應，但實際 join 邏輯需確認 | DetailDO 欄位 |
| `expectAmount` 預計銷售量單位（萬元）的精度與展示 | BigDecimal 無 scale 約束 | DO 欄位 |
| 範圍內某天兩來源都沒有 → 跳過，不留任何痕跡 | 使用者可能想知道「為什麼這天沒有？」 | `RawMaterialDemandHeadServiceImpl.java:142-144` |
| 對「未綁定 BPM」的物料需求單，下游採購是否會直接信任並建單？ | 缺管控環節 | 設計層面 |
| 程式碼大量重複（4 個 if 分支內邏輯非常相似） | 可重構，但目前可讀性差 | `RawMaterialDemandHeadServiceImpl.java:235-401` |
