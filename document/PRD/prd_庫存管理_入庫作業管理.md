# PRD｜庫存管理 — 入庫作業管理

> 來源：逆向自 `kingmaker-module-whs` 後端程式碼（`controller/admin/stockrecordhead/`、`controller/admin/stockrecord/`、`service/stockrecordhead/`、`service/stockrecord/StockRecordServiceImpl.java`、`dal/dataobject/stockrecord/`、`dal/dataobject/stockrecordhead/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。
>
> ⚠️ **資料表是「出入庫共用」**：`whs_stock_record_head` / `whs_stock_record` 以 `stockType`（0=出庫 / 1=入庫）區分。本 PRD 聚焦於入庫（stockType=1），但程式邏輯同時處理出庫。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **倉儲人員 / 採購助理**。當廠商實際到貨並通過 #35 驗收確認歸檔後，系統自動產生「入庫單」並將庫存加總到 `whs_stock`。某些情境下我也需要手動建入庫（如：盤盈、調整等）：

> 「驗收 PA-2026-001 歸檔 → 系統自動建入庫單 SI-2026-001 → 庫存表牛肉餅 LB-04 +2 公斤」

### 1.2 我要做什麼

- 檢視 / 查詢入庫單（單頭 + 明細）
- 透過 **物流管理行事曆生成入庫單** 端點（補檔用）
- 透過 **批次處理出入庫** 端點建立入庫（同時更新庫存表）
- 編輯既有單頭 + 明細
- 走簽核流程（雖然 `processStatus` 存在，但很多入庫由其他模組直接設為「已歸檔」跳過簽核）
- 待簽分頁、分頁查詢
- 跨單據來源：根據 sourceSignCode 前綴自動更新對應單據狀態（ST=調撥、CE=盤點、BP=不良品）

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 自動入庫 | 驗收確認後不要再手動 |
| 各種來源都能入庫 | 採購驗收 / 調撥 / 盤點調整 / 不良品退庫 |
| 入庫即更新庫存 | 庫存表要即時 |
| 來源單據狀態同步 | 調撥 / 盤點 / 不良品的 stockType 旗標要回寫 |
| 出入庫共用同表 | 透過 stockType 區分 |
| 編輯彈性 | 後續修正 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 單頭分頁 / 待簽分頁 | 主要查詢視圖 |
| 批次刪除 | 廢棄誤建單 |
| 物流行事曆生成入庫 | 配送到店時補單 |
| 批次處理入庫（含建單頭與庫存更新） | 提供給其他模組呼叫 |
| 跨來源更新狀態（ST/CE/BP） | 同步上游 |
| 編輯（含單頭單身一起） | 修正 |
| 庫存歷史分頁查詢 `/pageHis` | 倉儲查詢 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 入庫作業管理（業務名）／ 出入庫作業管理（程式碼語） |
| 所屬模組 | WHS（庫存管理） |
| 兄弟功能 | 倉儲查詢 (#38)、安全存量 (#36/37)、出庫 (#41)、調撥 (#42)、盤點 (#43+)、不良品 (#47) |
| 主要頁面 | 入庫單分頁、待簽分頁、入庫單編輯頁（含單頭單身）、歷史出入庫查詢 |
| 簽核流程 | 有：BPM `stock-record-head` 流程 |
| 自動觸發 | 驗收 #35 歸檔 → 自動建入庫 + 更新 `whs_stock`；庫存記錄寫入時同步更新來源單據（調撥 / 盤點 / 不良品）的 stockType |

---

## 2. 功能目的

入庫作業是「**WHS 模組的庫存增量入口**」：

1. **承接 #35 驗收確認** — 由驗收歸檔自動建立、processStatus 直接「已歸檔」
2. **`whs_stock_record_head` + `whs_stock_record`** 出入庫共用一套表，以 stockType 區分
3. **「批次處理」入口** — 給其他模組（#42 調撥 / #43+ 盤點 / #47 不良品）一律透過 batchProcessStockRecords 寫庫存
4. **更新 `whs_stock` 為唯一機制** — 不論來源，所有庫存增量都經過 processInboundStock 加總

---

## 3. 業務邏輯背景

### 3.1 兩張表（出入庫共用）

| 表 | 用途 |
|---|---|
| `whs_stock_record_head`（單頭 / `StockRecordHeadDO`） | 單據編號、processStatus、來源單據編號、區域 / 倉別 / 倉名 / warehouseId、stockType（0/1）、inboundTime、主旨、stockReason、processInstanceId |
| `whs_stock_record`（明細 / `StockRecordDO`） | recordId、ingredientId、warehouseId、stockReason、sourceSignCode、invNumChange、standardQuantity、stockType、prodCode |

### 3.2 庫存更新流程 `batchProcessStockRecords`

```
對每筆 StockRecordDO：
  1. 用 prodCode + warehouseId 查 whs_stock：
     - 有 → existingStock
     - 無 → new StockDO（prodCode, warehouseId）
  2. 依 stockType:
     - 1（入庫）→ processInboundStock：standardQuantity += stockRecordVO.standardQuantity
     - 0（出庫）→ processOutboundStock：standardQuantity -= ...（須先有庫存，否則拋 STOCK_NOT_EXISTS2）
  3. 若 existingStock.id == null → 新建 whs_stock；否則 update
  4. 累積 sourceSignCode 到 set（用於後續更新來源單據）

5. updateSourceDocumentStatus(set, stockType)：
   - signCode 前綴 ST → 調撥單 stockType 回寫
   - 前綴 CE → 盤點單 stockType 回寫
   - 前綴 BP → 不良品單 stockType 回寫
   - 其他 → 警告 log
```

來源：`StockRecordServiceImpl.java:122-180、189-280`。

關鍵：

- 各來源的 stockType 同步**只用前綴判斷** — ST / CE / BP
- 採購入庫（驗收歸檔）的 signCode 前綴推測為 SI / PA / 其他 → **不在三個分支內 → 只 log warn 不回寫**（其實採購入庫不需要回寫上游 stockType，因為 PMM #35 已歸檔）

### 3.3 入庫事由 `stockReason`

字典 enum `StockReasonEnum`，從 `getStockRecordByIngredientAndWarehouse` 看到用法：撈出後用 `StockReasonEnum.getReasonByCode(code)` 轉中文。

常見值（推測）：

- SW01–SW04（其他用途）
- SW05（採購入庫，#35 自動觸發時使用）

### 3.4 物流行事曆生成入庫 `/create-stock-in-from-demand-details`

接收 `List<RawMaterialDemandStockInReqVO>` — 由「物流行事曆」（#30 / 物流配送 #50）端傳入「明細 ID + 實際配送數量」。

意義：當門市實際收貨（非透過 PMM 採購流程，例如總部直接配送的場景），用此端點補單。

**Controller 上 `@PreAuthorize` 被註解掉**（line 69）— 無權限保護。詳見 §11。

### 3.5 批次處理含單頭 `/batch-process`

接收 `StockRecordBatchSaveVO`（含 head + details），呼叫 `batchProcessStockRecordsWithHead`：

```
1. 建單頭
2. 對每明細 setRecordId
3. 跑 batchProcessStockRecords（更新庫存 + 同步來源）
```

### 3.6 編輯含單頭單身 `/edit-with-head`

`editStockRecordsWithHead` — 一次性編輯單頭與明細（細節未讀，推測為刪舊插新模式）。

### 3.7 BPM 流程

- 待簽分頁：`getToDoStockRecordHeadPage` — 透過 BPM 取分派給我的 IDs
- 多數自動產生的入庫單直接 processStatus="已歸檔"（跳過簽核）

### 3.8 跨模組依賴

- `whs_stock`（被本功能寫入）
- `whs_stock_transfer`（#42 調撥）、`whs_check_plan_detail`（#43+ 盤點）、`whs_bad_product`（#47 不良品）— 都依 signCode 前綴回寫 stockType
- BPM 流程：`stock-record-head`

---

## 4. 情境說明

### 4.1 正常流程 — 驗收歸檔自動入庫

#35 PA-2026-001 歸檔：

1. PMM `processStockIn(reqVO)` 呼叫：
   - 建 StockRecordHeadDO（signCode="入庫單管理"、processStatus="已歸檔"、stockReason="SW05"、sourceSignCode=PA-2026-001、stockType=1、inboundTime=now）
   - 建 StockRecordDO 明細
   - `stockRecordService.batchProcessStockRecords(list)`
2. `batchProcessStockRecords`：
   - 對牛肉餅 LB-04 / warehouseId=北一倉 → 查 stock → 加 2 公斤
   - sourceSignCode=PA-... 前綴非 ST/CE/BP → log warn（合理：採購不需回寫上游）
3. WHS 庫存表更新完成

### 4.2 規則分流 — 調撥引發入出庫

#42 調撥單 ST-2026-001 執行：

- 出庫端：建 StockRecord stockType=0、sourceSignCode=ST-2026-001
- 入庫端：建 StockRecord stockType=1、sourceSignCode=ST-2026-001
- batchProcessStockRecords：
  - 入庫端加庫存
  - sourceSignCode 前綴 ST → updateStockTransferStatus(ST-2026-001, 1)
  - 調撥單 stockType 回寫

### 4.3 異常情境 — 出庫無庫存

出庫時對應 prodCode + warehouseId 在 `whs_stock` 沒記錄：

- 拋 `STOCK_NOT_EXISTS2`
- 整個 batch 不會被回滾（service 無 @Transactional 在 batchProcessStockRecords 上 — 詳見 §11）

### 4.4 異常情境 — 來源單號前綴未識別

某入庫 sourceSignCode 是 "ABC123"：

- 不是 ST/CE/BP → log warn "未知的单据编号前缀"
- 庫存仍會正常加，只是上游單據 stockType 不會回寫

### 4.5 規則分流 — 手動編輯入庫單

倉儲管理員透過 `/edit-with-head` 編輯既有入庫單：

- 刪舊插新模式
- ⚠️ **庫存如何處理？** 程式碼未明示是否會反推舊量再加新量 — 可能造成庫存值錯亂（見 §11）

---

## 5. 操作流程

```
[入庫來源]
  ├─ #35 PMM 驗收歸檔 → processStockIn → stockReason="SW05"
  ├─ #42 調撥 → batchProcessStockRecords (signCode 前綴 ST)
  ├─ #43+ 盤點 → batchProcessStockRecords (前綴 CE)
  ├─ #47 不良品 → batchProcessStockRecords (前綴 BP)
  ├─ 物流行事曆 → /create-stock-in-from-demand-details
  └─ 手動 → /batch-process

[batchProcessStockRecords 核心邏輯]
  │
  └─ 對每筆 StockRecordDO：
       ├─ 查 stock by (prodCode, warehouseId)
       ├─ stockType=1 → inbound：standardQuantity += 異動量
       ├─ stockType=0 → outbound：須先有庫存
       ├─ create/update whs_stock
       └─ 收集 sourceSignCode
     ↓
     updateSourceDocumentStatus：
       ├─ ST → 更新調撥單 stockType
       ├─ CE → 更新盤點單 stockType
       └─ BP → 更新不良品單 stockType

[查詢]
  ├─ GET /whs/stock-record-head/page
  ├─ GET /whs/stock-record-head/todo-page（待簽）
  ├─ GET /whs/stock-record/page
  ├─ GET /whs/stock-record/pageHis（含字典翻譯）
  └─ GET /whs/stock-record/get-with-details

[編輯 / 刪除]
  ├─ PUT /whs/stock-record/edit-with-head
  └─ DELETE /whs/stock-record-head/delete?ids=
```

---

## 6. 欄位規格

### 6.1 單頭（`whs_stock_record_head`）

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| signCode | 單據編號 |
| processStatus | 流程狀態 |
| remark | 備註 |
| stockReason | 入庫事由（字典） |
| sourceSignCode | 來源單據編號 |
| area / areaName | 區域 |
| warehouseType / warehouseTypeName | 倉別 |
| warehouse / warehouseName | 倉名 |
| warehouseId | 倉庫 ID |
| stockType | 0=出庫 / 1=入庫 |
| inboundTime | 入庫時間 |
| subject | 主旨 |
| processInstanceId | BPM 流程實例 |

### 6.2 明細（`whs_stock_record`）

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| ingredientId | 食材 ID |
| warehouseId | 倉庫 ID |
| stockReason | 入庫事由 |
| sourceSignCode | 來源單據編號 |
| invNumChange | 庫存異動數量 |
| standardQuantity | 入庫計數 |
| stockType | 0/1 |
| recordId | 單頭 ID |
| prodCode | 品號 |

---

## 7. 商業邏輯

### 7.1 入庫加法

```
existingStock.standardQuantity += stockRecord.standardQuantity
```

### 7.2 出庫減法

須先有庫存（否則拋例外）。

### 7.3 來源單據狀態同步

依 signCode 前綴分流（ST / CE / BP）。

### 7.4 stockReason 字典翻譯

`pageHis` 撈出後用 `StockReasonEnum.getReasonByCode` 轉中文。

---

## 8. 使用角色與權限

| 角色 | 可操作 | 對應權限字串 |
|---|---|---|
| 倉儲人員 | 查詢、編輯、刪除、批次處理 | `whs:stock-record:create`、`update`、`delete`、`query`、`whs:stock-record-head:query`、`delete` |
| 簽核主管 | 待簽分頁 | `query` + BPM |
| 上游模組（PMM #35、#42 / #43+ / #47） | 透過 service 內部呼叫 | — |

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節。建議：

### 9.1 入庫單分頁

- 條件：流程狀態、單據編號、來源單號、入庫時間、倉庫
- 表格：單據編號、來源單號、stockType（出 / 入）、stockReason（中文）、倉名、入庫時間、流程狀態

### 9.2 編輯頁

- 主表：單據編號、來源單號（連結到上游）、stockReason、倉位（cascade）、入庫時間、備註
- 明細：品號、食材名、數量、單位、儲位

### 9.3 待簽分頁

- 同分頁但限自己作為 assignee

---

## 10. 功能範圍

### 10.1 包含的功能

- 入庫單頭 / 明細的查詢、編輯、刪除
- 批次處理出入庫（更新庫存 + 同步上游）
- 物流行事曆生成入庫
- 待簽分頁
- 含字典翻譯的歷史分頁
- BPM 流程整合（部分）

### 10.2 預留但尚未實作 / 缺陷

- **編輯舊單頭時庫存如何回沖未明示**：可能造成庫存值錯亂
- **`/create-stock-in-from-demand-details` 權限被註解**：line 69
- **batchProcessStockRecords 無 @Transactional 在方法層**：批次中途失敗可能造成資料不一致
- **stockReason 是字串非 enum 欄位**：DO 上字串
- **未知 signCode 前綴只 log warn**：不通知使用者

### 10.3 不包含

- 出庫管理（#41，雖然技術上共用此模組）
- 庫存查詢（#38）
- 安全存量（#36/37）
- 各來源單據本身（#35、#42、#43+、#47）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| 編輯舊入庫單時，舊 standardQuantity 是否會從 stock 回沖再加新值？ | 程式邏輯未明示 | `editStockRecordsWithHead` 未完整讀 |
| `/create-stock-in-from-demand-details` 權限被註解 | 任何登入使用者可呼叫 | Controller line 69 |
| `batchProcessStockRecords` 無方法層 @Transactional | 批次中途失敗造成資料不一致 | service line 122 |
| 採購入庫 signCode 前綴非 ST/CE/BP，但仍呼叫 updateSourceDocumentStatus → log warn 噪音 | 應該分流：「PMM 採購不需回寫上游」 | line 206 |
| `STOCK_NOT_EXISTS2` 錯誤碼名稱 — 為什麼有 2？ | 推測與 `STOCK_NOT_EXISTS` 區分 | ErrorCode 重複定義？ |
| `stockReason` 字典 enum 在 enum 內，但 DO 上是字串 | 寫入時無校驗 | DO + enum |
| `inboundTime` 對出庫單據語意不明（共用同欄位） | 命名應改 | DO `inboundTime` |
| `warehouseId` 在單頭是 Integer 但在明細是 Long | 型別不一致 | DO 兩處 |
| 並行入庫導致庫存讀-改-寫競爭 | 無樂觀鎖 / 悲觀鎖 | service line 144-176 |
| 「物流管理行事曆」端點傳入的 RawMaterialDemandStockInReqVO 是否會驗證歸屬使用者 / 區域？ | 跨模組權限控制 | service 未讀 |
| 共用一張表（stockType 0/1）但兩個 Controller (`/stock-record`、`/stock-record-head`) 命名暗示「歷史」與「申請主表」 — 命名混亂 | Tag「出入庫作業管理表头」/「歷史出入庫記錄」 | Controller Tag |
| BPM 流程：哪些情境會啟動簽核？目前看到的自動入庫都「已歸檔」 | 手動建立會啟動？需確認 | service 邏輯 |
| 編輯時的 stock 反沖邏輯如果存在，多次編輯是否會累加 | 重要 |
| 「入庫計數」`standardQuantity` 與「庫存異動數量」`invNumChange` 兩個欄位都在明細上，差異？ | 命名混亂 | DO |
