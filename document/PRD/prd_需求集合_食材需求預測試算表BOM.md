# PRD｜需求集合 — 食材需求預測試算表（BOM）

> 來源：逆向自 `kingmaker-module-pdm` 後端程式碼（`controller/admin/demand/` 三個 Controller、`service/demand/DemandForecastServiceImpl.java`、`dal/dataobject/demand/`、相關 DTO 與 Mapper）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **總部採購／需求預測規劃人員**（或被授權的 **區經理**、**店長**）。每隔一段時間我要回答這個問題：

> 「下週北一區（或某家門市）大約會賣出多少華堡、薯條、雞塊？這些單品分解到食材（牛肉餅、薯條原料、雞肉塊…）後，每樣食材總共要備多少？」

這份答案就叫「**食材需求預測試算表**」 — 系統會把過去一段時間的歷史銷售拉出來，依照單品的食譜（BOM）展開為食材，再用「每萬元銷售額用掉多少食材」的口徑，搭配「下週預估銷售額」推算出每樣食材的預測用量。

### 1.2 我要做什麼

- 選擇預測範圍（區域 + 可選某門店）、銷售資料時段（如過去 28 天）、預測週起訖、預測加成（如 10% 表示比歷史多 10%）
- 系統即時試算：把每個門店的每個單品銷量 → 透過食譜展開為食材清單 → 對每樣食材計算「每日萬元平均需求量」「預測平均需求量」「箱換算」
- 對「長期庫存」（LONG）類食材：系統額外查當下庫存與安全存量，**若庫存未低於安全存量則跳過萬元計算**（前端顯示「判斷庫存」）
- 編輯試算結果（人工調整某項食材的數值）
- 儲存為一張「需求預測單」（主表 + 明細）並進入簽核流程
- 在待簽分頁查看交給自己的單據
- 已歸檔的單據視為定案，禁止再修改

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 想知道「下週要備多少食材」 | 採購要提前下單，倉儲要排補貨，憑直覺猜會偏多或偏少 |
| 用過去銷量自動推估，不要每次手算 | 人工試算需 1–2 天且公式不一致；每個區經理算法不同 |
| 平日 / 假日要分開算 | 漢堡王平日與週末客流差很大，混算會失準 |
| 食譜變動要立即反映 | 行銷把華堡的牛肉餅從 1 片改成 2 片時，預測也要跟著變 |
| 「長期食材」不要每週都被算進去 | 如沙拉醬、冷凍肉，庫存很多時下週其實不用補 |
| 預測結果要能調整 | 試算出 100 公斤，行銷說下週要做活動，要手動加到 120 |
| 試算完要走簽核 | 採購不能拍腦袋下單，需要主管 / 區經理確認 |
| 已歸檔的不能再改 | 否則 audit trail 會壞掉 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 「產品配方預測」即時試算 API | 一次回傳「某區某店 → 各產品 → 各食材」三層結構與預測量 |
| 「預測平均需求量」批次重算 API | 使用者調整 weekdaySales 後重新計算該行的萬元預測量，不必重打全部 |
| 「建立需求預測單（含明細）」 | 試算定案後落 DB |
| 「分頁查詢」「待簽分頁」 | 找回過去的單、看自己要處理的單 |
| 「更新流程狀態」 | 簽核流程中改 processStatus |
| 「批次刪除主表/明細」 | 廢棄誤建單據 |
| 「需求預測配置」（排程／適用範圍） | 自動跑預測：定期、按範圍 |
| 引用「漢堡王中繼」的區域 / 門店 / 銷售歷史 | 避免在 ERP 端維護門店主檔 |
| 結合「廠商報價」做箱換算 | 預測量 ÷ 每箱裝數 = 箱數，方便採購下單 |
| 結合「食材維護」「食譜（單品）維護」取得 BOM | 把產品銷量還原成食材用量 |
| BPM 流程整合 | 自動發起簽核（待處理 → 待簽核 → 已歸檔） |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 食材需求預測試算表（BOM） |
| 所屬模組 | 需求集合（程式碼路徑 `pdm/demand`，資料表前綴 `crg_demand_forecast`） |
| 兄弟功能 | 物料需求預測試算表（非 BOM）（#25）、臨時需求審核（#26） |
| 主要頁面 | 預測試算頁（即時計算 + 編輯 + 儲存）、預測單分頁查詢、待簽分頁、預測配置維護頁 |
| 簽核流程 | 有：透過 `MenuFlowProcessInstanceHelper` 綁定 BPM 流程；表單路徑 `FormPathUniqueEnum.DEMAND` |

---

## 2. 功能目的

「食材需求預測試算表（BOM）」是漢堡王 ERP 內最複雜也最核心的業務功能之一，扮演「**從銷售歷史到食材採購量的轉換引擎**」：

1. **回答「下週要備多少食材」這個生意核心問題**
2. **以「每日每萬元銷售額對應的食材用量」作為穩定口徑**，比直接用「銷量數字」更耐住菜單／價格變動
3. **平日 / 假日分流**：分開計算與顯示，避免週末高峰被平日稀釋
4. **長期食材的智慧跳過**：透過存量子分類 + 安全存量檢查，長期庫存類食材在庫存充足時不被計入下次補貨，**讓預測量更貼近實際採購需要**
5. **試算 → 編輯 → 儲存 → 簽核**完整流程：預測不是一次性報表，而是會被人工調整、最終定案的「需求預測單」
6. **資料權限切割**：依登入使用者的「區域 ID」「門店 ID」自動過濾可見資料，店長只看自己門市

---

## 3. 業務邏輯背景

### 3.1 兩張表：單頭與單身

| 表 | 用途 |
|---|---|
| `crg_demand_forecast`（單頭 / `DemandForecastDO`） | 一張需求預測單的主資訊：單據日期、單據編號、預測模式、區域 / 門店、預測週起訖、銷售資料起訖、預測加成 %、簽核單號、流程實例 ID、流程狀態（待處理 / 待簽核 / 已歸檔）、主旨 |
| `crg_demand_forecast_detail`（單身 / `DemandForecastDetailDO`） | 每張預測單下的食材明細：parentId、區域 / 門店 / 產品 / 食材、平日 / 假日銷售、標準用量、標準數量、平日 / 假日訂單金額、平日 / 假日萬元平均需求量、平日 / 假日預測萬元平均需求量、平日 / 假日平均銷量、平日 / 假日天數、區域 / 門店 ID |

> 表前綴是 `crg_`（推測為 Cross Region Group 或某內部代號）而不是 `pdm_`，與其他 PDM 功能不一致（見 §11）。

### 3.2 核心計算公式

對每個門店、每個單品、每樣食材執行：

```
平均銷量          = 銷量 / 天數
每日萬元平均銷量  = 平均銷量 × 10000 / 訂單金額
每日萬元平均需求量 = 每日萬元平均銷量 × 食材標準用量
預測平均需求量    = 每日萬元平均需求量 × (1 + 預測加成%)
箱換算            = 預測平均需求量 / 單箱裝數（來自廠商最新報價）
```

- 平日（週一至週四）與假日（週五至週日）分別套用 — 兩組數值
- BigDecimal 中間步驟使用 8 位精度 + HALF_UP，最終輸出小數 2 位（來源：`DemandForecastServiceImpl.java:645-648、676`）
- 訂單金額 / 天數任一為 0 或負 → 結果視為 0（避免除零）
- 單箱裝數為 null 或 0 → 箱換算回傳 null（前端應顯示 `-`）

### 3.3 BOM（食譜）展開

產品 → 食材的對應透過 `PdmProductRecipeRelMapper.selectProductRecipeAnalysisByProductIds(productIds)` 批量查詢，回傳 `ProductRecipeAnalysisDTO`，欄位含：

- productId / productName / prodCode
- ingredientId / ingredientName
- standardAmount / amountUnit（標準用量 + 單位）
- standardQuantity / quantityUnit（標準數量 + 單位）
- storageType（LONG / SHORT / null，長期 / 短期庫存類型）
- ingredientSubcategoryDetailId（食材小類，用於決定是否套用安全存量檢查）

一個產品可能對應多筆食材（例如華堡含牛肉餅、麵包、生菜、起司）。所有食材逐一展開後形成明細列。

### 3.4 LONG 食材的安全存量跳過邏輯

對 `storageType='LONG'` 且 `ingredientSubcategoryDetailId` 不為 null 的食材，額外執行：

```
1. 查該食材的安全存量（取 first，by ingredientId）
2. 查該門店該食材的當前庫存（by storeId + ingredientId）
3. 若 currentStock >= safeStock → 不需補貨：
     - 跳過萬元預測計算
     - 設 isSafetyStockWarning = false
     - 前端顯示「判斷庫存」
4. 若 currentStock < safeStock → 視為需補貨：
     - 設 isSafetyStockWarning = true
     - 回填 currentStock 給前端
     - 走萬元預測計算
5. 查無安全存量 → 視為低於（true，需補）
6. 查無庫存 → 視為低於（true，需補）
```

來源：`DemandForecastServiceImpl.java:715-757、829-848`。

### 3.5 廠商報價的箱換算

對非 LONG 或 LONG-需補的食材，依 `prodCode + storeId + demandWeekStartTime` 查 **最新一筆有效廠商報價**（含 vendorName、singlePackCount）：

- 有報價且單箱數 > 0 → 算箱換算
- 無報價或單箱數無效 → 箱換算為 null

注意：當前端未指定 `storeId`（區域整體預測）時，**直接跳過廠商查詢**（嚴格模式），所有 vendor 與箱換算皆為 null（來源：`DemandForecastServiceImpl.java:423`）。

### 3.6 資料權限：依登入者自動過濾

`SecurityFrameworkUtils.getLoginUserAreaId() / getLoginUserStoreId()`：

- 登入者有區域權限且請求未指定區域 → 強制以使用者的區域 ID 過濾
- 登入者有門店權限且請求未指定門店 → 強制以使用者的門店 ID 過濾
- 兩者都無 → 全公司資料可見（總部）

來源：`DemandForecastServiceImpl.java:110-126`。同樣的過濾也套用在「拉中繼門店清單」（`getRemoteGroupWithStoresInner`）。

### 3.7 BPM 流程整合

建立預測單時：

1. 取「需求預測試算表」選單對應的 signCode，寫入單頭
2. 流程狀態初始為「待處理」
3. 呼叫 `MenuFlowProcessInstanceHelper.createProcessInstanceIfFlowOpen()` 判斷該選單是否綁定流程
4. 若綁定 → 啟動 Flowable 流程實例，把 `processInstanceId` 寫回單頭
5. 後續流程節點推進時透過 `updateDemandForecastProcessStatus` 更新狀態（待處理 → 待簽核 → 已歸檔）

來源：`DemandForecastServiceImpl.java:864-887`。

### 3.8 已歸檔保護

`ARCHIVED = "已歸檔"`。更新單據時若已歸檔，拋 `DEMAND_FORECAST_ARCHIVED_CANNOT_UPDATE`（來源：`DemandForecastServiceImpl.java:892` + 後續 `validateDemandForecastExists` 應檢查）。

### 3.9 預測配置（DemandForecastConfig）

獨立於每張預測單之外的「自動跑預測」設定：

- 範圍互斥檢查：兩個啟用中的配置不可重疊範圍
- 啟用 / 停用：停用不刪資料
- precheck：加入前互斥預檢
- 啟用時自動掃衝突，有衝突就標記並拒絕啟用
- 手動觸發 run-now：依範圍獨立跑

來源：`DemandForecastConfigController.java`。

---

## 4. 情境說明

### 4.1 正常流程 — 北一區整區下週預測

採購規劃人員小張要做「北一區下週（5/25–5/31）食材預測」，銷售資料用上週（5/12–5/18）數字、預測加成 10%。

1. 進入預測試算頁，選「北一區」（groupAreaId=3），不選具體門店
2. 銷售資料起訖：5/12–5/18；預測週起訖：5/25–5/31；預測加成：1.10
3. 點「產品配方預測」
4. 系統內部：
   - 從中繼 API 拉北一區下所有門店該週銷售統計
   - 對每店每產品查 BOM、展開為食材
   - 對每樣食材跑公式計算平日 / 假日萬元預測量
   - 因為沒選 storeId（區域整體），跳過廠商查詢，箱換算與廠商名稱皆 null
5. 結果回傳：「店 1（信義店）→ 華堡 → 牛肉餅 / 麵包 / 生菜 / 起司」「店 1 → 雞塊 → 雞肉 / 醬料」「店 2（板橋店） → …」
6. 小張檢視結果，覺得某項食材偏低，手動把 `weekdaySales` 從 80 改成 100
7. 點「重新計算該行」，呼叫 `/calculate-projected-sales` 拿到該食材的新萬元預測量
8. 全部校對完成 → 點「儲存」呼叫 `/create-with-details`
9. 系統建立單頭（流程狀態「待處理」），批次寫入明細，啟動 BPM 流程拿到 `processInstanceId`
10. 單據進入主管的「待簽分頁」

### 4.2 典型業務 — 單店日常預測（含廠商箱換算）

店長進入試算頁，系統自動依其權限只允許他選自己門店（A 區 1 號店）。他選銷售資料 5/12–5/18、預測週 5/25–5/31、加成 5%、storeId=11。

跟 §4.1 不同點：

- 因為有 storeId，系統會查每樣食材對應 prodCode 的最新廠商報價
- 預測量 / 單箱裝數 = 箱換算（小數 2 位）
- 例如「牛肉餅」預測 120 公斤，廠商「冷凍肉商」單箱 24 公斤 → 箱換算 = 5.00 箱
- 平日 / 假日各算一次

### 4.3 異常情境 — LONG 食材庫存充足

醬料、冷凍肉這類 LONG（長期）食材，門店通常維持高庫存。試算時：

- 系統查「醬料 X 安全存量 = 5 公斤」「當前庫存 = 12 公斤」
- 12 > 5 → 跳過萬元計算，僅回傳食材基本資訊
- `isSafetyStockWarning = false`
- 前端顯示「判斷庫存」（表示「不用算，庫存夠」）

若某店該食材當前庫存掉到 3 公斤 < 5（安全存量）：

- `isSafetyStockWarning = true`
- 回填 currentStock = 3
- 繼續走萬元預測計算，給出補貨建議量

### 4.4 異常情境 — 查無安全存量／查無庫存

某新食材尚未在「安全存量設定」維護，或某店庫存表沒這筆記錄：

- 視為「低於安全存量」（true）→ 走完整預測計算
- 等於「保守處理」，避免漏補

### 4.5 規則分流 — 已歸檔不可改

單據已被簽核流程跑到「已歸檔」狀態。使用者試圖打開編輯並送出更新：

- `validateDemandForecastExists` 取出單頭，發現 processStatus = 「已歸檔」
- 拋 `DEMAND_FORECAST_ARCHIVED_CANNOT_UPDATE`，訊息：「已歸檔，禁止更新」

### 4.6 規則分流 — 待簽分頁的特殊邏輯

`/todo-page` 端點查「分派給我的、流程狀態符合查詢條件」的單據：

1. 透過 `menuFlowProcessInstanceHelper.listProcessInstanceIdsForAssigneeTodoPage(formPath, userId, processInstanceStatus)` 取得使用者作為簽核 assignee 的所有 processInstanceId
2. 若無任何 ID → 直接回空頁
3. 把 IDs 塞回查詢條件 `taskIds`
4. 套用統一分頁查詢（含使用者區域 / 門店過濾）

### 4.7 規則分流 — 區域整體 vs 單店預測

- 區域整體（無 storeId）：跳過廠商報價查詢，箱換算為 null；資料量大，效能上更耗時
- 單店（有 storeId）：完整跑廠商報價 + 箱換算

### 4.8 自動排程跑預測（DemandForecastConfig）

管理員建立一份配置：每週日 23:00 自動跑「北一區」整區預測，預測週為下週、銷售週為上週。

- 啟用時系統檢查與其他啟用中的配置是否範圍互斥（同區同時段）
- 有衝突 → 不啟用、標記衝突
- 無衝突 → 啟用，每週日由排程自動執行
- 系統在排程觸發時自動建立預測單，預設 assignee 為配置設定的負責人

---

## 5. 操作流程

```
[使用者進入「需求預測試算」頁]
  │
  ├─ 1. 取區域清單 GET /pdm/demand-forecast/detail/bk/group-summaries
  │    ├─ 依登入者區域權限自動過濾
  │    └─ 回 List<GroupSummaryRespVO>
  │
  ├─ 2. 取區域下門店 GET /pdm/demand-forecast/detail/bk/stores-by-group?groupId=
  │    └─ 依登入者門店權限自動過濾
  │
  ├─ 3. 即時試算 GET /pdm/demand-forecast/detail/product-recipe-analysis
  │    參數：groupAreaId（必）、storeId（可選）、銷售起訖、預測週起訖、預測加成
  │    │
  │    ├─ 從中繼拉銷售統計（帶 5 分鐘快取）
  │    ├─ 批次查產品 → 食譜 → 食材
  │    ├─ 對 LONG+食材小類者預載安全存量、門店庫存
  │    ├─ 若有 storeId：批次查廠商最新報價
  │    ├─ 對每店每產品每食材跑公式：
  │    │    ├─ LONG 且未低於安全存量 → 跳過萬元計算
  │    │    └─ 否則 → 計算萬元平均、預測平均、箱換算
  │    └─ 回三層結構：店 → 產品 → 食材明細
  │
  ├─ 4. 使用者編輯某行銷量 → 重算
  │    POST /pdm/demand-forecast/detail/calculate-projected-sales
  │    │
  │    ├─ 取 parentId（若試算結果還沒存則 null）+ productId
  │    ├─ 有 parentId → 查 DB 該行首條記錄取基準（standardQuantity / orderAmount / dayCount）
  │    ├─ 無 parentId → 用前端傳入的基準
  │    └─ 跑公式回傳 weekdayAverageSalesPer10k、projectedWeekdayAverageSalesPer10k 等
  │
  ├─ 5. 儲存（建立單頭+單身）
  │    POST /pdm/demand-forecast/detail/create-with-details
  │    │
  │    ├─ 產生簽核單號（signCode）
  │    ├─ 流程狀態設「待處理」
  │    ├─ insert 單頭，取得 headerId
  │    ├─ 批次 insert 明細（parentId = headerId）
  │    └─ 啟動 BPM 流程（若選單綁定）→ 寫回 processInstanceId
  │
  ├─ 6. 編輯（單頭+單身）
  │    PUT /pdm/demand-forecast/detail/update-with-details
  │    │
  │    ├─ 檢查存在
  │    ├─ 若 processStatus = 已歸檔 → 拋 DEMAND_FORECAST_ARCHIVED_CANNOT_UPDATE
  │    └─ 更新單頭，明細採「刪舊插新」策略
  │
  ├─ 7. 查詢列表 GET /pdm/demand-forecast/page
  │    ├─ 過濾：storeRegion like、demandStore like、週起訖區間、processStatus
  │    ├─ 依登入者區域 / 門店自動加過濾
  │    └─ 回分頁
  │
  ├─ 8. 待簽分頁 GET /pdm/demand-forecast/todo-page
  │    ├─ 找 assignee = 我 的 processInstanceIds
  │    └─ 套統一查詢
  │
  ├─ 9. 更新流程狀態 PUT /pdm/demand-forecast/update-process-status
  │    └─ 流程節點驅動，updateById 改 processStatus
  │
  └─ 10. 批次刪除 DELETE /pdm/demand-forecast/deleteBatch
        ├─ 先刪明細（by parentIds）
        └─ 再刪主表

[排程自動跑]
  └─ DemandForecastConfig 啟用 → 排程觸發 → run-now 為每個範圍獨立建立預測單
```

---

## 6. 欄位規格

### 6.1 單頭（`crg_demand_forecast`，由 `DemandForecastDO` 對應）

| 欄位 | 中文業務語 | 型別 | 必填 | 說明 |
|---|---|---|---|---|
| id | 預測單 ID | Long | 系統產生 | |
| documentDate | 單據日期 | LocalDate | ✕ | |
| documentCode | 單據編號 | 字串 | ✕ | |
| signCode | 簽核單號 | 字串 | 系統產生 | 由 `menuService.generateSignCode("需求預測試算表")` 產生 |
| forecastMode | 預測模式 | 字串 | ✕ | 業務語意需確認（見 §11） |
| storeRegion | 門市區域 | 字串 | ✕ | 區域名稱（與 regionId 配對） |
| demandStore | 需求門市 | 字串 | ✕ | 門市名稱（與 storeId 配對） |
| weekStartDate | 需求週別開始 | LocalDate | ✕ | 預測週起 |
| weekEndDate | 需求週別結束 | LocalDate | ✕ | 預測週迄 |
| forecastIncrementPercent | 預測加成 (%) | BigDecimal | ✕ | 例 1.10 表示加 10% |
| salesStartDate | 銷售資料開始 | LocalDate | ✕ | 歷史銷售區間起 |
| salesEndDate | 銷售資料結束 | LocalDate | ✕ | 歷史銷售區間迄 |
| processStatus | 流程狀態 | 字串 | 系統 | 待處理 / 待簽核 / 已歸檔 |
| subject | 主旨 | 字串 | ✕ | |
| regionId | 區域 ID | Integer | ✕ | 對應中繼 area_group_id |
| storeId | 門市 ID | Integer | ✕ | 對應中繼 store_id |
| processInstanceId | 流程實例 ID | 字串 | BPM 系統 | Flowable processInstance |

### 6.2 單身（`crg_demand_forecast_detail`）

關鍵欄位：

| 欄位 | 中文業務語 |
|---|---|
| parentId | 主表 ID |
| region / regionId | 區域名稱 / ID |
| storeName / storeId | 門店名稱 / ID |
| productId / productName | 商品 ID / 名稱 |
| weekdaySales / weekendSales | 平日銷售 / 假日銷售（人工可調整） |
| ingredientId / ingredientName | 食材 ID / 名稱 |
| prodCode | 品號（對應廠商報價） |
| standardAmount / amountUnit | 標準用量 / 單位 |
| standardQuantity / quantityUnit | 標準數量 / 單位 |
| weekdayDemandAmount / weekendDemandAmount | 平日 / 假日需求計量 |
| weekdayDemandCount / weekendDemandCount | 平日 / 假日需求計數 |
| forecastDemand | 預測需求 |
| weekdayOrderAmount / holidayOrderAmount | 平日 / 假日訂單金額 |
| weekdayAverageSalesPer10k / holidayAverageSalesPer10k | 平日 / 假日每日萬元平均需求量 |
| projectedWeekdayAverageSalesPer10k / projectedHolidayAverageSalesPer10k | 平日 / 假日每日萬元預測平均需求量 |
| weekdayAverageSales / holidayAverageSales | 平日 / 假日平均銷量 |
| weekdayCount / holidayCount | 平日 / 假日天數 |

> 共約 25+ 欄位，所有金額 / 數量為 BigDecimal，銷量為 Integer。

### 6.3 即時試算回傳（`StoreDemandForecastVO` 三層結構）

```
StoreDemandForecastVO
  ├─ storeId / storeName
  └─ products: List<ProductDemandForecast>
      ├─ productId / productName
      ├─ weekdayTotalSales / holidayTotalSales
      └─ ingredientDetails: List<DemandForecastDetailVO>
          ├─ 食材基本資訊
          ├─ 計算結果（萬元、箱換算）
          ├─ vendorName（含 storeId 時）
          ├─ storageType / isSafetyStockWarning / currentStock
          └─ 平日 / 假日各組數值
```

### 6.4 查詢條件（DemandForecastUnifiedPageReqVO）

| 條件 | 比對 |
|---|---|
| storeRegion | 模糊 |
| demandStore | 模糊 |
| startDate / endDate | 週範圍判斷 |
| processStatus | 等於 |
| createTime[0..1] | 區間 |
| queryType | 區分查詢類型（region / store / week / process / all） |
| regionId / storeId | 等於（自動加上登入者過濾） |
| processInstanceStatus | 流程實例狀態 |
| taskIds | 由系統內部填入（待簽分頁） |

---

## 7. 商業邏輯

### 7.1 試算（`getProductRecipeAnalysis`）

略 — 詳見 §3.2、§3.4、§5 第 3 步。重點：

- 批次預載：產品配方、安全存量、門店庫存、廠商報價（4 個批次查詢，避免 N+1）
- LONG + 食材小類者才執行安全存量判斷
- 區域整體（無 storeId）跳過廠商查詢

### 7.2 重算單行（`calculateProjectedSales`）

- 同一批 items 的 parentId 必須一致（取首個非 null）
- parentId 有值 → 一次批次查 DB 取 productId 的首條明細作基準
- parentId 無值 → 用前端傳入基準
- 公式：`projected = (sales / dayCount) × 10000 / orderAmount × standardQuantity`

### 7.3 建立（`createDemandForecastWithDetails`）

1. signCode = `menuService.generateSignCode("需求預測試算表")`
2. processStatus = 「待處理」
3. insert 單頭 → 取 headerId
4. 明細 setParentId(headerId) → 批次 insert
5. 啟動 BPM 流程（選單綁定時）→ 回填 processInstanceId

### 7.4 更新（`updateDemandForecastWithDetails`）

1. 取舊單頭：不存在 → `DEMAND_FORECAST_NOT_EXISTS`
2. 已歸檔 → `DEMAND_FORECAST_ARCHIVED_CANNOT_UPDATE`
3. 更新單頭
4. 明細「刪舊插新」（推測 — 未讀到此段）

### 7.5 BPM 整合

- 表單路徑：`FormPathUniqueEnum.DEMAND.getPath()`
- 啟動：`menuFlowProcessInstanceHelper.createProcessInstanceIfFlowOpen(userId, formPath, headerId)`
- 推進：透過流程節點觸發 `updateDemandForecastProcessStatus`
- 待簽：`listProcessInstanceIdsForAssigneeTodoPage`

### 7.6 資料權限自動過濾

- 區域 ID：登入者有設定 + 請求未指定 → 自動覆寫
- 門店 ID：同上
- 套用範圍：統一分頁查詢、拉中繼門店清單

---

## 8. 使用角色與權限

| 角色 | 可看資料 | 可操作 | 對應權限字串 |
|---|---|---|---|
| 總部採購規劃 | 全部區域 / 全部門店 | 查詢、試算、建立、更新、刪除 | `pdm:demand-forecast:query`、`create`、`update`、`delete` |
| 區經理 | 限自己區域 | 同上但限其區域 | 同上（受 areaId 過濾） |
| 店長 | 限自己門店 | 同上但限其門店 | 同上（受 storeId 過濾） |
| 簽核者（主管） | 透過待簽分頁看到分派的單 | 通過 BPM 流程簽核 | `query` + BPM 角色 |

> 注意：權限字串只有一個 `pdm:demand-forecast:*`，**不區分 BOM 與非 BOM 試算** — 兩功能共用權限（見 §11）。預測配置（DemandForecastConfig）也共用此前綴。

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節，**待前端對照**。推測的最小頁面組成：

### 9.1 試算頁

- 條件區：區域下拉（必）、門店下拉（可選）、銷售資料區間、預測週起訖、預測加成（含 100% 表示無加成 / 或顯示為 +10%）
- 試算按鈕 → 觸發 `/product-recipe-analysis`
- 結果：三層折疊樹「店 → 產品（顯示總銷量）→ 食材（明細表格）」
- 食材表格欄位：食材名 / 單位 / 平日預測 / 假日預測 / 平日箱換算 / 假日箱換算 / 廠商 / 庫存提示
- 編輯：人工調整某行 weekdaySales → 觸發 `/calculate-projected-sales` 重算該行
- LONG 且充足：顯示「判斷庫存」灰色文字（不是數字）
- LONG 且不足：顯示警告圖示 + 當前庫存
- 儲存按鈕 → `/create-with-details` → 進入分頁列表

### 9.2 預測單分頁

- 條件區：區域、門店、流程狀態、週起訖區間、建立時間區間
- 表格：單據編號 / 簽核單號 / 區域 / 門店 / 預測週 / 流程狀態 / 建立人 / 建立時間 / 操作

### 9.3 待簽分頁

- 與分頁相似，但只顯示自己作為 assignee 的單據
- 操作：核准 / 退回 / 改派

### 9.4 預測配置維護頁

- 列表：配置名、範圍（區域 / 門店 / 全公司）、排程 cron、啟用狀態
- 編輯：新增 / 編輯 / 啟用 / 停用 / 手動 run-now
- 互斥提示：加入範圍前 precheck，啟用時即時掃衝突

---

## 10. 功能範圍

### 10.1 包含的功能

- 食材需求預測即時試算（BOM 展開）
- 平日 / 假日分流計算
- LONG 食材安全存量跳過邏輯
- 廠商報價箱換算
- 編輯後重算
- 建立 / 更新 / 刪除預測單（含明細）
- 分頁查詢 + 待簽分頁
- BPM 流程綁定
- 已歸檔保護
- 資料權限自動過濾
- 預測配置（排程、互斥、啟停、手動觸發）

### 10.2 預留但尚未實作

- **配方圖形化檢視**：目前只是表格展開
- **多週 / 月度預測**：目前只支援單週
- **跨區比較**：不能一次跑兩個區做對比
- **歷史試算結果存查**：每次試算都重算，沒有「上次試算結果」緩存
- **明細的更新邏輯細節未完整讀取**（程式碼超過 1000 行，文件僅含關鍵段落）

### 10.3 不包含

- 安全存量本身的維護（屬於 [庫存管理 > 安全存量設定]）
- 食譜（BOM）本身的維護（屬於 [PDM > 單品維護作業]）
- 廠商報價本身的維護（屬於 [採購管理 > 廠商報價維護作業]）
- 銷售歷史的記錄（屬於漢堡王中繼系統）
- 門店與分群的維護（屬於漢堡王中繼系統，見 PRD #22）
- 物料需求預測非 BOM（屬於 PRD #25）
- 採購單建立（屬於 [採購管理 > 採購單管理]，預測單通常會作為採購單的依據）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| 資料表前綴 `crg_` 與 PDM 其他模組的 `pdm_` 不一致 | 命名混亂；前綴語意未說明 | `DemandForecastDO.java:22` |
| `forecastMode` 業務語意？有哪些合法值？ | 程式無字典轉換，無預設值清單 | `DemandForecastDO.java:57` |
| `processStatus` 是否要字典化？ | 目前用字面字串「待處理 / 待簽核 / 已歸檔」，前端比對需硬編 | `DemandForecastServiceImpl.java:866、892` |
| 「平日」「假日」的定義（週一至週四 vs 週五至週日）是否符合業務認知？ | 程式碼註解寫週一四 vs 五日，但連假、補班是否要重新分類？ | `DemandForecastServiceImpl.java:324` 註解 |
| BOM 與非 BOM 試算共用權限 `pdm:demand-forecast:*` 是否合理？ | 兩功能語意不同，應分權限 | Controller `@PreAuthorize` |
| 即時試算未做結果緩存，每次重算耗時 | 大區域試算可能很慢（中繼 + 多次 batch DB 查詢） | `getProductRecipeAnalysis` 無快取 |
| 中繼銷售統計快取期 5 分鐘是否合理？ | 太長可能拉不到最新 / 太短會打中繼太頻繁 | `getCompletedOrdersFilterCached` 註解 |
| `singlePackCount = 0` 時箱換算回 null，是否需明確報警？ | 採購會不知道為什麼沒箱換算 | `DemandForecastServiceImpl.java:807-818` |
| LONG 食材「查無安全存量視為低於」是否為產品決策？ | 程式設計保守，但業務可能覺得「沒設定 → 不用算」 | `DemandForecastServiceImpl.java:835-837` |
| 「食材小類」`ingredientSubcategoryDetailId` 必填條件下才套用 LONG 邏輯，為何？ | 業務規則需釐清，是否該對所有 LONG 都套用？ | `DemandForecastServiceImpl.java:850` |
| 預測加成 % 的格式（`1.10` vs `10`）是否前後一致？ | `forecastIncrementPercent.multiply(...)` 直接乘，所以是「乘數」如 1.10；但欄位描述為「預測加成(%)」易讓人填 10 | `DemandForecastServiceImpl.java:778-783` |
| 「signCode」由 menuService.generateSignCode 產生 — 規則為何？ | 簽核單號格式對審計重要 | `DemandForecastServiceImpl.java:864` |
| 試算結果中沒有「總計」（區域 / 店 / 產品 / 食材的彙整列） | 報表常見需求，前端要自行加總 | 程式碼結構 |
| 已歸檔的更新拒絕邏輯是否還會影響 processStatus 變更？ | 流程節點若需 active update 已歸檔的單，會被擋 | `validateDemandForecastExists` |
| `documentCode` 與 `signCode` 並存的意義？ | 兩個字串欄位，業務語意分工需釐清 | `DemandForecastDO.java:45、52` |
| 試算頁的「銷售資料區間」與「預測週起訖」是否需驗證合理性（不重疊、不未來等）？ | 程式碼無檢查 | Controller 無交叉驗證 |
| `weekdayDemandAmount/Count` 與 `weekdayAverageSales` 等多個近似欄位的差異？ | 欄位多達 25+，名稱接近，PM 需逐一釐清業務含義 | `DemandForecastDetailDO.java` |
| 預測配置的「互斥」具體規則？兩配置「同區同時段」算衝突？跨區跨時段算不算？ | 程式有 precheck 但規則不明 | `DemandForecastConfigController.java:50-54` |
| 當前端要編輯已存在的明細時，後端是否完整更新或刪舊插新？ | 程式邏輯未完整讀取 | `updateDemandForecastWithDetails` |
| 多人同時編輯同一單頭的併發處理？ | 無版本欄位、無鎖機制 | DO 無 version 欄位 |
| 排程自動建立預測單時的「建立人」是誰？ | BPM 通常需要 assignee | `DemandForecastConfigServiceImpl.runNow` 未讀 |
