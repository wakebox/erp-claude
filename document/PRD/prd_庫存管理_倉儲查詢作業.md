# PRD｜庫存管理 — 倉儲查詢作業

> 來源：逆向自 `kingmaker-module-whs` 後端程式碼（`controller/admin/stock/StockController.java`、`service/stock/StockServiceImpl.java`、`dal/dataobject/stock/StockDO.java`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **倉儲人員 / 採購助理 / 區經理 / 店長**。每天工作的第一件事就是：

> 「今天信義店冷藏倉的牛肉餅還剩幾公斤？北一倉的麵包庫存夠下週用嗎？哪些食材已經低於安全存量了？」

「倉儲查詢作業」就是這份「**當前庫存量**」的查詢視窗。

### 1.2 我要做什麼

- 分頁查詢「當前庫存量」 — `/currentPage`（主要使用）
- 系統依登入者的「區域」「倉庫」自動過濾可見資料
- 一般 CRUD（建立 / 更新 / 刪除 / 取單筆）— 雖然存在，但**實務上 stock 由其他模組維護**（#40 入庫、#41 出庫、#42 調撥）
- 一般分頁 `/page`
- Excel 匯出

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 看當前庫存量 | 補貨決策的基礎 |
| 依登入者自動過濾 | 店長只看自己門店、區經理只看自己區 |
| 與安全存量對照 | 知道哪些低於安全水位 |
| 多倉庫多品號 | 整體掌握庫存分佈 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 當前庫存量分頁（含使用者權限過濾） | 主查詢視圖 |
| Excel 匯出 | 對照、稽核 |
| 一般 CRUD | 後門 / 修補用（業務上應由 #40/#41/#42 維護） |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 倉儲查詢作業 |
| 所屬模組 | WHS（庫存管理） |
| 兄弟功能 | 安全存量設定 (#36/37)、庫存基本設定 (#39)、入庫 (#40)、出庫 (#41)、調撥 (#42)、盤點 (#43–46)、不良品 (#47) |
| 主要頁面 | 當前庫存量分頁、Excel 匯出 |
| 簽核流程 | 無（純查詢） |
| 寫入流程 | 由其他模組維護（驗收 #35、入庫 #40、出庫 #41、調撥 #42、盤點 #43+） |

---

## 2. 功能目的

倉儲查詢是「**庫存即時視圖**」：

1. **核心查詢視窗** — 採購、店長、倉儲日常使用
2. **資料權限自動過濾** — 依登入者區域 / 倉庫
3. **`whs_stock` 是庫存表** — 各業務模組對庫存的寫入最終落在這張表上

---

## 3. 業務邏輯背景

### 3.1 一張表

`whs_stock`（`StockDO`）

| 欄位 | 含義 |
|---|---|
| id | 主鍵 |
| ingredientId | 食材 ID |
| warehouseId | 倉庫表 ID |
| invNum | 庫存數量 |
| standardQuantity | 庫存計數 |
| unit | 數量單位 ID |
| prodCode | 品號 |
| singleSpec / singleSpecUnit | 單一規格 / 單位 |

### 3.2 兩個分頁端點的差異

| 端點 | 用途 | service 方法 |
|---|---|---|
| `/page` | 一般分頁，直接撈 `whs_stock` | `getStockPage` |
| `/currentPage` | 「當前庫存量」分頁，含使用者權限過濾、可能 join 其他表（如安全存量、倉庫名） | `getStockCurrentPage` |

業務上應使用 `/currentPage`，`/page` 是底層 CRUD。

### 3.3 使用者區域 / 倉庫自動過濾（僅 currentPage）

`getStockCurrentPage`：

- 登入者有 areaId → 強制 pageReqVO.area = loginAreaId
- 登入者有 storeId → 強制 pageReqVO.warehouseId = loginStoreId.longValue()

⚠️ **店長的 storeId 被當作 warehouseId 用** — 邏輯上「店」與「倉」概念混淆（見 §11）。

來源：`StockServiceImpl.java:90-103`。

### 3.4 中繼門市庫存的缺失

`getStockCurrentPage` 註解寫「中繼上缺少根據傳入的門市，計算門市的庫存量」 — 表示**理想設計**是從中繼計算門市庫存，但目前未實作（line 109）。

### 3.5 CRUD 端點與業務流程衝突

- `/create`、`/update`、`/delete`：可由 admin 操作
- 但庫存正確值應由 #35 驗收 / #40 入庫 / #41 出庫 / #42 調撥 / #43+ 盤點 自動維護
- 直接 CRUD 可能造成資料不一致

詳見 §11。

### 3.6 跨模組依賴

- `whs_stock` 被 #35、#40、#41、#42、#43+ 寫入
- 被 PMM #28、#31 讀取（庫存試算）
- 被 PDM #24 讀取（食材需求預測）

---

## 4. 情境說明

### 4.1 正常流程 — 店長看自己門店庫存

店長小王早上開系統，進入「倉儲查詢作業」：

1. GET /whs/stock/currentPage
2. 系統檢測 loginUserStoreId = 11（信義店）
3. 自動加 warehouseId=11 過濾
4. 回傳該店的所有食材庫存（含安全存量對照、單位等）

### 4.2 規則分流 — 總部採購看全公司

採購人員無 areaId / storeId 限制：

- 不加過濾
- 全公司庫存

### 4.3 異常情境 — 直接 CRUD 改庫存

某管理員透過 /update 直接改 invNum：

- 系統不擋（與業務流程衝突）
- 庫存與「入出庫流水」不一致，audit trail 壞掉

### 4.4 規則分流 — 區經理看整區

某使用者 areaId=3（北一區）但無 storeId：

- 自動加 area=3 過濾
- warehouseId 不限制
- 看北一區所有門店倉庫

---

## 5. 操作流程

```
[使用者進入「倉儲查詢作業」]
  │
  ├─ 1. 當前庫存量 GET /whs/stock/currentPage
  │    ├─ 權限：whs:stock:query
  │    ├─ 自動套區域 / 倉庫過濾
  │    └─ 回 StockVO 分頁（含關聯資訊）
  │
  ├─ 2. 一般分頁 GET /whs/stock/page
  │    └─ 直接撈 whs_stock（不套權限過濾）
  │
  ├─ 3. 匯出 GET /whs/stock/export-excel
  │
  └─ 4. CRUD（不建議業務使用）
       ├─ POST /create
       ├─ PUT /update
       ├─ DELETE /delete?id=
       └─ GET /get?id=
```

---

## 6. 欄位規格

### 6.1 庫存表（`whs_stock`）

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| ingredientId | 食材 ID |
| warehouseId | 倉庫表 ID |
| invNum | 庫存數量 |
| standardQuantity | 庫存計數 |
| unit | 數量單位 ID |
| prodCode | 品號 |
| singleSpec / singleSpecUnit | 單一規格 / 單位 |

### 6.2 查詢條件（`StockPageReqVO`）

主要：area、warehouseId、prodCode、ingredientId 等（未完整列）

---

## 7. 商業邏輯

### 7.1 使用者權限自動過濾（僅 currentPage）

- areaId / storeId 從登入者帶入

### 7.2 直接 CRUD

無業務檢查，純資料層操作

---

## 8. 使用角色與權限

| 角色 | 可看資料 | 可操作 | 對應權限字串 |
|---|---|---|---|
| 店長 | 限自己門店 | 查詢、匯出 | `whs:stock:query`、`export` |
| 區經理 | 限自己區域 | 同上 | 同上 |
| 總部採購 / 倉儲 | 全部 | 查詢、匯出 | 同上 |
| 系統管理員 | 全部 | CRUD（不建議業務使用） | `whs:stock:create`、`update`、`delete` |

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節。建議：

### 9.1 主查詢頁

- 條件：區域 / 倉庫（依權限自動帶）、品號、食材
- 表格：品號、食材名稱、倉庫、庫存數量、單位、安全存量（join）、低於安全存量警示
- 操作：匯出 Excel

---

## 10. 功能範圍

### 10.1 包含的功能

- 當前庫存量分頁（含使用者權限過濾）
- 一般分頁 / CRUD
- Excel 匯出

### 10.2 預留但尚未實作

- **中繼計算門店庫存**：line 109 TODO
- **CRUD 業務檢查**：應禁止人工改庫存
- **與安全存量對照**：未確認是否在 SQL join

### 10.3 不包含

- 入庫 (#40)、出庫 (#41)、調撥 (#42)、盤點 (#43+)、不良品 (#47)
- 食材主檔（PDM）
- 倉庫主檔（WHS warehouse 子模組）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| 店長的 storeId 被當作 warehouseId — 「店」與「倉」概念混淆 | 一店多倉的場景無法表達 | line 100-103 |
| 中繼計算門店庫存的 TODO 未實作 | line 109 |
| 直接 CRUD 端點可繞過業務流程改庫存 | 應移除或加業務限制 | Controller |
| `/page` 不套使用者權限過濾 | 與 `/currentPage` 不一致 | service line 73-76 vs line 89-111 |
| `getStockByIngredientAndWarehouse(prodCode, warehouseId)` — 參數名是 prodCode 但方法名是 ingredient | 命名不一致 | service line 79 |
| `whs_stock` 對「食材 + 倉庫」唯一性如何保證？ | 同食材同倉應只一筆，否則庫存重複 | DO 無唯一性 |
| 「庫存數量」`invNum` 與「庫存計數」`standardQuantity` 區別？ | DO 有兩個欄位語意需釐清 | DO `invNum` vs `standardQuantity` |
| 安全存量資訊是 currentPage 內 join 還是前端再查？ | xml 未讀 | service line 107 |
| `getStockCurrentPage` 不對 prodCode 過濾 — 業務上常見「查某品號」 | 視覺化是否要支援 |
| Excel 匯出不套使用者權限 | 同 page 一樣 | line 96-101 |
