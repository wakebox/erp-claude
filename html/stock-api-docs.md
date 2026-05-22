# 📦 Stock 模組 API 文件

> 基於前端 `/stock/` 目錄分析，整理所有 WHS (Warehouse) 相關 API 端點  
> **OA實作說明**：在 `OA實作` 欄標記 `[x]` 表示已實作，`[ ]` 表示未實作  
> 執行 `python3 gen-stock-docs.py` 可依此 Markdown 重新生成 HTML

---

## 一、🛡️ 安全存量設定 (Safety Stock)

**路由**: `/stock/safetyStock` | **檔案**: `src/api/stock/safetyStock/index.ts` | **優先級**: `P2 高`

| 方法 | 端點 | 功能 | 說明 | OA實作 |
|:----:|------|------|------|:------:|
| GET | `/whs/stock-safe/page` | 查詢安全存量列表（分頁） | 支援 signCode、applyDept、processStatus 等篩選；createTime 為 LocalDateTime 陣列 | [ ] |
| GET | `/whs/stock-safe/getAllProductDaySales` | 取得所有產品每日銷售量 | 必填 weightDay（加權日數），回傳食材計算結果 | [ ] |
| GET | `/whs/stock-safe/get` | 取得安全存量設定詳情 | 必填 id | [ ] |
| POST | `/whs/stock-safe/create` | 建立安全存量設定 | 含表頭與明細列表 | [ ] |
| PUT | `/whs/stock-safe/update` | 更新安全存量設定 | 含表頭與明細列表 | [ ] |
| DELETE | `/whs/stock-safe/delete` | 刪除安全存量設定 | 必填 id | [ ] |

---

## 二、🏭 倉庫基本設定 (Warehouse)

**路由**: `/stock/stockBasic` | **檔案**: `src/api/stock/stockBasic/index.ts` | **優先級**: `P1 最高`

| 方法 | 端點 | 功能 | 說明 | OA實作 |
|:----:|------|------|------|:------:|
| GET | `/whs/warehouse/page` | 倉庫列表（分頁） | 支援 category、warehouseType、warehouse、zone、area 篩選 | [ ] |
| POST | `/whs/warehouse/create` | 新增倉庫 | 建立一筆倉庫記錄 | [ ] |
| PUT | `/whs/warehouse/update` | 修改倉庫 | 更新倉庫資料 | [ ] |
| DELETE | `/whs/warehouse/delete` | 刪除倉庫 | 必填 id | [ ] |
| POST | `/whs/warehouse/deleteList` | 批量刪除倉庫 | ids 以逗號分隔 | [ ] |
| GET | `/whs/warehouse/hierarchy` | 層級查詢倉庫 | 返回樹狀結構，支援 area/warehouseType/warehouse/zone/binCode 篩選 | [ ] |
| GET | `/whs/warehouse/distinct-areas` | 取得區域列表 | 回傳 {area, areaName}[] | [ ] |
| GET | `/whs/warehouse/distinct-warehouse-types` | 取得倉別列表 | 可依 area 篩選，回傳 {warehouseType, warehouseTypeName}[] | [ ] |
| GET | `/whs/warehouse/distinct-warehouses` | 取得倉名列表 | 可依 area/warehouseType 篩選 | [ ] |
| GET | `/whs/warehouse/distinct-zones` | 取得儲區列表 | 可依 area/warehouseType/warehouse 篩選 | [ ] |
| GET | `/whs/warehouse/distinct-area-warehouses` | 取得區域倉庫（調撥用） | 用於調撥單出/入庫倉選擇 | [ ] |

---

## 三、🔍 倉儲查詢作業 (Storage Query)

**路由**: `/stock/storageQuery` | **檔案**: `src/api/stock/stockQuery/index.ts` | **優先級**: `P1 最高`

| 方法 | 端點 | 功能 | 說明 | OA實作 |
|:----:|------|------|------|:------:|
| GET | `/whs/stock/currentPage` | 查詢當前庫存（分頁） | 支援品號、倉庫、區域、物料大類/中類、安全存量等篩選 | [ ] |
| GET | `/whs/stock-record/pageHis` | 查詢出入庫明細（分頁） | 必填 prodCode 和 warehouseId | [ ] |

---

## 四、📥 入庫作業管理 (Stock In)

**路由**: `/stock/in` | **檔案**: `src/api/stock/in/index.ts` | **優先級**: `P1 最高`

| 方法 | 端點 | 功能 | 說明 | OA實作 |
|:----:|------|------|------|:------:|
| GET | `/whs/stock-record-head/page` | 入庫列表（分頁） | 需帶 stockType=1 篩選入庫 | [ ] |
| GET | `/whs/stock-record-head/todo-page` | 待辦入庫列表 | 簽核模式下使用，顯示待審核單據 | [ ] |
| GET | `/whs/stock-record/get-with-details` | 取得入庫單詳情（含明細） | 必填 recordId，回傳表頭+stockRecordList | [ ] |
| POST | `/whs/stock-record/batch-process` | 批量處理（暫存/提交） | 建立表頭+明細，stockType=1，回傳 id | [ ] |
| PUT | `/whs/stock-record/edit-with-head` | 編輯入庫單（含明細） | 更新表頭與明細列表 | [ ] |
| PUT | `/whs/stock-in/update-process-status` | 更新入庫流程狀態 | 審核用，含 approvalComments | [ ] |
| DELETE | `/whs/stock-record-head/delete` | 批量刪除表頭 | params ids 陣列 | [ ] |

---

## 五、📤 出庫作業管理 (Stock Out)

**路由**: `/stock/out` | **檔案**: `src/api/stock/out/index.ts` | **優先級**: `P2 高`

> 與入庫共用底層端點，以 stockType=0 區分

| 方法 | 端點 | 功能 | 說明 | OA實作 |
|:----:|------|------|------|:------:|
| GET | `/whs/stock-record-head/page` | 出庫列表（分頁） | 需帶 stockType=0 | [ ] |
| GET | `/whs/stock-record-head/todo-page` | 待辦出庫列表 | 簽核模式，stockType=0 | [ ] |
| GET | `/whs/stock-record/get-with-details` | 取得出庫單詳情 | 必填 recordId | [ ] |
| POST | `/whs/stock-record/batch-process` | 批量處理出庫 | stockType=0 | [ ] |
| PUT | `/whs/stock-record/edit-with-head` | 編輯出庫單 | | [ ] |
| PUT | `/whs/stock-in/update-process-status` | 更新出庫流程狀態 | 注意：出庫也沿用 stock-in 路徑 | [ ] |

---

## 六、🔄 門市調撥管理 (Stock Transfer)

**路由**: `/stock/transfer` | **檔案**: `src/api/stock/transfer/index.ts` | **優先級**: `P2 高`

| 方法 | 端點 | 功能 | 說明 | OA實作 |
|:----:|------|------|------|:------:|
| GET | `/whs/stock-transfer/page` | 調撥列表（分頁） | 支援 signCode、area、outWarehouse、inWarehouse 等篩選 | [ ] |
| GET | `/whs/stock-transfer/todo-page` | 待辦調撥列表 | 簽核模式 | [ ] |
| DELETE | `/whs/stock-transfer/delete` | 刪除調撥單 | 必填 id | [ ] |
| POST | `/whs/stock-transfer-detail/compute-area-inventory` | 計算區域庫存數量 | 必填 area、prodCode[]，可選 outWarehouse/inWarehouse | [ ] |
| POST | `/whs/stock-transfer-detail/batch-process` | 建立調撥批次（表頭+明細） | 含 stockTransferDetailList | [ ] |
| PUT | `/whs/stock-transfer-detail/edit-with-head` | 編輯調撥單（含明細） | | [ ] |
| GET | `/whs/stock-transfer-detail/get-with-details` | 取得調撥單詳情 | 必填 transferId | [ ] |
| POST | `/whs/stock-transfer-detail/get-by-opposite-stock-type` | 取得調撥來源單據 | 用於入/出庫單選擇來源，stockReason=SW02 | [ ] |
| GET | `/whs/stock-transfer-detail/record-batch-by-sign-code` | 依單號取得調撥記錄 | 用於入庫單填充明細 | [ ] |

---

## 七、🚫 不良品管理 (Bad Product)

**路由**: `/stock/badProduct` | **檔案**: `src/api/stock/badProduct/index.ts` | **優先級**: `P3 中`

| 方法 | 端點 | 功能 | 說明 | OA實作 |
|:----:|------|------|------|:------:|
| GET | `/whs/bad-product/page` | 不良品列表（分頁） | 支援 signCode、area、warehouse、returnDate、processStatus 篩選 | [ ] |
| GET | `/whs/bad-product/todo-page` | 待辦不良品列表 | 簽核模式 | [ ] |
| GET | `/whs/bad-product/get` | 不良品詳情 | 必填 id，回傳 BadProductAndDetailVO（主+子） | [ ] |
| POST | `/whs/bad-product/create` | 建立不良品單據 | 含 badProductDetails[]，支援 pictureUrl 圖片附件 | [ ] |
| PUT | `/whs/bad-product/update` | 更新不良品單據 | | [ ] |
| POST | `/whs/bad-product/get-outbound-source-list` | 取得出庫來源單據 | 必填 area/warehouse/stockReason | [ ] |
| POST | `/whs/bad-product/get-inbound-source-list` | 取得入庫來源單據 | | [ ] |
| GET | `/whs/bad-product/get-stock-record-batch-by-sign-code` | 依單號取得庫存記錄 | 必填 signCode，可選 stockType | [ ] |
| DELETE | `/whs/bad-product/delete` | 刪除不良品單據 | 必填 id | [ ] |

---

## 八、📋 每日盤點作業 (Daily Inventory)

**路由**: `/stock/dayCheck` | **檔案**: `src/api/stock/dayCheck/index.ts` | **優先級**: `P3 中`

| 方法 | 端點 | 功能 | 說明 | OA實作 |
|:----:|------|------|------|:------:|
| GET | `/whs/daily-inventory/page` | 每日盤點列表（分頁） | 支援 signCode、area、warehouse、processStatus、日期範圍篩選 | [ ] |
| GET | `/whs/daily-inventory/todo-page` | 待辦每日盤點列表 | 簽核模式 | [ ] |
| GET | `/whs/daily-inventory/get` | 每日盤點詳情 | 必填 id | [ ] |
| GET | `/whs/daily-inventory/daily-product-sales` | 取得每日產品銷量 | 必填 groupAreaId、date，可選 storeId | [ ] |
| GET | `/whs/daily-inventory/ingredient-options` | 取得盤點食材選項 | 依 area/warehouse 篩選 | [ ] |
| POST | `/whs/daily-inventory/create` | 建立每日盤點單 | 含 dailyInventoryDetails[] | [ ] |
| PUT | `/whs/daily-inventory/update` | 更新每日盤點單 | | [ ] |
| DELETE | `/whs/daily-inventory/delete` | 刪除每日盤點單 | 必填 id | [ ] |

---

## 九、📅 盤點計劃製定 (Check Plan)

**路由**: `/stock/checkPlan` | **檔案**: `src/api/stock/check/plan/index.ts` | **優先級**: `P3 中`

| 方法 | 端點 | 功能 | 說明 | OA實作 |
|:----:|------|------|------|:------:|
| GET | `/whs/check-plan/page` | 盤點計劃列表（分頁） | 支援 area、warehouse、periodicity、processStatus 篩選 | [ ] |
| GET | `/whs/check-plan/todo-page` | 待辦盤點計劃列表 | 簽核模式 | [ ] |
| GET | `/whs/check-plan/get` | 盤點計劃詳情 | 必填 id，含 checkPlanItems[] | [ ] |
| POST | `/whs/check-plan/create` | 建立盤點計劃 | periodicity: 每月/每季/每年 | [ ] |
| PUT | `/whs/check-plan/update` | 修改盤點計劃 | | [ ] |
| DELETE | `/whs/check-plan/delete` | 刪除盤點計劃 | 必填 id | [ ] |
| DELETE | `/whs/check-plan/deleteBatch` | 批量刪除盤點計劃 | body: {ids: number[]} | [ ] |

---

## 十、✅ 盤點計劃執行 (Check Execution)

**路由**: `/stock/checkExecution` | **檔案**: `src/api/stock/check/execution/index.ts` | **優先級**: `P3 中`

| 方法 | 端點 | 功能 | 說明 | OA實作 |
|:----:|------|------|------|:------:|
| GET | `/whs/check-plan-detail/page` | 盤點執行列表（分頁） | | [ ] |
| GET | `/whs/check-plan-detail/todo-page` | 待辦盤點執行列表 | 簽核模式 | [ ] |
| GET | `/whs/check-plan-detail/get` | 盤點執行詳情 | 必填 id，含 checkTaskDetailList[] | [ ] |
| PUT | `/whs/check-plan-detail/update` | 更新盤點執行 | 記錄實際盤點數量 | [ ] |
| GET | `/whs/check-plan-detail/check-plan-item/list-by-plan-detail-id` | 取得盤點品項列表 | 必填 planId | [ ] |
| POST | `/whs/check-plan-detail/get-by-opposite-stock-type` | 取得盤點來源單據 | stockReason=SW03 | [ ] |
| GET | `/whs/check-plan-detail/get-stock-record-batch-by-sign-code` | 依單號取得盤點記錄 | 用於入庫填充，含 accountQuantity/checkQuantity | [ ] |

---

## 十一、🔗 PDM 相關 API（相依模組）

**說明**: Stock 模組依賴以下 PDM 端點提供食材、食譜等基礎資料

| 方法 | 端點 | 功能 | 說明 | OA實作 |
|:----:|------|------|------|:------:|
| GET | `/pdm/ingredient-specs/getAllIngredientPage` | 取得全部食材規格（分頁） | | [x] |
| GET | `/pdm/recipe/allRecipe` | 取得全部食譜列表 | | [x] |
| POST | `/whs/stock-record-head/create-stock-in-from-demand-details` | 從需求明細建立入庫單 | | [ ] |
