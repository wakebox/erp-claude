# PRD：需求集合（Demand Aggregation）模組 — 逆向規格分析

> 對應 `erp-claude/document/excel.md` 中「需求集合」業務主模組（序號 24~26）。
> 三個系統主功能：
> 1. 食材需求預測試算表（BOM）
> 2. 物料需求預測試算表（非 BOM）
> 3. 臨時需求審核
>
> 本 PRD 為**逆向分析**輸出，目的是把目前散落在 `kingmaker-module-pdm` 的程式碼還原成可被業務方審閱的規格文件。
> 與 [`PDM_PRD.md`](PDM_PRD.md) 的差異：本文件**只談需求集合三個功能**，並對應到 Excel 業務清單的命名；PDM_PRD 是整個 PDM 模組的規格。

---

## Problem Statement

漢堡王台灣的「需求集合」業務模組是採購與物流的**起點**：把門市的食材/物料需求量化成可下單的數量，再轉手給採購與物流。但目前：

1. **缺乏功能對應表**：Excel 清單（excel.md）用業務語言「食材需求預測試算表 / 物料需求預測試算表 / 臨時需求審核」描述，但程式碼用 `DemandForecast / RawMaterialDemand / TempReq`，業務方無法對照。
2. **「物料需求預測試算表（非 BOM）」沒有獨立實作**：程式碼只實作了 BOM 展開版本（`getProductRecipeAnalysis` 透過 `pdm_product_recipe_rel` 走 BOM 推算食材）。非 BOM 的物料（例如包材、清潔用品、文具）目前沒有對應的試算表入口。
3. **試算公式無書面紀錄**：每萬元平均用量、預測增量、LONG/SHORT 安全存量分支邏輯都埋在 `DemandForecastServiceImpl.buildIngredientDetail()` 裡，業務方無法驗證對錯。
4. **歸檔後不會自動生成下游單據**：`DemandForecastStatusListener` 與 `processDemandForecastArchived()` 留有 TODO，沒有把歸檔的需求預測單接到原物料需求行事曆（`pdm_raw_material_demand_head`）。
5. **三個功能的 ER 與資料流向沒有圖**：需求預測 → 原物料需求行事曆 → 物流 → 採購是核心鏈條，但連 sign_code 字串關聯這種「鬆耦合設計」都沒寫下來，新人完全看不出來。

---

## Solution

產出本 PRD，作為「需求集合」模組的**權威逆向規格**：

1. 業務功能 ↔ 程式碼對照表（Excel 名稱 ↔ Controller/Service/DO）
2. 三個功能的 ER Model（含跨表 sign_code 鬆耦合關係）
3. 每張資料表的完整欄位清單（語意、單位、計算來源）
4. 食材需求預測的**計算公式還原**（LONG/SHORT 分支、安全庫存比對、箱數換算）
5. BPM 審批流綁定與狀態流轉
6. 三個功能的 API 端點清單
7. 已知缺口（含非 BOM 試算表、歸檔後自動生成原物料需求等）

---

## 功能 ↔ 程式碼對照表

| Excel 序號 | Excel 名稱 | 程式對應 | 狀態 |
|---|---|---|---|
| 24 | 食材需求預測試算表（BOM） | `DemandForecastController` + `DemandForecastDetailController` + `DemandForecastConfigController`<br/>+ DO：`DemandForecastDO`、`DemandForecastDetailDO`、`DemandForecastConfigDO`、`DemandForecastConfigScopeDO`<br/>+ 表：`crg_demand_forecast`、`crg_demand_forecast_detail`、`crg_demand_forecast_config`、`crg_demand_forecast_config_scope` | ✅ 計算 + 審批<br/>❌ 歸檔後生成原物料需求（TODO）|
| 25 | 物料需求預測試算表（非 BOM） | **目前無對應實作** | ❌ 完全缺失（見 Out of Scope 註記）|
| 26 | 臨時需求審核 | `TempReqController`、`TempReqService(Impl)`、`TempReqStatusListener`<br/>+ DO：`TempReqDO`、`TempReqDetailDO`<br/>+ 表：`crg_temp_req`、`crg_temp_req_detail` | ✅ 完整（CRUD + BPM + 試算）|

下游關聯（不屬於本模組但被引用）：
- `pdm_raw_material_demand_head`、`pdm_raw_material_demand_date_list`、`pdm_raw_material_demand_detail` → 原物料需求行事曆（屬於採購/物流模組）
- `crg_demand_forecast.sign_code` → 透過字串掛載至 `pdm_raw_material_demand_date_list.demand_relation_doc`
- `crg_temp_req.sign_code` → 透過字串掛載至 `pdm_raw_material_demand_date_list.temp_relation_doc`

---

## User Stories

### 食材需求預測試算表（BOM）

#### 預測排程設定

1. 作為**採購主管**，我想建立**需求預測設定（DemandForecastConfig）**，定義設定名稱、預測模式（如「區域-季」）、Quartz Cron 表達式、需求週數、銷售資料天數、預測增量百分比（如 1.05）。
2. 作為**採購主管**，我想為一筆設定維護**適用範圍（DemandForecastConfigScope）**：可以「全區域」（只填 regionId）或「指定門市」（regionId + storeId）。
3. 作為**採購主管**，我想在儲存設定後**啟用（enable）**，系統會即時掃描是否有兩個 config 覆蓋同一門市；若有衝突則回傳衝突清單並標記 `conflict_flag=1`，不允許啟用。
4. 作為**採購主管**，我想在送出範圍前先呼叫**預檢（precheck）**，提前看到衝突，避免送出後被擋。
5. 作為**採購主管**，我想**停用（disable）**設定（不刪資料，只將 `enabled=0`），讓對應門市暫時跳過排程。
6. 作為**採購主管**，我想手動**立即執行（run-now）**某個設定（指定一個或多個 scope），無需等到 Cron 觸發。
7. 作為**系統**，每次成功執行後，我要回寫 `last_success_time` 作為下次續跑的斷點。

#### 需求預測單建立

8. 作為**門市採購人員**或**區域採購主管**，我想透過 `/bk/all-areas-with-stores` 或 `/bk/group-summaries` 取得漢堡王中繼的「區域 → 門市」清單，作為建立預測單的選擇基礎。
9. 作為**採購人員**，我想指定**預測週區間（weekStartDate ~ weekEndDate）**、**銷售分析期間（salesStartDate ~ salesEndDate）**、**預測增量倍率（forecastIncrementPercent）**。
10. 作為**採購人員**，我想呼叫**產品配方分析（`product-recipe-analysis`）**，系統會：
    1. 呼叫漢堡王中繼 `/api/burgerking/admin/order/completed/filter` 取得各門市各產品的完成訂單統計（平日/假日銷量、平日/假日金額倍率、平日/假日天數）。
    2. 用 `pdm_product_recipe_rel` + `pdm_single_serving_recipe` 把每個產品展開成食材清單。
    3. 對每一筆「產品 × 食材」，套用公式（見 Implementation Decisions）計算每萬元平日/假日平均用量與預測用量。
    4. 對「**長效食材（storage_type = LONG）且有副類型**」，額外比對該門市的安全存量與當前庫存；當「庫存 ≥ 安全存量」時跳過試算，前端只顯示「判斷庫存」字樣；當「庫存 < 安全存量」時補上 `is_safety_stock_warning=true` 並回填 `current_stock`。
    5. 若有傳 `storeId`，用 `pdm_vendor_quote` 撈廠商最新報價並補上 `vendor_name`、`weekday_box_conversion`、`holiday_box_conversion`（換箱數）。
11. 作為**採購人員**，我想在前端**手動調整平日/假日銷售數字**，呼叫 `calculate-projected-sales` 即時重新計算 `projected_weekday_average_sales_per10k` 與 `projected_holiday_average_sales_per10k`。
12. 作為**採購人員**，我想呼叫 `create-with-details` 一次性建立**單頭（DemandForecast）+ 單身（DemandForecastDetail）**；系統自動生成 `sign_code`，並依「選單是否綁定流程」決定是否發起 BPM 流程實例。
13. 作為**採購人員**，我想用 `update-with-details` 編輯尚未歸檔的需求預測單（單頭 + 子表整批刪後重建）。

#### 需求預測審批

14. 作為**審批人**，我想在 `/pdm/demand-forecast/todo-page` 看到指派給我的待辦預測單（任意流程節點），逐一審核或退件。
15. 作為**系統**，當審批通過（`BpmTaskStatusEnum.APPROVE`），`DemandForecastStatusListener` 監聽 `BpmProcessInstanceStatusEvent`，將 `process_status` 改為「已歸檔」並執行 `processDemandForecastArchived(headerId)` 後置邏輯。
16. 作為**系統**，當審批退件，狀態回到「待處理」（目前 listener 中註解掉，需確認）。
17. 作為**採購人員**，我想在 `/pdm/demand-forecast/page` 以「門市區域模糊、需求門市模糊、週期區間、流程狀態」組合查詢預測單。

#### 歸檔後處理（缺口）

18. 作為**系統**，預測單歸檔後我想自動把每筆 `crg_demand_forecast_detail` 累加成 `pdm_raw_material_demand_head` + `pdm_raw_material_demand_date_list` + `pdm_raw_material_demand_detail` 的行事曆資料，並用 `sign_code` 串回原始預測單。（**目前未實作，TODO 在 `processDemandForecastArchived()`**）

### 物料需求預測試算表（非 BOM）— 規格化但未實作

19. 作為**採購人員**（非 BOM 物料），我想為包材、清潔用品、文具等「不走食譜展開」的物料建立預測試算表。
20. 作為**採購人員**，我想直接以「品項 + 預測週 + 銷售期間 + 增量倍率 + 人工填寫的歷史用量」算出需求，無需走 product_recipe_rel 展開。
21. 作為**採購人員**，我想送出 BPM 審批，歸檔後同樣寫入原物料需求行事曆。
22. （**注意：本功能在程式碼內沒有對應入口，需另立 OpenSpec 變更獨立規劃。本 PRD 把它列為已知缺口。**）

### 臨時需求審核

23. 作為**門市人員**，我想在正式預測週期之外，建立**臨時需求單（TempReq）**，填寫申請單位、單據編號、簽核單號、門市區域、需求門市、需求週區間、主旨。
24. 作為**門市人員**，我想在臨時需求單下填寫**明細（TempReqDetail）**，指定 `productId`（單品 ID）+ `appliTempNum`（申請臨時需求量），系統自動補 `prod_code`（食譜產品代碼）與 `ing_prod_code`（食材品號）。
25. 作為**門市人員**，我想呼叫 `GET /pdm/temp-req/get?id=` 看臨時需求試算結果：系統依每個產品的食譜（`pdm_single_serving_recipe`）展開成食材列表，並計算每個食材的 `tempReqQuantity = standardQuantity × appliTempNum`，產出 `tempReqFinalNum`。
26. 作為**門市人員**，我想匯出**臨時需求 Excel**（`export-excel`）作為紙本走簽用。
27. 作為**審批人**，我想在 `/pdm/temp-req/todo-page` 看到指派給我的臨時需求單，逐一審核。
28. 作為**系統**，當審批通過，`TempReqStatusListener` 監聽 `BpmProcessInstanceStatusEvent` 並將 `process_status` 改為「已歸檔」。
29. 作為**採購人員**，我想在 `/pdm/temp-req/page` 以「申請單位、需求門市、區域、狀態、單號」組合查詢臨時需求單；前端依登入者的 `loginUserAreaId` / `loginUserStoreId` 自動限縮範圍。
30. 作為**臨時需求單建立者**，我想能更新或刪除**未歸檔**的單據；**已歸檔且未綁流程**的單據應被拒（`TEMP_REQ_ARCHIVED_CANNOT_UPDATE`）。
31. 作為**系統**，臨時需求歸檔後我想把 `sign_code` 寫進 `pdm_raw_material_demand_date_list.temp_relation_doc`，讓行事曆能追溯臨時需求來源。（**目前 listener 內沒有對應寫入邏輯，與預測單歸檔同屬 TODO。**）

---

## Implementation Decisions

### 1. 子域劃分（需求集合）

| 子域 | 核心資料表 | 說明 |
|---|---|---|
| 預測排程設定 | `crg_demand_forecast_config`、`crg_demand_forecast_config_scope` | 多筆 Config × 多筆 Scope，啟用瞬間掃描衝突 |
| 食材需求預測單 | `crg_demand_forecast`、`crg_demand_forecast_detail` | 表頭 + 表身，sign_code 為跨域 key |
| 臨時需求 | `crg_temp_req`、`crg_temp_req_detail` | 表頭 + 表身，sign_code 為跨域 key |
| 下游耦合（非本模組擁有） | `pdm_raw_material_demand_head/date_list/detail` | 透過 sign_code 字串掛載 |

---

### 2. ER Model（文字描述）

```
預測排程設定:
  crg_demand_forecast_config (1) ──< crg_demand_forecast_config_scope (config_id FK)
  crg_demand_forecast_config_scope >── 漢堡王 region/store [邏輯外鍵，僅存 regionId/storeId]

食材需求預測單（BOM）:
  crg_demand_forecast (1) ──< crg_demand_forecast_detail (parent_id FK)
  crg_demand_forecast_detail >── pdm_ingredient (ingredient_id) [邏輯外鍵]
  crg_demand_forecast_detail >── pdm_product_recipe_rel (product_id 路徑) [邏輯關聯]
  crg_demand_forecast_detail >── 漢堡王 product (product_id) [邏輯外鍵]
  crg_demand_forecast >── crg_demand_forecast_config [無實體 FK；由排程或手動 run-now 觸發]

臨時需求:
  crg_temp_req (1) ──< crg_temp_req_detail (parent_id FK)
  crg_temp_req_detail >── pdm_recipe (product_id) [邏輯外鍵：透過 prodCode 對應]
  crg_temp_req_detail >── pdm_ingredient_specs (ingredient_id) [邏輯外鍵：透過 ingProdCode 對應]

跨域鬆耦合（透過 sign_code）:
  crg_demand_forecast.sign_code ──→ pdm_raw_material_demand_date_list.demand_relation_doc
  crg_temp_req.sign_code        ──→ pdm_raw_material_demand_date_list.temp_relation_doc
```

```
┌───────────────────────────────┐
│ crg_demand_forecast_config    │
│ (排程、增量%、適用範圍主檔)    │
└───────┬───────────────────────┘
        │ 1
        │
        │ n
┌───────▼───────────────────────┐
│ crg_demand_forecast_config_   │
│ scope (regionId/storeId)      │
└───────────────────────────────┘

┌───────────────────────────────┐         ┌───────────────────────────────┐
│ crg_demand_forecast (單頭)     │         │ crg_temp_req (單頭)            │
│ - signCode                    │         │ - signCode                    │
│ - processStatus               │         │ - processStatus               │
│ - processInstanceId           │         │ - processInstanceId           │
└───────┬───────────────────────┘         └───────┬───────────────────────┘
        │ 1                                       │ 1
        │ n                                       │ n
┌───────▼───────────────────────┐         ┌───────▼───────────────────────┐
│ crg_demand_forecast_detail    │         │ crg_temp_req_detail           │
│ - parentId                    │         │ - parentId                    │
│ - productId / ingredientId    │         │ - productId / ingredientId    │
│ - 平日/假日 銷量 + 金額 + 預測 │         │ - appliTempNum / tempReq*     │
└───────────────────────────────┘         └───────────────────────────────┘
        │  signCode                                │  signCode
        └────────────────┬─────────────────────────┘
                         │
                         ▼ (跨域，字串掛載)
                 pdm_raw_material_demand_date_list
                  ├── demand_relation_doc
                  └── temp_relation_doc
```

---

### 3. 資料表詳細規格

#### 3.1 `crg_demand_forecast_config`（需求預測設定）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵（KeySequence: `crg_demand_forecast_config_id_seq`）|
| name | VARCHAR | 設定名稱（如「全區域標準週預測」）|
| enabled | INT | 1=啟用, 0=停用 |
| conflict_flag | INT | 1=有衝突（列表橙色標籤）, 0=無衝突 |
| forecast_mode | VARCHAR | 預測模式（如「區域-季」）|
| cron_expression | VARCHAR | Quartz Cron 表達式 |
| demand_weeks | INT | 需求週數（如 4）|
| sales_days | INT | 銷售資料天數（最近 N 天）|
| data_length_days | INT | 資料長度（如 28）|
| forecast_increment_percent | DECIMAL | 預測增量倍率（1.00=100%, 1.05=105%）|
| last_success_time | TIMESTAMP | 上次成功執行的斷點時間 |
| + BaseDO | | deleted、tenant_id、creator、create_time、updater、update_time |

#### 3.2 `crg_demand_forecast_config_scope`（預測設定適用範圍）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| config_id | BIGINT FK→`crg_demand_forecast_config` | 設定 ID |
| region_id | INT NOT NULL | 區域 ID（漢堡王中繼）|
| store_id | INT NULLABLE | 門市 ID（漢堡王中繼）；NULL 表示「該區域全部門市」|

**互斥規則**：同一個 `(region_id, store_id)` 不得被兩個啟用中的 config 同時涵蓋；「region_id, NULL」涵蓋的是該區域的所有門市，要與該區域下任何「region_id, store_id」互斥。

#### 3.3 `crg_demand_forecast`（食材需求預測 — 單頭）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| document_date | DATE | 單據日期 |
| document_code | VARCHAR | 單號 |
| sign_code | VARCHAR | 簽核單號（由 `MenuService.generateSignCode("需求預測試算表")` 產生，是跨域 key）|
| forecast_mode | VARCHAR | 預測模式 |
| store_region | VARCHAR | 門市區域名稱（冗餘存名）|
| demand_store | VARCHAR | 需求門市名稱（冗餘存名）|
| week_start_date | DATE | 預測週起 |
| week_end_date | DATE | 預測週迄 |
| forecast_increment_percent | DECIMAL | 預測增量% |
| sales_start_date | DATE | 銷售分析起 |
| sales_end_date | DATE | 銷售分析迄 |
| process_status | VARCHAR | 流程狀態：「待處理」/「審批中」/「已歸檔」/「已退件」|
| subject | VARCHAR | 主旨 |
| region_id | INT | 區域 ID（外部）|
| store_id | INT | 門市 ID（外部）|
| process_instance_id | VARCHAR | Flowable 流程實例 ID |
| + BaseDO | | |

#### 3.4 `crg_demand_forecast_detail`（食材需求預測 — 單身）

> 完整欄位（共 30 個）已列於 `PDM_PRD.md §資料表 22`，本節僅補充「需求集合」視角下的語意與計算來源。

關鍵欄位：

| 欄位 | 來源 | 語意 |
|---|---|---|
| parent_id | FK→crg_demand_forecast | 所屬單頭 |
| region / store_name | 漢堡王中繼快照 | 冗餘存名 |
| region_id / store_id | 漢堡王中繼 | 外部 ID |
| product_id / product_name | `ProductSalesStatisticsVO.productId` | 漢堡王產品 |
| weekday_sales / weekend_sales | 前端輸入 | 使用者**手動填寫**的銷售額（萬元）|
| ingredient_id / ingredient_name / prod_code | `pdm_product_recipe_rel` + `pdm_single_serving_recipe` | 由 BOM 展開 |
| standard_amount / amount_unit | `pdm_single_serving_recipe.standardAmount/unit` | 單份標準用量 |
| standard_quantity / quantity_unit | `pdm_single_serving_recipe.singleSpec/singleSpecUnit` | 單份標準數量 |
| weekday_order_amount / holiday_order_amount | `multiplier × 10000` | 訂單金額（元）|
| weekday_average_sales_per10k / holiday_average_sales_per10k | `multiplier × 10000 × standardQuantity` | 每萬元平均用量 |
| projected_weekday/holiday_average_sales_per10k | `× forecast_increment_percent` | 預測平均（依 BigDecimal 規則四捨五入 scale=2）|
| weekday_average_sales / holiday_average_sales | `orderAmount ÷ dayCount` | 每日平均銷售（scale=2）|
| weekday_count / holiday_count | `ProductSalesStatisticsVO` | 平假日天數 |
| weekday_demand_amount / weekend_demand_amount | （目前 builder 未填入）| 預留：平日/假日需求計量 |
| forecast_demand | （目前 builder 未填入）| 預留：最終預測需求 |

#### 3.5 `crg_temp_req`（臨時需求 — 單頭）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | INTEGER PK | 主鍵 |
| apply_unit | VARCHAR | 申請單位 |
| document_code | VARCHAR | 單據編號 |
| sign_code | VARCHAR | 簽核單號（由 `generateSignCode("臨時需求審核")` 產生）|
| store_region | VARCHAR | 門市區域名稱 |
| demand_store | VARCHAR | 需求門市名稱 |
| region_id | INT | 區域 ID（漢堡王中繼）|
| store_id | INT | 門市 ID（漢堡王中繼）|
| week_start_date | TIMESTAMP | 需求週起 |
| week_end_date | TIMESTAMP | 需求週迄 |
| subject | VARCHAR | 主旨 |
| process_status | VARCHAR | 流程狀態 |
| process_instance_id | VARCHAR | Flowable 流程實例 ID |
| + BaseDO | | |

#### 3.6 `crg_temp_req_detail`（臨時需求 — 單身）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | INTEGER PK | 主鍵 |
| parent_id | INTEGER FK→`crg_temp_req` | 所屬單頭 |
| product_id | BIGINT | 單品 ID（對應 `pdm_recipe.id`）|
| prod_code | VARCHAR | 食譜產品代碼（從 `pdm_recipe.productCode` 自動帶入）|
| ingredient_id | BIGINT | 食材 ID（對應 `pdm_ingredient_specs.id`）|
| ing_prod_code | VARCHAR | 食材品號（從 `pdm_ingredient_specs.prodCode` 自動帶入）|
| appli_temp_num | INT | 申請臨時需求量 |
| temp_req_quantity | INT | 臨時需求計數（試算結果：`standardQuantity × appliTempNum`）|
| temp_req_final_num | INT | 臨時需求最終數量（試算後或人工調整）|

---

### 4. 食材需求預測計算公式（逆向還原）

> 來源：`DemandForecastServiceImpl.buildIngredientDetail()` + `calculateProjectedSales()`。

#### 4.1 變數定義

| 變數 | 來源 | 說明 |
|---|---|---|
| `weekdayMultiplier` / `holidayMultiplier` | 漢堡王中繼 `ProductSalesStatisticsVO` | 平日/假日的銷售比例（小數）|
| `weekdayCount` / `holidayCount` | 漢堡王中繼 | 平日/假日天數 |
| `standardQuantity` | `pdm_single_serving_recipe.singleSpec` | 單份標準數量 |
| `forecastIncrementPercent` | 前端輸入 | 預測增量倍率（1.05 = 105%）|
| `singlePackCount` | `pdm_vendor_quote` 最新報價 | 每箱個數 |
| `weekdaySales` / `weekendSales` | 前端輸入 | 使用者手動填寫的銷售額（萬元，整數）|

#### 4.2 公式（SHORT 或 LONG-低於安全存量分支）

```text
1. 訂單金額（元）
   weekdayOrderAmount = round(weekdayMultiplier × 10000)
   holidayOrderAmount = round(holidayMultiplier × 10000)

2. 每萬元平日/假日平均用量
   weekdayAverageSalesPer10k = weekdayMultiplier × 10000 × standardQuantity
   holidayAverageSalesPer10k = holidayMultiplier × 10000 × standardQuantity

3. 預測平均用量（套用增量）
   projectedWeekdayAverageSalesPer10k = weekdayAverageSalesPer10k × forecastIncrementPercent
   projectedHolidayAverageSalesPer10k = holidayAverageSalesPer10k × forecastIncrementPercent

4. 每日平均銷售（保留 2 位）
   weekdayAverageSales = weekdayOrderAmount / weekdayCount        (when weekdayCount > 0)
   holidayAverageSales = holidayOrderAmount / holidayCount        (when holidayCount > 0)

5. 箱數換算（需要 singlePackCount > 0）
   weekdayBoxConversion = projectedWeekdayAverageSalesPer10k / singlePackCount   (scale=2, HALF_UP)
   holidayBoxConversion = projectedHolidayAverageSalesPer10k / singlePackCount   (scale=2, HALF_UP)
```

#### 4.3 `calculateProjectedSales`（前端調整銷量後重算）

```text
avgSales        = sales / dayCount              (scale=8, HALF_UP)
avgSalesPer10k  = avgSales × 10000 / orderAmount(scale=8 → 2, HALF_UP)
projectedPer10k = avgSalesPer10k × standardQuantity            (scale=2, HALF_UP)
```

優先取基準（standardQuantity / weekdayOrderAmount / holidayOrderAmount / weekdayCount / holidayCount）：
1. 若帶 `parentId`：用 `selectFirstMapByParentIdAndProductIds` 取得該 parentId 下每個 productId 的第一筆已存明細的基準值。
2. 否則：用前端 `CalculationItem` 中回傳的同名欄位。

#### 4.4 LONG 食材的安全存量分支

只有「`storage_type=LONG` 且有副類型（`ingredient_subcategory_detail_id != null`）」會走此分支：

| 條件 | 行為 |
|---|---|
| 查無安全存量 | 視為「低於安全存量」（`isSafetyStockWarning=true`）|
| 查無門市庫存 | 視為「低於安全存量」（`isSafetyStockWarning=true`）|
| 當前庫存 < 安全存量 | `isSafetyStockWarning=true`，回填 `current_stock`，**執行完整 4.2 試算** |
| 當前庫存 ≥ 安全存量 | `isSafetyStockWarning=false`，**跳過試算**，box conversion = null，前端顯示「判斷庫存」|

非 LONG（SHORT 或 storage_type 為 null）→ `isSafetyStockWarning=null`，直接執行 4.2。

#### 4.5 廠商報價回填

- `storeId` 為空 → **嚴格模式**，不撈廠商，`vendor_name / box_conversion` 全為 null。
- `storeId` 不為空 → 用 `selectLatestVendorQuotesByProdCodesAndStoreId(prodCodes, storeId, demandWeekStartTime)` 撈每個品號最新報價，補 `vendor_name` + 計算箱數。

---

### 5. 臨時需求試算邏輯（GET /pdm/temp-req/get）

呼叫 `TempReqServiceImpl.getTempReq(id)`：

1. 撈臨時需求單頭。
2. 撈該單下所有單品（含 product 名稱）。
3. 用 `selectIngredientInfo(recipeIdList)` 把每個單品展開成食材清單（含 `standardAmount`、`standardQuantity`、`recipeId`）。
4. 依公式計算：
   ```
   tempReqQuantity = standardQuantity × appliTempNum
   tempReqFinalNum = tempReqUnit ?? tempReqQuantity      (優先用 unit；標準寫法待澄清)
   ```
   - 註：原始程式碼中 `tempReqUnit` 的計算被註解掉，目前只剩 `tempReqQuantity`。
5. 回傳 `TempReqRespVO`，含 `tempReqDetailRecipeDTOS`（按產品分組，每組下含食材列表）。

---

### 6. BPM 流程綁定

| 模組 | FormPathUniqueEnum | 路徑 | sign_code 前綴 |
|---|---|---|---|
| 食材需求預測 | `DEMAND` | `reqCalculation` | 需求預測試算表-* |
| 臨時需求 | `TEMP_REQ` | `tempReq` | 臨時需求審核-* |

**businessKey 格式**：`{formPath}:{headerId}`（例如 `reqCalculation:42`）。Listener 用前綴判斷是否屬於自己。

**流程狀態流轉**：

```
建立 → 待處理 → [若選單綁流程] 審批中 → 已歸檔 / 已退件
                ↓
            [若選單未綁流程] 直接歸檔（前端傳 processStatus="已歸檔"）
```

**回到「待處理」的退件分支**：`DemandForecastStatusListener` / `TempReqStatusListener` 在 REJECT / CANCEL 分支目前**僅留註解**，未實作。

---

### 7. 外部依賴（漢堡王中繼 API）

| API | 用途 |
|---|---|
| `/api/burgerking/admin/store/group-with-stores/inner` | 取得區域 + 門市清單（缺城市/縣市）|
| `/api/burgerking/admin/area-group/all-areas-with-stores` | 取得完整 group → area → store 三層 |
| `/api/burgerking/admin/order/completed/filter` | 取得完成訂單統計（產品銷量、平日/假日金額倍率、天數），**是需求預測的核心輸入** |

`BurgerKingStoreClient` 由 `BurgerKingTokenManager` 自動維護 token（有效期 55 分鐘）。

---

### 8. API 端點清單

#### 需求預測設定（`/pdm/demand-forecast-config`）

| Method | Path | 用途 |
|---|---|---|
| GET | `/list` | 列出全部設定（含 scope）|
| GET | `/get?id=` | 取得設定詳情 |
| POST | `/save` | 新增/編輯（啟用狀態下強校驗互斥）|
| POST | `/precheck` | 預檢適用範圍互斥 |
| PUT | `/enable?id=` | 啟用（瞬間掃描衝突）|
| PUT | `/disable?id=` | 停用 |
| POST | `/run-now` | 手動觸發執行 |

#### 食材需求預測單（`/pdm/demand-forecast` + `/pdm/demand-forecast/detail`）

| Method | Path | 用途 |
|---|---|---|
| GET | `/pdm/demand-forecast/page` | 統一分頁查詢（區域/門市/週/狀態）|
| GET | `/pdm/demand-forecast/todo-page` | 我的待辦預測單 |
| DELETE | `/pdm/demand-forecast/deleteBatch` | 批次刪除 |
| PUT | `/pdm/demand-forecast/update-process-status` | 直接更新流程狀態 |
| GET | `/pdm/demand-forecast/detail/get-with-header?id=` | 取得單頭 + 結構化單身（按門店→產品→食材）|
| GET | `/pdm/demand-forecast/detail/bk/all-areas-with-stores` | 中繼三層區域樹 |
| GET | `/pdm/demand-forecast/detail/bk/group-summaries` | 中繼區域摘要 |
| GET | `/pdm/demand-forecast/detail/bk/stores-by-group?groupId=` | 中繼指定區域的門市 |
| GET | `/pdm/demand-forecast/detail/product-recipe-analysis` | **試算入口**：分析中繼銷售 + 展開食譜 + 計算預測 |
| POST | `/pdm/demand-forecast/detail/calculate-projected-sales` | 前端調整銷量後重算 |
| POST | `/pdm/demand-forecast/detail/create-with-details` | 一次性建立單頭 + 單身 |
| PUT | `/pdm/demand-forecast/detail/update-with-details` | 一次性更新單頭 + 單身 |
| DELETE | `/pdm/demand-forecast/detail/deleteBatch` | 批次刪除明細 |

#### 臨時需求審核（`/pdm/temp-req`）

| Method | Path | 用途 |
|---|---|---|
| POST | `/create` | 建立臨時需求 |
| PUT | `/update` | 更新（未歸檔可改）|
| DELETE | `/delete?id=` | 刪除 |
| GET | `/get?id=` | 取得單頭 + 試算後的明細結構 |
| GET | `/page` | 分頁查詢 |
| GET | `/todo-page` | 我的待辦臨時需求 |
| GET | `/export-excel` | 匯出 Excel |
| GET | `/temp-req-detail/list-by-parent-id?parentId=` | 取得指定單頭的明細列表（無試算）|

#### 下游：原物料需求行事曆（屬於採購/物流，僅列出 reference）

| Method | Path | 用途 |
|---|---|---|
| GET | `/pdm/raw-material/list` | 行事曆主清單（門市區域 + 日期）|
| GET | `/pdm/raw-material/detail` | 行事曆食材明細（按需求日 + 門市）|

---

### 9. 權限命名

| 權限碼 | 用途 |
|---|---|
| `pdm:demand-forecast:query/create/update/delete` | 食材需求預測（單頭 + 單身共用）|
| `crg:temp-req:query/create/update/delete/export` | 臨時需求審核 |
| `pdm:raw-material:query` | 原物料需求行事曆（下游）|

---

## Testing Decisions

**好的測試定義**：只驗證對外行為（HTTP 回應、DB 變化、BPM 事件），不測私有方法或內部 SQL 結構。

**目前測試現況**：
- 已存在 `DemandForecastIngredientFilterTest.java`（單元測試，驗食材過濾邏輯）。
- 其餘無自動化測試，靠 Swagger UI 手動驗。

**建議優先測試模組**（若要補測試）：

1. **需求預測計算公式**（`buildIngredientDetail` + `calculateProjectedSales`）
   - 輸入：固定的銷售統計 + 食譜 + 增量倍率
   - 驗：每個 detail 欄位值符合 §4.2 公式
   - 為什麼：核心業務邏輯，最容易因 multiplier/scale 改變而錯
   - 已有 prior art：`DemandForecastIngredientFilterTest`

2. **LONG 食材安全存量分支**（`isLongIngredientLowSafety`）
   - 四個 case：查無安全存量 / 查無庫存 / 庫存 < 安全 / 庫存 ≥ 安全
   - 驗：四種 case 下 `isSafetyStockWarning` 與後續欄位回填正確

3. **預測排程設定互斥**（`precheck` + `enable`）
   - 兩個 config，一個「region=A, store=null」、一個「region=A, store=1」
   - 驗：`precheck` 回傳衝突清單；`enable` 第二個時擋下並設 conflict_flag=1

4. **BPM Listener 端到端**
   - 驗：審批通過後 `process_status` 變「已歸檔」，`process_instance_id` 保留可查
   - 驗：businessKey 不屬於本 listener 時，listener 不會誤處理

5. **臨時需求試算**（`getTempReq`）
   - 一筆單品 × 多筆食材 × `appliTempNum`，驗 `tempReqQuantity` 計算

---

## Out of Scope

1. **物料需求預測試算表（非 BOM）功能本體**：目前完全沒有實作；本 PRD 僅以 user story 形式描述需求方向，**實際做法需另立 OpenSpec 變更**（建議使用 `/opsx:new`）。
2. **歸檔後生成原物料需求行事曆的自動化**：`DemandForecastStatusListener.onEvent()` 的 APPROVE 分支與 `processDemandForecastArchived()` 都是 TODO；屬下游採購/物流模組的串接，需另立變更。
3. **退件 / 取消的狀態回退**：listener 中 REJECT、CANCEL 分支已寫成註解，本 PRD 不規範實作細節。
4. **PDM 其他子域**：食材、食譜、包材、單位、編碼管理已涵蓋於 `PDM_PRD.md`，本 PRD 不再贅述。
5. **前端 UI 細節**：本 PRD 只規範後端 API 合約與資料模型。
6. **資料庫 migration**：目前無 Flyway/Liquibase，schema 手動管理；本 PRD 列欄位但不負責 DDL 版本控。
7. **多租戶細節**：`BaseDO.tenant_id` 由 MyBatis Plus 自動注入，不在本 PRD 規範。

---

## Further Notes

### 已知缺口（對應 [UNKNOWNS.md](UNKNOWNS.md) / [BACKLOG.md](BACKLOG.md)）

| 缺口 | 影響 | 對應位置 |
|---|---|---|
| 物料需求預測試算表（非 BOM）完全缺失 | Excel 序號 25 對應功能無法執行 | excel.md L27 |
| 歸檔後不自動生成 `pdm_raw_material_demand_*` | 預測單核准後行事曆是空的，需手動補資料 | `DemandForecastServiceImpl.processDemandForecastArchived()`、`DemandForecastStatusListener` 的 APPROVE 分支 TODO |
| 臨時需求歸檔後不寫 `temp_relation_doc` | 行事曆無法回追臨時需求來源 | `TempReqStatusListener.onEvent()` |
| `tempReqUnit` 計算被註解 | `tempReqFinalNum` 永遠等於 `tempReqQuantity`，業務口徑可能不對 | `TempReqServiceImpl.getTempReq()` L170-174 |
| `weekday_demand_amount` / `weekend_demand_amount` / `forecast_demand` 欄位永遠為 null | 表身有欄位但 builder 沒填 | `DemandForecastServiceImpl.buildIngredientDetail()` |
| 退件 / 取消狀態不回退 | 退件後 process_status 卡在「審批中」 | 兩個 listener 的 REJECT/CANCEL 分支 |
| LONG 食材安全存量取數 | 目前用 `selectFirstSafetyStockByIngredientIds`「第一筆」，是否為最新版本？是否要過濾門市？ | `PdmProductRecipeRelMapper.selectFirstSafetyStockByIngredientIds` |
| 廠商報價篩選 | `selectLatestVendorQuotesByProdCodesAndStoreId` 中是否要加「廠商已歸檔」過濾？ | STATUS.md `PDM` 表中提及 |

### 命名與設計觀察

- **跨域鬆耦合用字串 sign_code**：而非 FK；好處是模組可以獨立刪資料而不撞外鍵，壞處是無法在 DB 層保證一致性。
- **單身整批刪後重建**：`updateDemandForecastWithDetails` 與 `updateTempReq` 都採「先刪整批子表 → 重新插入」，這代表外部如果 JOIN 子表的 id 會失效，依賴方需依 parentId 重撈。
- **多種 PageReqVO 並存**：`DemandForecastPageReqVO` / `RegionPageReqVO` / `StorePageReqVO` / `WeekRangePageReqVO` / `ProcessStatusPageReqVO` / `UnifiedPageReqVO` 六個，Controller 已收斂到 `UnifiedPageReqVO` 但其他 VO 與 Mapper 方法尚未清掉，屬技術債。
- **`crg_*` vs `pdm_*` 表前綴**：需求集合的核心表都是 `crg_*`（forecast/temp_req/config），原物料需求行事曆是 `pdm_*`；兩個 prefix 的取捨理由目前無書面紀錄。
- **「萬元」是系統慣用單位**：所有銷售與用量公式中的 10000 都是「萬元 → 元」的轉換係數。
