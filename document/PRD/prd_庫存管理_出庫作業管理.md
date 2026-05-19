# PRD｜庫存管理 — 出庫作業管理

> 來源：逆向自 `kingmaker-module-whs` 後端程式碼。本功能與 [入庫作業管理 (#40)](prd_庫存管理_入庫作業管理.md) **共用同一套程式碼與資料表** — `whs_stock_record_head` / `whs_stock_record`，由 `stockType` 欄位區分（0=出庫 / 1=入庫）。本文件聚焦於出庫（stockType=0）的特殊邏輯，其他重複部分請參照 #40。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **倉儲人員 / 店長 / 採購助理**。當倉庫的食材要：

- 領用（餐廳營業日常使用）
- 調撥到他店（透過 #42 觸發）
- 報損（透過 #47 不良品觸發）
- 盤點調整（透過 #43–#46 盤虧調整）

我就需要建立「出庫單」，**從 `whs_stock` 庫存表扣減對應品號的數量**。

### 1.2 我要做什麼

- 透過共用的「批次處理」入口建立出庫（stockType=0）
- 出庫前必須先有對應庫存記錄，否則拋 `STOCK_NOT_EXISTS2`
- 出庫量從現有 `standardQuantity` 減去
- 系統根據 sourceSignCode 前綴自動更新對應單據狀態：
  - `ST` → 調撥單回寫 stockType
  - `CE` → 盤點單回寫 stockType
  - `BP` → 不良品單回寫 stockType
- 編輯既有單頭 / 明細
- 分頁查詢（出入庫混合，依 stockType 過濾）

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 出庫必須先有庫存 | 防止庫存變負 |
| 多種出庫來源整合 | 調撥 / 報損 / 盤調都走同一入口 |
| 出庫後自動回寫上游單據狀態 | 上游不用再二次呼叫 |
| 一筆出庫對應一筆庫存異動 | 不要把減法寫在多處 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| `batchProcessStockRecords` 出庫分支 | 減庫存的唯一機制 |
| 庫存不存在檢查 | 防呆 |
| 跨來源狀態回寫（同 #40） | 上游單據驅動 |
| 分頁查詢（出入庫混合） | 倉儲日常檢視 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 出庫作業管理 |
| 所屬模組 | WHS（庫存管理） |
| 與 #40 關係 | **共用** `whs_stock_record_head` / `whs_stock_record`，stockType=0 |
| Controller / Service | 與 #40 完全相同 — `StockRecordController` / `StockRecordHeadController` |
| 簽核流程 | 與 #40 相同 |
| 觸發來源 | #42 調撥（部分出庫）/ #47 不良品 / #43–#46 盤點調整 |

---

## 2. 功能目的

出庫作業是「**WHS 模組的庫存減量唯一機制**」：

1. **`processOutboundStock`** 是唯一可減少 `whs_stock.standardQuantity` 的入口
2. **共用表設計** — 與入庫同表同 service，以 stockType 區分
3. **必驗證庫存存在** — 防止庫存變負
4. **跨單據狀態同步** — 出庫完成後回寫上游

---

## 3. 業務邏輯背景

### 3.1 與 #40 共用的程式邏輯

| 項目 | 來源 |
|---|---|
| 兩張表 | 同 #40 §3.1 |
| 端點 | 同 #40 §5（`/stock-record`、`/stock-record-head`） |
| 批次處理流程 | 同 #40 §3.2，分流為 inbound / outbound |
| 跨來源回寫 | 同 #40 §3.2 — ST/CE/BP 前綴 |

### 3.2 出庫專屬邏輯：`processOutboundStock`

```java
1. 用 (prodCode, warehouseId) 查 whs_stock
2. existingStock == null → throw exception(STOCK_NOT_EXISTS2)
3. 對 standardQuantity 做減法：
   existingStock.standardQuantity -= stockRecordVO.standardQuantity
4. update whs_stock
```

**問題點**（程式邏輯推測）：

- **不檢查減法後是否為負值** — 庫存可能變負（見 §11）
- **不檢查 stockRecordVO.standardQuantity 是否為正** — 若使用者傳負值，會反向變成加法

### 3.3 出庫事由（stockReason）

字典 enum，常見出庫類型推測：

- `SW06` 等：調撥出庫
- `SW07` 等：盤虧調整
- `SW08` 等：不良品報損

實際值由 `StockReasonEnum` 維護（未深查）。

### 3.4 跨來源回寫（ST/CE/BP）

詳見 #40 §3.2。三類來源：

- ST（StockTransfer 調撥）：見 #42
- CE（CheckTake 盤點）：見 #43+
- BP（BadProduct 不良品）：見 #47

### 3.5 出庫時的庫存讀-改-寫競爭

無樂觀鎖、無悲觀鎖。並行兩筆出庫同品號同倉時可能造成：

- A 讀 quantity=10
- B 讀 quantity=10
- A 寫 quantity=10-3=7
- B 寫 quantity=10-5=5 ← 應該是 2

詳見 §11。

---

## 4. 情境說明

### 4.1 正常流程 — 調撥出庫

#42 調撥單 ST-2026-001（信義店 → 板橋店）執行：

1. 系統建立兩筆 StockRecord：
   - 出庫端：stockType=0、sourceSignCode=ST-2026-001、warehouseId=信義店倉、standardQuantity=2 公斤
   - 入庫端：stockType=1、sourceSignCode=ST-2026-001、warehouseId=板橋店倉、standardQuantity=2 公斤
2. `batchProcessStockRecords([出庫筆, 入庫筆])`：
   - 出庫：查信義店倉牛肉餅 → 有 10 公斤 → 減為 8 公斤
   - 入庫：查板橋店倉牛肉餅 → 有 5 公斤 → 加為 7 公斤
   - sourceSignCode 前綴 ST → 同步更新調撥單 stockType

### 4.2 異常情境 — 出庫無庫存

某新進門市還沒有任何牛肉餅庫存，調撥單請求從該門市出 2 公斤：

- 查 stock → null
- 拋 `STOCK_NOT_EXISTS2`，訊息「庫存不存在」
- 整個 batch 失敗（但**無 @Transactional 在方法層**，前面已處理的可能未回滾，見 #40 §11）

### 4.3 異常情境 — 庫存不足扣到負值

庫存 10 公斤，使用者誤填出庫 15 公斤：

- 查 stock → 有
- existingStock.standardQuantity = 10 - 15 = -5
- update whs_stock → 庫存 -5

⚠️ 程式無檢查 — 庫存變負是隱性錯誤（見 §11）。

### 4.4 規則分流 — 不良品出庫

#47 不良品單 BP-2026-001 確認報損 5 公斤過期食材：

- 建 StockRecord stockType=0、sourceSignCode=BP-...、standardQuantity=5
- batchProcessStockRecords → 減庫存
- updateBadProductStatus(BP-..., 0) → 不良品單 stockType 回寫

---

## 5. 操作流程

```
[出庫來源]
  ├─ #42 調撥（信義店出庫 + 板橋店入庫）
  ├─ #47 不良品報損
  ├─ #43–#46 盤點：盤虧 → 出庫
  └─ 手動 → /batch-process（系統管理員直接出庫）

[batchProcessStockRecords - 出庫分支]
  │
  └─ 對每筆 StockRecordDO (stockType=0)：
       ├─ 查 stock by (prodCode, warehouseId)
       ├─ 不存在 → throw STOCK_NOT_EXISTS2
       ├─ processOutboundStock：standardQuantity -= 異動量
       └─ update whs_stock
     ↓
     updateSourceDocumentStatus：
       ├─ ST → 更新調撥單 stockType
       ├─ CE → 更新盤點單 stockType
       └─ BP → 更新不良品單 stockType
```

---

## 6. 欄位規格

與 #40 完全相同。

**過濾出庫只要**：`stockType = 0`

---

## 7. 商業邏輯

### 7.1 出庫減法（唯一機制）

```
1. 查 stock：須存在（否則 STOCK_NOT_EXISTS2）
2. standardQuantity -= 異動量
3. 不檢查負值（⚠️ bug）
```

### 7.2 跨單據狀態回寫

同 #40 §7.3。

---

## 8. 使用角色與權限

| 角色 | 可操作 | 對應權限字串 |
|---|---|---|
| 倉儲人員 / 店長 | 透過 /batch-process 建出庫 | `whs:stock-record:create` |
| 上游模組（#42、#47、#43+） | service 內部呼叫 | — |
| 簽核 / 查詢 | 同 #40 | 同上 |

---

## 9. 畫面需求 / 視覺規範

通常**沒有獨立的「出庫單」UI**，因為出庫由上游業務模組（調撥、不良品、盤點）的歸檔自動觸發。

若要查詢「出庫歷史」：

- 進入「歷史出入庫記錄」分頁（同 #40）
- 過濾 stockType=0
- 表格欄位：單據編號、來源單號（連結到上游）、stockReason 中文、倉名、品號、出庫數量、時間

---

## 10. 功能範圍

### 10.1 包含的功能

- 透過共用入口進行出庫（減庫存）
- 出庫前的庫存存在性檢查
- 跨來源狀態回寫（ST/CE/BP）
- 與入庫共用 CRUD / 分頁 / 待簽

### 10.2 預留但尚未實作 / 缺陷

- **不檢查減法後負值**：庫存可能變負
- **不檢查 standardQuantity 為正**：負值會反向變加法
- **無 @Transactional 在 batchProcessStockRecords**：中途失敗無法回滾
- **無樂觀鎖**：並行出庫競爭
- **未知 sourceSignCode 前綴只 log warn**：不通知

### 10.3 不包含

- 調撥單本身（#42）
- 不良品單（#47）
- 盤點單（#43–#46）
- 入庫管理（#40，共用 80% 程式碼）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| 出庫不檢查庫存是否足夠 → 可能變負 | 業務需求 | `processOutboundStock`（推測，與 inbound 對稱） |
| `STOCK_NOT_EXISTS2` 為什麼有 2？ | 與 `STOCK_NOT_EXISTS` 區分？ | #40 同一問題 |
| 並行出庫無樂觀鎖 | 線上常見競爭問題 | service line 144-176 |
| 出庫 stockReason 字典定義 | 哪些情境對應哪個 code | StockReasonEnum |
| 「手動出庫」（非透過 #42/#47/#43+）的情境是否存在？前綴非 ST/CE/BP 時跨來源不回寫 | 業務需確認 | 同 #40 §11 |
| 是否該對「出庫到負值」加 ServiceException？ | 業務安全 | 程式邏輯 |
| 出庫與入庫共用 controller / service，但業務語意分明 — 是否該拆？ | 維護性 | Controller |
| 編輯 / 刪除出庫單時是否回沖庫存？ | 與 #40 同樣問題 | service 未明示 |
