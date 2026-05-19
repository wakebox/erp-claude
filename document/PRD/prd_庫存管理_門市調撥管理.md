# PRD｜庫存管理 — 門市調撥管理

> 來源：逆向自 `kingmaker-module-whs` 後端程式碼（`controller/admin/stocktransfer/`、`service/stocktransfer/StockTransferDetailServiceImpl.java`、`dal/dataobject/stocktransfer/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **倉儲人員 / 店長 / 區經理**。當某個倉庫的食材有剩、另一個倉庫缺貨，我建立「調撥單」把食材從 A 倉移到 B 倉：

> 「信義店冷凍倉的牛肉餅還有 20 公斤、板橋店只剩 3 公斤已低於安全存量 → 建立調撥單把信義店 10 公斤調撥到板橋店」

調撥單**走簽核** → 通過後分兩步：先做「出庫」（A 倉減 10 公斤）、再做「入庫」（B 倉加 10 公斤），完成才算結案。

### 1.2 我要做什麼

- 建立調撥單（單頭：出庫倉 / 入庫倉 / 調撥時間 / 物流處理；明細：每品號 + 申請數量 + 確認數量 + 雙邊庫存）
- 編輯（含簽核狀態切換的特殊邏輯）
- 走簽核流程
- **歸檔後分兩階段執行**：
  - 出庫階段：減 A 倉 standardQuantity（呼叫 #41）
  - 入庫階段：加 B 倉 standardQuantity（呼叫 #40）
- 用 `signCode` 前綴 `ST` 觸發 batchProcessStockRecords 後的狀態回寫
- 試算 / 查詢輔助：
  - `compute-area-inventory`：對品號列表計算 A 倉 / B 倉的當前庫存
  - `get-by-opposite-stock-type`：出入庫互查（已出庫的單據作為入庫來源、反之）
  - `record-batch-by-sign-code`：依 signCode 生成入庫的 StockRecord 批次（給 #40 使用）

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 看 A 倉 / B 倉現有庫存 | 決定能調多少 |
| 申請數量與實際確認數量分開 | 廠商 / 物流可能無法配送全量 |
| 走簽核 | 跨店資源移動需審核 |
| 出入庫分兩步 | 物流配送有時間差 |
| 已歸檔後不能改 | audit |
| 用 ST 前綴觸發跨來源回寫 | 與 #40 / #41 串接 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 調撥單 CRUD（批次處理單頭+單身） | 一站式建單 |
| 區域庫存試算 API | 給編輯頁顯示「現有多少能調」 |
| 出入庫互查 API | 「找已出庫的單據作為入庫來源」場景 |
| `record-batch-by-sign-code` | 給 #40 / #41 從 signCode 反查出 StockRecord 批次 |
| BPM 流程整合 | 簽核 |
| 已歸檔保護（含「已簽核」「已歸檔」中文 / 簡繁體相容） | 防誤改 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 門市調撥管理（程式碼語：調拨单） |
| 所屬模組 | WHS（庫存管理） |
| 兄弟功能 | 入庫 (#40)、出庫 (#41)、倉儲查詢 (#38) |
| 主要頁面 | 調撥單編輯頁、單頭分頁、待簽分頁 |
| 簽核流程 | 有：`FormPathUniqueEnum.STOCK_TRANSFER` |
| 與 #40/#41 串接 | signCode 前綴 `ST`，由 batchProcessStockRecords 觸發跨來源回寫；signCode 由 `generateSignCode("門市調撥管理")` 產生 |

---

## 2. 功能目的

調撥是「**跨倉位移轉**」的核心節點：

1. **承上** — 倉儲規劃發現門市存量不平衡
2. **執行** — 透過 BPM 簽核 + 出入庫聯動完成搬移
3. **狀態同步** — 出入庫完成後回寫單頭 stockType
4. **試算輔助** — 編輯時即時看兩端庫存

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `whs_stock_transfer`（單頭 / `StockTransferDO`） | 單據編號、processStatus、區域、倉別、**出庫倉名 / 入庫倉名**、調撥時間、主旨、物流處理、`stockType`（出入庫已完成的旗標）、processInstanceId |
| `whs_stock_transfer_detail`（明細 / `StockTransferDetailDO`） | stockTransferId、品號、申請計數、確認數量、A 倉庫存、B 倉庫存、warehouseId |

### 3.2 兩個 Controller

| Controller | 用途 |
|---|---|
| `StockTransferController` `/whs/stock-transfer` | 主要查詢端點（分頁、待簽、刪除） |
| `StockTransferDetailController` `/whs/stock-transfer-detail` | 建立 / 編輯 / 試算 / 跨表查詢端點 |

**注意**：建立 / 編輯都在「明細」controller 上，因為都是「單頭 + 多筆明細」一起處理。

### 3.3 建立流程 `batchCreateStockTransferWithDetails`

```
1. signCode = generateSignCode("門市調撥管理")
2. processStatus = "待處理"
3. insert 單頭 → transferId
4. 對每筆明細 setStockTransferId → insert
5. 啟動 BPM 流程（FormPathUniqueEnum.STOCK_TRANSFER）
6. 回填 processInstanceId
```

### 3.4 編輯流程的特殊邏輯

`editStockTransferWithHead`：

1. 必須帶 id（否則拋 `STOCK_TRANSFER_ID_NOT_NULL`）
2. validateStockTransferCanUpdate：
   - 不存在 → `STOCK_TRANSFER_NOT_EXISTS`
   - processInstanceId 空且歸檔 → `STOCK_TRANSFER_ARCHIVED_CANNOT_UPDATE`
3. 若 processStatus 為「已簽核」/「已签核」 → **只更新 processStatus**（簽核節點推進專用）
4. 若 processStatus 為「已歸檔」/「已归档」 → **只更新 processStatus**
5. 否則 → 正常更新單頭與明細（明細為 null 時不刪除既有 — 避免簽核節點誤刪明細）

⚠️ **同時支援繁簡中文字面比對**（「已签核」/「已簽核」/「已归档」/「已歸檔」） — 一個欄位四種值的字串比對，易出錯（見 §11）。

### 3.5 已歸檔保護（同陷阱）

processInstanceId 空且歸檔 → 拒絕修改。有 processInstanceId 的歸檔**不被擋**（同 #26、#31–#35 陷阱）。

### 3.6 stockType 與 status 雙狀態

| 欄位 | 含義 |
|---|---|
| `processStatus` | BPM 流程狀態（待處理 / 待簽核 / 已簽核 / 已歸檔） |
| `stockType` | 出入庫執行狀態：null=未執行 / 0=已出庫 / 1=已入庫 |

由 #40/#41 `batchProcessStockRecords` 內 `updateStockTransferStatus(signCode, stockType)` 回寫。

### 3.7 三個試算 / 輔助 API

| 端點 | 用途 |
|---|---|
| `/compute-area-inventory` | 對品號列表計算 A 倉 / B 倉當前庫存（areaInvNum / inAreaInvNum） |
| `/get-by-opposite-stock-type` | 找「對向」的調撥單（已出庫 stockType=0 + stock_reason=SW02 的單據，給入庫時下拉選擇） |
| `/record-batch-by-sign-code` | 依調撥單 signCode 生成入庫的 StockRecord 批次（stock_reason=SW02），給 #40 使用 |

`stock_reason="SW02"` 為調撥事由代碼。

### 3.8 跨模組依賴

- `whs_stock`：試算與更新（透過 #40/#41）
- `whs_stock_record_head` / `whs_stock_record`：實際出入庫
- BPM：`STOCK_TRANSFER`

### 3.9 兩個 Controller 共用 service

雖然有兩個 controller，建立 / 編輯都委派到 `StockTransferDetailServiceImpl`。

---

## 4. 情境說明

### 4.1 正常流程 — 信義店調撥到板橋店

倉儲主管小李：

1. 進入調撥編輯頁，主表：
   - 區域：北一區
   - 出庫倉：信義店冷凍倉
   - 入庫倉：板橋店冷凍倉
   - 調撥時間：2026-05-25
   - 主旨：「信義店牛肉餅調板橋」
2. 明細加入「牛肉餅 LB-04」：
   - 點 /compute-area-inventory → 顯示信義店 20 公斤、板橋店 3 公斤
   - 申請數量 10 公斤、確認數量 10 公斤
3. POST /batch-process
4. 系統：
   - signCode = ST-2026-0518-001
   - processStatus = "待處理"
   - insert 單頭 + 明細
   - 啟動 BPM 流程
5. 主管簽核 → processStatus = 已簽核 → 第二步只改狀態

### 4.2 典型業務 — 簽核後出庫

簽核者點「執行出庫」（非本功能而是 #41 出庫管理或 BPM 流程觸發）：

1. 系統根據 ST-2026-0518-001 呼叫 /record-batch-by-sign-code 生成出庫 StockRecord 批次
2. 呼叫 #41 batchProcessStockRecords（stockType=0）
3. 信義店牛肉餅 -10 公斤
4. 系統依 sourceSignCode 前綴 ST → updateStockTransferStatus(ST-..., 0) → 調撥單 stockType=0

### 4.3 典型業務 — 物流配送後入庫

物流抵達板橋店：

1. 板橋店人員點「執行入庫」（從入庫管理或調撥單觸發）
2. 系統根據 signCode 找出對應的調撥單身
3. 建入庫 StockRecord 批次 → #40 batchProcessStockRecords
4. 板橋店牛肉餅 +10 公斤
5. 調撥單 stockType=1（覆寫 0），表示「已完整出入庫」

### 4.4 異常情境 — 編輯已歸檔但有 processInstanceId

編輯時：

- validateStockTransferCanUpdate：processInstanceId 非空 → 不擋
- 但編輯流程內部會依 processStatus = 已歸檔 → 只允許改 processStatus（line 136-143）

實際結果：**已歸檔且有流程實例的調撥單，仍可改 processStatus**（例如改回「待處理」）。**這個情境設計不明**（見 §11）。

### 4.5 規則分流 — 物流處理

`logistics` 字串欄位（單頭）— 業務語意不明，可能是「物流公司代號」或「物流類型」。前端如何使用需確認（見 §11）。

---

## 5. 操作流程

```
[使用者進入「門市調撥管理」]
  │
  ├─ 1. 建立 POST /whs/stock-transfer-detail/batch-process
  │    ├─ insert 單頭（signCode 自動生成）
  │    ├─ insert 明細
  │    └─ 啟動 STOCK_TRANSFER 流程
  │
  ├─ 2. 編輯 PUT /whs/stock-transfer-detail/edit-with-head
  │    ├─ 必帶 id、檢查存在 + 未歸檔（陷阱）
  │    ├─ 若 processStatus = 已簽核 / 已歸檔 → 只改狀態
  │    └─ 否則：更新單頭 + 明細（為 null 不刪明細）
  │
  ├─ 3. 取單筆 GET /whs/stock-transfer-detail/get-with-details?transferId=
  │
  ├─ 4. 試算 POST /whs/stock-transfer-detail/compute-area-inventory
  │    └─ 對品號列表算 A 倉 / B 倉庫存
  │
  ├─ 5. 出入庫互查 POST /whs/stock-transfer-detail/get-by-opposite-stock-type
  │
  ├─ 6. 依 signCode 取 StockRecord 批次
  │    GET /whs/stock-transfer-detail/record-batch-by-sign-code?signCode=
  │    └─ 給 #40 入庫使用
  │
  ├─ 7. 單頭刪除 / 明細刪除 DELETE /whs/stock-transfer/delete、/whs/stock-transfer-detail/delete
  │
  ├─ 8. 單頭分頁 / 待簽分頁 GET /whs/stock-transfer/page、/todo-page
  │
  └─ 9. 執行出庫 / 入庫（透過 #40/#41 跨模組）
       └─ batchProcessStockRecords → 觸發 updateStockTransferStatus 回寫
```

---

## 6. 欄位規格

### 6.1 單頭（`whs_stock_transfer`）

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| signCode | 單據編號（前綴 ST） |
| processStatus | 流程狀態（待處理 / 待簽核 / 已簽核 / 已歸檔） |
| area / areaName | 區域 |
| warehouseType / warehouseTypeName | 倉別 |
| outWarehouse / outWarehouseName | 出庫倉名 |
| inWarehouse / inWarehouseName | 入庫倉名 |
| transferTime | 調撥時間 |
| subject | 主旨 |
| logistics | 物流處理 |
| stockType | 出入庫旗標（null/0/1） |
| processInstanceId | BPM |

### 6.2 明細（`whs_stock_transfer_detail`）

| 欄位 | 中文業務語 |
|---|---|
| stockTransferId | 主表 ID |
| prodCode | 品號 |
| standardQuantity | 調撥申請計數 |
| confirmedQuantity | 確認數量 |
| areaInvNum | 出庫倉當前庫存（試算用） |
| inAreaInvNum | 入庫倉當前庫存（試算用） |
| warehouseId | 倉庫表 ID（出庫倉？） |

---

## 7. 商業邏輯

### 7.1 建立

略，見 §3.3。

### 7.2 編輯的狀態分流

- 已簽核 / 已歸檔 → 只改 processStatus
- 其他 → 更新單頭 + 明細

### 7.3 已歸檔保護（陷阱）

processInstanceId 空且歸檔 → 拒絕；非空 → 允許

### 7.4 stockType 回寫

由 #40/#41 觸發。

### 7.5 簡繁體相容比對

processStatus 同時支援「已簽核」「已签核」「已歸檔」「已归档」

---

## 8. 使用角色與權限

| 角色 | 可操作 | 對應權限字串 |
|---|---|---|
| 倉儲人員 / 店長 | 建立 / 編輯 / 查詢 | `whs:stock-transfer-detail:create`、`update`、`query` |
| 簽核主管 | 待簽分頁 + 簽核 | `whs:stock-transfer:query` + BPM |
| 系統管理員 | 刪除 | `whs:stock-transfer:delete`、`whs:stock-transfer-detail:delete` |

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節。建議：

### 9.1 編輯頁

- 主表：區域、倉別、出庫倉（cascade 來自 #39）、入庫倉（cascade 來自 #39）、調撥時間、物流處理、主旨
- 明細：品號、申請數量（input）、確認數量（input）、A 倉現有庫存（自動填）、B 倉現有庫存（自動填）
- 「重新試算庫存」按鈕

### 9.2 分頁

- 條件：流程狀態、stockType、區域、出庫倉、入庫倉、調撥時間
- 表格：單據編號、出庫倉 → 入庫倉、調撥時間、流程狀態、出入庫狀態

---

## 10. 功能範圍

### 10.1 包含的功能

- 調撥單 CRUD（單頭 + 明細）
- 區域庫存試算
- 出入庫互查
- 簽核流程整合
- 與 #40/#41 串接

### 10.2 預留但尚未實作 / 缺陷

- **簡繁體混搭比對**：line 127、136
- **已歸檔且有 processInstanceId 仍可改狀態**：陷阱
- **無「申請量 = 確認量 = 實際出庫量」校驗**
- **logistics 欄位語意未文件化**
- **stock_reason="SW02"** 字面值硬編

### 10.3 不包含

- 出入庫實際執行（#40/#41 共用一套程式）
- 倉庫主檔（#39）
- 庫存查詢（#38）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| processStatus 同時支援繁簡 4 種寫法易出錯 | i18n / 字典 enum 化 | service line 127、136 |
| 已歸檔且有 processInstanceId 仍可改 processStatus | 是否符合 audit 要求？ | service line 112 + 136-143 |
| `logistics` 欄位語意未說明 | 業務需確認 | DO |
| `stock_reason="SW02"` 硬編 | 字典化 | StockReasonEnum |
| 出庫量未必等於入庫量（運輸損耗）→ 程式無分流處理 | 業務需求 | 程式邏輯 |
| 申請量 vs 確認量 vs 實際出庫量三層無校驗 | 可能造成資料不一致 | DO |
| stockType=0（已出庫）後若取消，stockType 如何重置？ | 程式無此入口 | service |
| `compute-area-inventory` 對「品號為空 / 倉庫為空」的處理 | xml 未讀 | service line 86-92 |
| 「物流處理」與 #23 物流類型維護表的關係 | 跨模組欄位對應 | DO |
| `logistics` 是否該指向 `pdm_logistics_type.id`？ | 若是，型別應為 Long | DO `logistics` 是 String |
| `signCode` 前綴 `ST` 是與 generateSignCode 規則對應，需確認 | 前綴對齊回寫邏輯（#40 service） | service line 99 |
| 編輯時明細為 null 不刪除 — 簽核節點正確，但前端正常編輯漏傳明細也會被當「不變」 | 業務語意需確認 | service line 148-150 |
| 區域 area 是 Long，但 #39 倉庫主檔的 area 是 Integer | 型別不一致 | DO |
