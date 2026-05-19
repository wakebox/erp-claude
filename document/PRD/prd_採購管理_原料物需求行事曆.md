# PRD｜採購管理 — 原料物需求行事曆

> 來源：逆向自 `kingmaker-module-pdm` 後端程式碼（`controller/admin/rawmaterial/RawMaterialDemandController.java` 為主，並參考 `rawmaterial1` 的 VO 與部分服務、`service/rawmaterial/RawMaterialDemandServiceImpl.java`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。
>
> ⚠️ **重要**：序號 30「原料物需求行事曆」在 PMM 模組內**無對應實作**，實作在 PDM 模組。本功能與 #25「物料需求預測試算表(非 BOM)」共用同一套資料表（`pdm_raw_material_demand_head` / `_date_list` / `_detail`），但本功能聚焦於**「行事曆視角」的查詢與檢視**，#25 聚焦於「建立與彙整」。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **採購規劃 / 物流規劃 / 區經理 / 店長**。我希望以「行事曆視角」看每個門市未來幾天的原物料需求：

> 「2026-05-26（一）信義店要進牛肉餅 50 公斤、起司 20 包、麵包 30 袋…」
> 「下週每天每店的需求量總覽，方便採購安排配送車次」

這份資訊不是「請購單」（請購單由人工建單），而是「**將需求預測（#24）與臨時需求（#26）的結果，依日期 / 門市攤平，並補上廠商與預計配送日**」。

### 1.2 我要做什麼

- 以「區域 + 日期區間 + 可選門市」查詢未來幾天的「需求日列表」
- 每筆需求日記錄包含：需求日、門市、預測單號 / 臨時需求單號（若有）、預估銷售量（萬元）
- 點某筆需求日，drill-down 看當日該門市的「食材明細」：品號、需求數量、廠商、預計配送日、模式（直送 / 配送）
- 平日 / 假日分流：以週五六日為假日，套用對應的需求量欄位（holidaySum / weekDaySum）

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 用行事曆視角看需求 | #25 的單頭分頁查詢以「批次試算」為單位，看不出每日每店的需求 |
| 同時整合預測 + 臨時需求 | 兩者分開看會漏掉行銷臨時加單 |
| 平日 / 假日自動套對應的需求量 | 銷量天差地遠，不該混算 |
| 看到廠商 / 預計配送日 | 物流規劃要安排配送車次 |
| 直接從預測單 / 臨時單號 drill-down | 點某天看細項 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 行事曆列表查詢（GET /list） | 主視圖：某區某段時間每天每店需求單號 |
| 食材明細查詢（GET /detail） | drill-down：某天某店的食材清單 |
| 平日 / 假日自動分流 | 取對應的 weekDaySum / holidaySum |
| 引用 #24 需求預測 + #26 臨時需求 | 兩源資料合併 |
| 跨模組共用 `pdm_raw_material_demand_*` 表 | 與 #25 共資料源 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 原料物需求行事曆 |
| 所屬模組 | Excel 列「採購管理」，**實作在 PDM 模組** |
| 兄弟功能 | 食材需求預測試算表 BOM（#24）、物料需求預測試算表 非 BOM（#25）、臨時需求審核（#26）、請購單管理（#31，下游） |
| 主要頁面 | 行事曆查詢頁、食材明細 drill-down |
| 簽核流程 | 無（純查詢） |
| Controller 對應 | `RawMaterialDemandController`（注意：非 `rawmaterial1` 的 controller，僅有 2 個查詢端點） |

---

## 2. 功能目的

原料物需求行事曆是「需求預測 + 臨時需求」結果的**展示層**，扮演「以時間軸把需求展開供物流規劃使用」：

1. **時間維度檢視** — 採購 / 物流以「日」「週」為單位看需求，而非以「試算批次」
2. **跨來源合併** — 同時整合 #24 預測結果與 #26 臨時加單
3. **平日 / 假日自動套用** — 依需求日是否為週五六日，自動取對應的 sum 欄位
4. **drill-down 模式** — 主畫面看總覽，點某天進去看細項
5. **唯讀** — 本功能不建單、不寫資料；資料源是 `crg_demand_forecast_detail` 與 `crg_temp_req_detail`，本功能只查詢與展示

---

## 3. 業務邏輯背景

### 3.1 兩個查詢端點

`RawMaterialDemandController` 只有兩個端點：

| 端點 | 用途 |
|---|---|
| `GET /pdm/raw-material/list` | 輸入區域、日期區間、可選門市 → 回每日每店的「需求單號彙整」（demandRelationDoc + tempRelationDoc + expectAmount） |
| `GET /pdm/raw-material/detail` | 輸入「需求日 + 預測單號 + 臨時單號」→ 回該日該店的食材清單，套用平日 / 假日 sum |

### 3.2 服務內部邏輯（`RawMaterialDemandServiceImpl`）

`getRawMaterialDemandList`：

1. 驗證 regionId 非空、startDate / endDate 非空
2. **storeId 非空 — 單店模式**：
   - 對日期區間內每一天：
     - 從 `demandForecastMapper.selectRawMaterialDemandOneStore` 撈當日該店的需求預測單號
     - 從 `tempReqMapper.selectRawMaterialDemandOneStore` 撈當日該店的臨時需求單號
     - 兩者都空 → 跳過
     - 任一有 → 組合輸出
3. **storeId 空 — 區域模式**：**目前直接 `return List.of();`**（未實作！）— 與 `rawmaterial1` 的 controller 不同（後者有實作區域模式）

來源：`RawMaterialDemandServiceImpl.java:48-78`。

⚠️ **明確的缺陷**：區域模式（不指定門店）回空清單，與 `rawmaterial1` 的同名端點行為不一致。詳見 §11。

### 3.3 食材明細邏輯

`getRawMaterialIngredientDetailList`：

1. 若 demandRelationDoc 與 tempRelationDoc 都空 → 回空清單
2. 若 demandRelationDoc 非空 → 撈 `selectDemandIngredientDetailList(demandRelationDoc)`，逐筆設：
   - 平日 → demandAmount = weekDaySum、expectDeliveryDate = demandDate
   - 假日 → demandAmount = holidaySum、expectDeliveryDate = demandDate
3. 若僅 tempRelationDoc 非空 → **未實作**（被註解掉）

⚠️ **缺陷**：只處理 demandRelationDoc 路徑，臨時需求的食材展開未實作；同時若兩者都有，只看 demandRelationDoc。詳見 §11。

### 3.4 平日 / 假日的定義

`isFridaySaturdayOrSunday(date)`：

- 週五、週六、週日 → 假日（true）
- 週一至週四 → 平日（false）

與 #24、#25 一致。

### 3.5 預計配送日

本功能的 `expectDeliveryDate` **直接設為 demandDate**（同一天） — 沒有反推「依物流類型推算的真正配送日」。

對比 #25 在建立時已根據 cycleType / logisticsCycle 算出實際配送日（如「週二的需求 → 週一配送」）。本功能查詢時**重新覆寫**這個欄位為 demandDate，造成資料與 #25 不一致（見 §11）。

### 3.6 與 #25 並存的關係

| 項目 | #25（物料需求預測試算表非 BOM） | #30（原料物需求行事曆） |
|---|---|---|
| 端點所在 | `rawmaterial1/RawMaterialDemandHeadController`（多端點，含建立） | `rawmaterial/RawMaterialDemandController`（僅查詢 2 個） |
| 用途 | 主要為**建立 + 彙整**（POST /create） | 主要為**檢視 + drill-down** |
| 區域模式 | 已實作（建立時逐店跑） | **未實作**（return List.of()） |
| 食材明細的兩源合併 | 已實作 | **未實作**（只看預測單） |
| 預計配送日 | 依 cycleType / logisticsCycle 反推 | 直接 = demandDate |
| 廠商綁定 | 建立時自動補 | 查詢時跟 SQL 取 |

**結論**：本功能在程式碼上**像是被棄置或未完成的早期版本**，`rawmaterial1` 才是現役。詳見 §11。

### 3.7 跨模組依賴

- `DemandForecastMapper.selectRawMaterialDemandOneStore` / `selectDemandIngredientDetailList`：依賴 #24 的資料表
- `TempReqMapper.selectRawMaterialDemandOneStore`：依賴 #26 的資料表
- 中繼 API（區域模式若實作會用到）

---

## 4. 情境說明

### 4.1 正常流程 — 看某店未來一週需求

採購規劃人員小王要看「信義店 2026-05-25 ~ 2026-05-31 的原料需求行事曆」：

1. GET /pdm/raw-material/list
   - regionId=3、storeId=11、startDate=2026-05-25、endDate=2026-05-31
2. 系統對每天：
   - 撈該日該店的預測單號 + expectAmount
   - 撈該日該店的臨時單號
   - 都無 → 跳過
   - 有 → 組合輸出
3. 回傳 7 筆（或更少，沒需求的天會被跳過）：
   ```
   2026-05-25 信義店 D-2026-0518-001 T-2026-0520-003 預估銷售 12.50 萬
   2026-05-26 信義店 D-2026-0518-001 null              預估銷售 10.00 萬
   2026-05-27 信義店 D-2026-0518-001 null              預估銷售 9.80 萬
   ...
   ```

### 4.2 典型業務 — 看某天的食材明細

小王點 2026-05-30（週六）那筆：

1. GET /pdm/raw-material/detail
   - demandRelationDoc=D-2026-0518-001、tempRelationDoc=null、demandDate=2026-05-30
2. 系統撈該預測單號的食材清單
3. 因 2026-05-30 是週六（假日）→ 對每筆食材：
   - demandAmount = holidaySum
   - expectDeliveryDate = 2026-05-30（直接 = demandDate）
4. 回傳：
   ```
   牛肉餅 LB-04   80 公斤  冷凍肉商  配送日 2026-05-30
   起司          30 包    起司商    配送日 2026-05-30
   ...
   ```

### 4.3 異常情境 — 區域模式

小王不指定門店，想看「整個北一區下週的需求行事曆」：

- GET /pdm/raw-material/list?regionId=3&storeId=null&startDate=...&endDate=...
- 系統 `storeId == null` 分支 → **直接 return List.of()**
- 前端拿到空清單，卻沒有任何錯誤或提示
- 使用者誤以為「整區沒有需求」

⚠️ 此為明顯 bug，需修復或文件化。

### 4.4 異常情境 — 同時有預測單與臨時單

某天該店同時有 demandRelationDoc 與 tempRelationDoc：

- `/list`：兩者都會回傳在同一筆 RawMaterialDemandDateListVO 中
- `/detail`：因為傳入的是「需求日 + 預測單號 + 臨時單號」，但 service 只判斷 demandRelationDoc → **臨時需求的食材清單會漏掉**

### 4.5 規則分流 — 區域 vs 門市過濾

服務目前依賴調用者明確傳入 regionId + storeId。**沒有自動套用登入者區域 / 門店過濾**（與 #24、#25 的 `SecurityFrameworkUtils.getLoginUser*` 機制不同） — 店長如果用 storeId 不為自己門店仍可查到別店資料。詳見 §11。

### 4.6 使用者鍵入錯誤 — 缺必填

- 漏 regionId → 拋 `RAW_MATERIAL_REGION_EMPTY`
- 漏 startDate / endDate → 拋 `RAW_MATERIAL_DATE_EMPTY`

---

## 5. 操作流程

```
[使用者進入「原料物需求行事曆」]
  │
  ├─ 1. GET /pdm/raw-material/list
  │    參數：regionId（必）、storeId（建議）、startDate/endDate（必）
  │    │
  │    ├─ 驗證 regionId / startDate / endDate
  │    ├─ storeId 非空 → 單店逐日查
  │    │    ├─ 撈該日 demandForecast 單號
  │    │    ├─ 撈該日 tempReq 單號
  │    │    ├─ 都空 → 跳過
  │    │    └─ 任一有 → 組合輸出
  │    └─ storeId 空 → 直接 return [] ⚠️ 未實作區域模式
  │
  └─ 2. GET /pdm/raw-material/detail
       參數：需求日 / 預測單號 / 臨時單號（從 /list 結果帶入）
       │
       ├─ 兩單號皆空 → 回 []
       ├─ demandRelationDoc 非空：
       │    ├─ 撈食材清單
       │    ├─ 平日 → demandAmount = weekDaySum
       │    └─ 假日 → demandAmount = holidaySum
       │    └─ expectDeliveryDate = demandDate（直接覆寫）
       └─ 只有 tempRelationDoc → 回 [] ⚠️ 未實作
```

---

## 6. 欄位規格

### 6.1 輸入（`RawMaterialDemandTitleVO`）

| 欄位 | 中文業務語 | 必填 |
|---|---|---|
| regionId | 區域 ID | ✅ |
| storeId | 門店 ID | 建議（區域模式未實作） |
| startDate / endDate | 日期區間 | ✅ |
| category / subcategory | 食材中類 / 小類 | 可選（過濾） |

### 6.2 列表回傳（`RawMaterialDemandDateListVO`）

| 欄位 | 中文業務語 |
|---|---|
| regionId / demandStore / storeId | 區域與門店 |
| demandDate | 需求日 |
| demandRelationDoc | 預測單號 |
| tempRelationDoc | 臨時需求單號 |
| expectAmount | 預估銷售量（萬元） |
| expectDeliveryDate | 預計配送日 |

### 6.3 明細回傳（`RawMaterialDemandIngredientDetailVO`）

| 欄位 | 中文業務語 |
|---|---|
| prodCode / ingredientName | 品號 / 食材名稱 |
| demandAmount | 需求數量（依平日 / 假日套對應 sum） |
| mfrId / mfrName | 廠商代號 / 全名 |
| expectDeliveryDate | 預計配送日（覆寫為 demandDate） |
| deliveryMode | 模式（直送 / 配送） |
| actualArrivalDate / actualArrivalAmount | 實際到店日 / 數量（後續入庫回填） |
| weekDaySum / holidaySum | 平日 / 假日每日萬元加權需求量 |
| cycleType / logisticsCycle | 物流週期類型與週期 |
| stockSignCode | 入庫單號 |
| 其他關聯欄位 | headId、demandDateId、demandRelationDoc、tempRelationDoc、regionId、storeId、appliTempNum、standardAmount、storeCode、materialProductId |

---

## 7. 商業邏輯

### 7.1 列表查詢

略，見 §3.2。

### 7.2 明細查詢

略，見 §3.3。

### 7.3 平日 / 假日分流

```java
if (isFridaySaturdayOrSunday(date)) {
    setDemandAmount(holidaySum);
} else {
    setDemandAmount(weekDaySum);
}
```

### 7.4 預計配送日

**直接設為 demandDate**（即需求日本身），未反推實際配送日。

---

## 8. 使用角色與權限

| 角色 | 可操作 | 對應權限字串 |
|---|---|---|
| 採購規劃 / 物流規劃 / 區經理 / 店長 | 查詢 | `pdm:raw-material:query` |

> 注意：權限統一使用 `pdm:raw-material:query`，**未做使用者區域 / 門店過濾** — 店長可查別店資料。

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節。建議：

### 9.1 行事曆主視圖

- 條件：區域下拉（必）、門店下拉（必，因區域模式未實作）、日期區間（必）、食材中類 / 小類過濾（可選）
- 行事曆視覺：以週為單位顯示，每格顯示該店該天的「需求單號」「預估銷售量」
- 點某格 → drill-down 進食材明細

### 9.2 食材明細頁

- 條件：（已從上一頁帶入）
- 表格：品號、食材名稱、需求量、廠商、預計配送日、模式、平日 sum / 假日 sum
- 操作：（無，唯讀）

---

## 10. 功能範圍

### 10.1 包含的功能

- 行事曆視角的單店逐日需求列表
- 食材明細查詢（僅預測單路徑）
- 平日 / 假日自動套對應 sum
- 必填驗證（regionId、日期區間）

### 10.2 預留但尚未實作

- **區域模式**（storeId 為空時逐店跑）— 程式 `return List.of()`
- **臨時需求路徑的食材展開** — `tempRelationDoc != null` 分支被註解
- **兩源合併**（同時有 demand + temp 時的食材合計）— 只看 demand
- **預計配送日的反推** — 直接 = demandDate
- **使用者區域 / 門店自動過濾** — 未套用 SecurityFrameworkUtils
- **匯出 Excel** — 雖然 VO 上有 `@ExcelProperty` 但無對應端點

### 10.3 不包含

- 需求預測試算（屬於 #24）
- 物料需求預測建立（屬於 #25）
- 臨時需求審核（屬於 #26）
- 物流配送排程 / 物流行事曆（屬於 #48–52，與 `rawmaterial1` 的物流端點重疊）
- 請購單建立（屬於 #31）
- 採購單建立（屬於 #33）
- 入庫回填（屬於 #40）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| 區域模式（storeId=null）未實作，是否該補上？ | 採購規劃想看整區，目前回空清單沒提示 | `RawMaterialDemandServiceImpl.java:75-78` |
| 臨時需求路徑的食材展開未實作 | 即使該日有臨時加單，明細也看不到 | 同檔 line 99-102（註解掉） |
| 兩源都存在時的合併規則 | 目前只看 demand，與 #25 的合併規則不一致 | `getRawMaterialIngredientDetailList` |
| 預計配送日直接設為 demandDate | 對物流規劃無意義，應依物流週期反推（如 #25 做的） | line 92-95 |
| 與 #25 並存兩個 Controller，何者現役？ | `rawmaterial` 看起來像舊版 / 未完成；前端應該用哪個？ | 兩個 controller 並存 |
| 沒有套用使用者區域 / 門店自動過濾 | 店長可查別店資料，違反資料權限 | service 無 `SecurityFrameworkUtils` |
| `expectAmount` 預估銷售量（萬元）的計算來源？ | 來自 #24 的單頭，但其精度與更新時機未文件化 | `selectRawMaterialDemandOneStore` SQL |
| 「需求量」（demandAmount）的單位為何？ | 食材的計量單位（公斤 / 包 / 個），但 VO 沒有單位欄位 | VO 缺單位 |
| 列表查詢沒有食材中類 / 小類過濾 — VO 上有但 Service 沒用 | 篩選功能缺失 | service 未讀 category |
| 是否該支援匯出 Excel？ | VO 上有 @ExcelProperty | 無 export 端點 |
| 沒有分頁 — 大區域大日期區間會回大量資料 | 效能風險 | 程式無分頁 |
| 模組歸屬：Excel 列「採購管理」但實作在 PDM | 應該重新討論模組界線 | 跨模組設計 |
| 與 `rawmaterial1` 中物流相關的端點（#48–52）功能重疊 | 是否要整併到本功能？ | `RawMaterialDemandHeadController` 內物流端點 |
| 「請購計劃」與「需求行事曆」的關係 | 兩者的業務分工不明：行事曆是查詢、計劃是排程，但中間缺「自動建請購單」 | 跨 #29、#30、#31 設計 |
| 廠商在明細中已綁定 — 但「該天某品號的多家廠商」如何選擇？ | 程式邏輯未列出，可能取第一筆 | `selectDemandIngredientDetailList` SQL |
| 「實際到店日 / 數量 / 入庫單號」何時回填？ | VO 預留但回填邏輯不在本功能 | DO 欄位 |
| 「物流週期類型」cycleType 為何在明細上而非單頭上 | 不同食材可能來自不同物流類型，但目前每筆都重複帶 | VO 結構 |
