# PRD｜庫存管理 — 安全存量設定

> 來源：逆向自 `kingmaker-module-whs` 後端程式碼（`controller/admin/stocksafe/StockSafeController.java`、`service/stocksafe/StockSafeServiceImpl.java`、`dal/dataobject/stocksafe/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。
>
> ⚠️ Excel 中 **#36 與 #37 同名「安全存量設定」**，疑似重複登記。後端僅有一套 `whs_stock_safe` 實作 — 本 PRD 同時涵蓋兩個序號。詳見 §11。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **總部採購規劃 / 區經理 / 倉儲管理員**。每樣食材在每個倉庫都需要設定「安全存量」 — 當實際庫存低於此水位，需求預測（#24）會自動將其納入補貨建議；採購單（#33 / 報價 #32）會以此為輔助標準。

> 「總部冷凍倉的牛肉餅 LB-04 安全存量設為 50 公斤，當庫存低於 50 公斤時系統要顯示警示／納入需求預測」

### 1.2 我要做什麼

- 建立 / 編輯安全存量設定單（單頭：倉庫、加權日數、申請單位、主旨；明細：產品 → 食材 → 每日銷量 + 安全存量）
- **從漢堡王中繼自動拉「近 12 個月每產品平均銷量」**，依「標準用量 × 每日銷量」自動算每個食材的建議安全存量
- 人工調整建議值
- 走簽核（**程式碼預留 `processStatus` 但無 BPM 流程整合**）
- 分頁查詢、Excel 匯出
- 取單筆（含明細）

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 系統自動算安全存量 | 上百樣食材每樣手動算太花時間 |
| 用「每日銷量 × 標準用量」當基準 | 銷售歷史已知，BOM 也已知，可機械式推算 |
| 加權日數設定 | 「3 天份」「7 天份」不同情境 |
| 一張單可涵蓋多倉 / 多產品 | 倉儲規劃集中管理 |
| 走簽核 | 庫存政策需審核 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 試算 API `/getAllProductDaySales` | 從中繼拉銷量 → 對應食材 → 算安全存量建議 |
| 安全存量單 CRUD | 維護 |
| 給下游使用的查詢方法（透過 mapper） | #24 / #31 取安全存量做試算 |
| 簽核流程整合（待實作） | 預留 |
| Excel 匯出 | 對照、稽核 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 安全存量設定 |
| 所屬模組 | WHS（庫存管理） |
| 兄弟功能 | 倉儲查詢 (#38)、庫存基本設定 (#39)、入庫管理 (#40)、出庫管理 (#41)、調撥 (#42) 等 |
| 主要頁面 | 安全存量編輯頁（含試算）、分頁、Excel 匯出 |
| 簽核流程 | **無**（DO 有 processStatus 欄位但程式無 BPM 整合）— 預留 |

---

## 2. 功能目的

安全存量設定是「**WHS 模組的核心輸入主檔**」：

1. **觸發補貨判斷** — 庫存低於安全存量時，需求預測（#24）對 LONG 食材會納入計算，請購單（#31）的庫存試算公式也依此運作
2. **半自動試算** — 從中繼拉銷量 + BOM 展開 + 加權日數 → 算建議值，再由人工調整
3. **多倉多產品** — 一張單可批次設定

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `whs_stock_safe`（單頭 / `StockSafeDO`） | 單據編號、申請單位、主旨、加權日數、倉名代碼、流程狀態 |
| `whs_stock_safe_detail`（明細 / `StockSafeDetailDO`） | stockSafeId、recipeId（產品 ID）、ingredientId（食材 ID）、dailySaleNum（每日預計銷量）、safeStock（安全存量） |

### 3.2 試算公式

`getAllProductDaySales`：

```
1. 從中繼 burgerKingStoreClient.getNearTwelveMonths() 取近 12 個月每產品銷售統計
2. 對每產品：撈該產品的所有食材（透過 searchAllIngredient(productIdList)）
3. 對每食材：
   - dailySaleNum = totalSalesCount（⚠️ 註解寫應該是 dayAverageSales 但實際取 totalSalesCount）
   - safeQuantity = standardAmount × daySalesCount（HALF_UP scale=2）
   - safeStock = safeQuantity
```

來源：`StockSafeServiceImpl.java:47-97`。

⚠️ **明顯 bug**：

- TODO 註解寫「正常應該是平均每天的銷量 dayAverageSales」但實際取 `totalSalesCount`（12 個月總銷量）
- 結果：safeStock 比正確值大 365 倍
- line 66-67

### 3.3 加權日數 weightDay

DO 上有 `weightDay` 欄位（單頭層級），但 `getAllProductDaySales` **沒用到**它。意味試算未套用「N 天份」的加權。詳見 §11。

### 3.4 流程狀態未整合 BPM

- DO 有 `processStatus` 欄位
- Service 完全無 BPM 呼叫（與 PMM 模組功能對比）
- 表單路徑也沒有對應的 `FormPathUniqueEnum`

結論：本功能**設計時預留簽核**，但**尚未實作**。

### 3.5 跨模組依賴

- 中繼 API：取近 12 個月銷量
- PDM 食譜：透過 `searchAllIngredient` 取產品 → 食材關係（join `pdm_recipe` + `pdm_ingredient_specs`）

### 3.6 編輯子表的策略

刪舊插新（同前述功能）。

### 3.7 給下游使用的查詢方法

`pdmProductRecipeRelMapper.selectFirstSafetyStockByIngredientIds` 用來給 #24 食材需求預測查 LONG 食材的安全存量，撈的就是 `whs_stock_safe_detail` 的 `safeStock` 欄位（first by ingredientId）。

---

## 4. 情境說明

### 4.1 正常流程 — 為總部冷凍倉建立安全存量

倉儲主管小李為總部冷凍倉設定安全存量：

1. 進入安全存量編輯頁
2. 主表：倉名「總部冷凍倉」、申請單位「倉儲部」、加權日數「3」、主旨「2026 Q3 安全存量更新」
3. 點「試算」按鈕 → GET /getAllProductDaySales
4. 系統：
   - 從中繼拉近 12 個月每產品銷量
   - 對每產品撈所有食材
   - 對每食材算 safeStock = standardAmount × totalSalesCount
5. 前端顯示：牛肉餅 dailySaleNum=18000、safeStock=18000 ⚠️（公斤數異常大）
6. 小李手動調整：牛肉餅 safeStock=50 公斤
7. POST /create 儲存

### 4.2 異常情境 — 中繼 API 不可用

`getNearTwelveMonths` 失敗 → 回空清單，前端拿不到任何試算建議。

### 4.3 規則分流 — 多產品共用食材

「華堡」「雙層華堡」都用牛肉餅。試算時兩個產品各自展開明細，會出現**牛肉餅明細 2 筆**（一張單有兩筆同 ingredientId）。儲存時兩筆都會寫入 `whs_stock_safe_detail`。

下游 #24 查 `selectFirstSafetyStockByIngredientIds` 取 first by ingredientId → 撈到其中一筆（順序未保證）。

⚠️ 同 ingredientId 多筆設定的 fallback 規則不明（見 §11）。

### 4.4 異常情境 — 編輯後試算建議與舊值差異

小李重新試算後，建議值與舊值差異大（可能因為中繼資料更新）。系統沒有 diff 比較功能，得人工核對。

---

## 5. 操作流程

```
[使用者進入「安全存量設定」]
  │
  ├─ 1. 試算 GET /whs/stock-safe/getAllProductDaySales
  │    ├─ 從中繼拉近 12 個月銷量
  │    ├─ 對每產品撈食材
  │    └─ 算 safeStock = standardAmount × salesCount  ⚠️ bug: 用 totalSalesCount 而非 dayAverageSales
  │
  ├─ 2. 建立 POST /whs/stock-safe/create
  │    ├─ insert 單頭
  │    └─ batch insert 明細
  │
  ├─ 3. 更新 PUT /whs/stock-safe/update
  │    ├─ 檢查存在
  │    ├─ updateById 單頭
  │    └─ 更新明細（刪舊插新）
  │
  ├─ 4. 刪除 DELETE /delete?id=
  │
  ├─ 5. 取單筆 GET /get?id=
  │    └─ 單頭 + 明細（join 食譜 + 食材取名稱）
  │
  ├─ 6. 分頁 GET /page
  │
  └─ 7. 匯出 Excel GET /export-excel
```

---

## 6. 欄位規格

### 6.1 單頭（`whs_stock_safe`）

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| signCode | 單據編號 |
| applyDept | 申請單位 |
| subject | 主旨 |
| weightDay | 加權日數 |
| warehouse | 倉名代碼 |
| processStatus | 流程狀態（**未使用**） |

### 6.2 明細（`whs_stock_safe_detail`）

| 欄位 | 中文業務語 |
|---|---|
| stockSafeId | 主表 ID |
| recipeId | 食譜 / 產品 ID |
| ingredientId | 食材 ID |
| dailySaleNum | 每日預計銷量 |
| safeStock | 安全存量 |

---

## 7. 商業邏輯

### 7.1 試算公式（含 bug）

```
dailySaleNum = totalSalesCount（⚠️ 應為 dayAverageSales）
safeQuantity = standardAmount × daySalesCount   scale=2 HALF_UP
safeStock = safeQuantity
```

### 7.2 編輯刪舊插新

同前述功能。

### 7.3 無 BPM 流程

`processStatus` 欄位存在但無流程節點驅動。

---

## 8. 使用角色與權限

| 角色 | 可操作 | 對應權限字串 |
|---|---|---|
| 倉儲主管 / 總部規劃 | CRUD / 試算 / 查詢 / 匯出 | `whs:stock-safe:create`、`update`、`delete`、`query`、`export` |
| 下游模組（#24/#31）讀取 | 透過 Mapper | — |

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節。建議：

### 9.1 編輯頁

- 主表：申請單位、主旨、加權日數、倉名（下拉）
- 「試算」按鈕：呼叫 /getAllProductDaySales
- 明細表格：產品名、食材名、每日銷量（input）、建議安全存量、實際安全存量（input，人工調整）

### 9.2 分頁

- 條件：流程狀態、倉名、建立時間
- 表格：單據編號、倉名、申請單位、加權日數、建立時間

---

## 10. 功能範圍

### 10.1 包含的功能

- 安全存量單 CRUD
- 從中繼自動試算（含 bug）
- Excel 匯出
- 給下游使用的查詢

### 10.2 預留但尚未實作 / 缺陷

- **`totalSalesCount` 應為 `dayAverageSales`**（明確 bug）
- **`weightDay` 未在試算中使用**
- **`processStatus` 與 BPM 流程未整合**
- **同 ingredientId 多筆設定的 fallback 規則不明**
- **`getStockSafeDetailListByStockSafeId` 端點 `@PreAuthorize` 被註解**（line 113-115）

### 10.3 不包含

- 倉儲查詢（#38）
- 庫存基本設定（#39，可能是門市倉、區域倉的設定）
- 入出庫管理（#40、#41）
- 食譜 / 食材主檔（PDM）
- 銷量資料（中繼系統）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| Excel #36 與 #37 同名「安全存量設定」是登記錯誤還是兩個不同功能？ | Excel 重複登記 | excel.md line 38-39 |
| `dailySaleNum = totalSalesCount` 明顯錯誤 | 應為 dayAverageSales，目前數值偏大 365 倍 | line 66-67 + TODO 註解 |
| `weightDay` 加權日數在試算中未使用 | DO 有此欄位但邏輯不參考 | DO `weightDay` |
| `processStatus` 與 BPM 流程未實作 | 無 FormPathUniqueEnum 對應 | DO 有但 service 無使用 |
| 同 ingredientId 多筆設定（多產品共用食材）的 fallback 規則 | 下游 #24 取 first by ingredientId 順序未保證 | #24 `selectFirstSafetyStockByIngredientIds` |
| `getStockSafeDetailListByStockSafeId` 端點權限被註解 | line 113-115 |
| 試算撈中繼資料失敗時靜默回空 | 沒有使用者提示 | line 50-52 |
| 編輯刪舊插新導致明細 id 變動 | line 176-181 |
| 試算沒有「重新試算」與「保留人工調整」的合併機制 | 每次試算覆寫前一版本 | line 47-97 |
| 是否該支援多倉同產品不同安全存量？ | 目前單頭一個 warehouse，多倉需要建多張單 | DO 設計 |
| 「申請單位」字串欄位，無字典化 | 同 #26 / #28 等問題 | DO `applyDept` |
| `recipeId` 在註解寫「食譜表id」但業務上是「產品 ID」？ | 對應 `pdm_recipe` 還是 `pdm_recipe_product`？需確認 | DO `recipeId` |
| 沒有「批次匯入」端點 | 上百樣食材設定靠手動 | Controller |
| Controller 與 Excel 命名差：Excel「安全存量設定」、後端「庫存安全存量設定」 | 命名不一致 | Controller Tag |
