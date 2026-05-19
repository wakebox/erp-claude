# PRD｜採購管理 — 驗收確認作業

> 來源：逆向自 `kingmaker-module-pmm` 後端程式碼（`controller/admin/puracceptance/PurAcceptanceController.java`、`service/puracceptance/PurAcceptanceServiceImpl.java`、`dal/dataobject/puracceptance/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **驗收人員 / 倉儲人員**。結轉驗收（#34）填了「本次驗收數量」並結轉後，系統自動產生「驗收確認單」 — 這是「**實際收貨確認**」單據。我負責：

> 「對廠商實際到貨的品項與數量做最後確認 → 填短缺數量（若有）、入庫數量 → 走簽核 → 歸檔瞬間系統自動建立入庫單（#40），扣留入庫處理會更新 WHS 庫存」

### 1.2 我要做什麼

- 檢視 / 編輯系統自動產生的驗收確認單（單頭 + 明細）
- 對每筆明細確認「本次驗收數量」`inspectedQty`、「入庫數量」`stockQty`、「短缺數量」`shortageQty`
- 走簽核流程
- **歸檔瞬間**：自動產生「入庫單」（WHS 模組，stockRecordHead + stockRecord）、設入庫原因 `SW05`、更新庫存
- 分頁查詢、待簽分頁、單筆查詢（含明細與廠商代號）、Excel 匯出
- 取廠商報價下拉清單

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 確認實到數量與簽收 | 防止廠商虛報 / 短缺漏記 |
| 入庫量可能 < 驗收量 | 部分壞品不入庫 |
| 短缺數量分開記 | 之後對廠商索賠 / 退款用 |
| 歸檔自動入庫 | 不要倉儲人員再手動建入庫單 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 驗收確認 CRUD（單頭 + 明細） | 主要由 #34 結轉自動建 |
| 簽核流程 | 收貨金額確認 |
| 歸檔自動入庫（建 stockRecordHead + stockRecord + 更新庫存） | 串到 WHS 入庫管理 |
| 取單筆時補 mfrCode + 食材名稱 | 前端顯示完整 |
| 廠商報價下拉 | 編輯時選擇 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 驗收確認作業 |
| 所屬模組 | PMM（採購管理） |
| 兄弟功能 | 結轉驗收 (#34)、入庫作業 (WHS #40) |
| 主要頁面 | 驗收確認編輯頁、單頭分頁、待簽分頁 |
| 簽核流程 | 有：`FormPathUniqueEnum.PUR_ACCEPTANCE` |
| 自動觸發下游 | 歸檔瞬間建立 WHS 入庫單 + 庫存更新（透過 `stockRecordService.batchProcessStockRecords`） |

---

## 2. 功能目的

驗收確認是「**實際收貨確認**」+「**自動入庫**」的雙重節點：

1. **承接 #34 結轉驗收** — `forwardSignCode` 為對外鍵
2. **三量再次確認** — 本次驗收量、實際入庫量、短缺量
3. **自動入庫** — 歸檔瞬間建立 WHS 入庫單（stockReason="SW05"）、更新庫存
4. **跨模組橋樑** — 從 PMM（採購側）跨到 WHS（倉儲側）

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `pmm_pur_acceptance`（單頭 / `PurAcceptanceDO`） | 單據編號、廠商 ID/名、交貨地點、`forwardSignCode`、驗收日期、主旨、processStatus、processInstanceId |
| `pmm_pur_acceptance_detail`（明細 / `PurAcceptanceDetailDO`） | purAcceptanceId、orderSignCode、prodCode、mfrUnit、inspectedQty、stockQty、shortageQty、warehouseId、remark |

### 3.2 三量定義

| 欄位 | 含義 |
|---|---|
| inspectedQty | 本次驗收數量（廠商實際到貨被檢查的量） |
| stockQty | 入庫數量（預設 = inspectedQty） |
| shortageQty | 短缺數量（預設 = 0） |

公式：

```
正常情況：stockQty = inspectedQty, shortageQty = 0
有壞品/短缺：stockQty < inspectedQty, shortageQty = inspectedQty - stockQty
```

⚠️ 程式碼**未強制** stockQty + shortageQty = inspectedQty — 使用者可手動填出不一致的值（見 §11）。

### 3.3 已歸檔保護

同 #31–#34：`processInstanceId 空且歸檔` → 拒絕。

### 3.4 歸檔瞬間自動入庫

`updatePurAcceptance` 在 `processStatus="已歸檔"` 時呼叫 `processStockIn(reqVO)`：

```
1. 查 selectStockInData(id) → 一次性 join 驗收明細 + 倉庫資訊（PurAcceptanceStockInVO 列表）
2. 建 StockRecordHeadDO（入庫單頭，WHS 表）：
   - signCode = generateSignCode("入庫作業管理")
   - processStatus = "已歸檔"（直接定案）
   - stockReason = "SW05"（採購入庫代碼）
   - sourceSignCode = 第一筆驗收單號
   - stockType = 1
   - inboundTime = now
   - subject = "驗收入庫 - " + signCode
   - remark = "由驗收單自動生成"
   - area / warehouseType / warehouse 等：取「有完整倉庫資訊」的第一筆，否則第一筆
3. insert 單頭 → recordId
4. 對每筆明細建 StockRecordDO：
   - recordId、warehouseId、prodCode、stockReason="SW05"、sourceSignCode
   - stockType = 1
   - standardQuantity = stockQty
   - invNumChange = stockQty
5. 逐筆 insert（**非 batch**，line 306）
6. stockRecordService.batchProcessStockRecords(list) → 更新 WHS 庫存
```

來源：`PurAcceptanceServiceImpl.java:214-310`。

關鍵：

- **入庫單直接設為「已歸檔」**，跳過 WHS 入庫單的簽核流程（與 #29「自動產生需求預測單已歸檔」設計一致）
- **stockReason = "SW05"** 固定字串（推測為「採購入庫」代碼，需查 WHS 模組字典確認）
- **逐筆 insert 而非 batch**：效能差，且註解寫「批量插入」實為迴圈單筆

### 3.5 取單筆時的多表合成

`getPurAcceptanceWithDetails`：

1. 查單頭
2. 用 mfrId 查 `vendorQuoteMapper.selectById(mfrId)` 取 mfrName 和 mfrCode 寫回 RespVO（同 #33 的 mfrId 命名問題）
3. 用 `purAcceptanceDetailMapper.selectDetailsWithIngredientName(id)` 取明細並 join 食材名稱

⚠️ 同 #33：DO 上的 `mfrId` 實際是「廠商報價維護內部 ID」，不是「廠商代號」字串。

### 3.6 跨模組依賴

- WHS `StockRecordHeadMapper` / `StockRecordMapper` / `StockRecordService`：建入庫單 + 更新庫存
- VQM `VendorQuoteMapper`（#28）：取廠商代號
- PDM 食材 mapper：join 食材名稱
- BPM：`PUR_ACCEPTANCE`

### 3.7 編輯子表的策略

刪舊插新（同前述功能）。

### 3.8 PmmConstants.ARCHIVED 常數

本功能引入 `PmmConstants.ARCHIVED` 而非自己宣告 — 較好的常數管理。

---

## 4. 情境說明

### 4.1 正常流程 — 全數正常入庫

驗收人員小李在「待簽分頁」看到 PA-2026-001（由 #34 結轉產生）：

- 牛肉餅 LB-04 inspectedQty=2、stockQty=2、shortageQty=0
- 起司 PKG-CHEESE inspectedQty=3、stockQty=3、shortageQty=0

她確認無誤，點「歸檔」（透過 BPM）：

1. validatePurAcceptanceExists 通過
2. 更新明細（刪舊插新）
3. updateById
4. processStatus="已歸檔" → 觸發 processStockIn：
   - 撈 join 後的入庫資料
   - 建入庫單頭（signCode="入庫單管理"、stockReason="SW05"）
   - 建 2 筆入庫明細
   - 逐筆 insert
   - `batchProcessStockRecords` → 更新 WHS 庫存
5. 倉儲在 WHS 庫存查詢看到牛肉餅 +2、起司 +3

### 4.2 典型業務 — 短缺處理

某批起司 inspectedQty=3 但 1 包破損，實際入庫 2：

- 編輯：stockQty=2、shortageQty=1
- 歸檔
- WHS 庫存只 +2

短缺數量留在驗收單上做後續對廠商索賠依據。

### 4.3 異常情境 — stockQty + shortageQty ≠ inspectedQty

使用者填 inspectedQty=3、stockQty=2、shortageQty=0（漏記短缺）：

- 系統不擋
- WHS 庫存 +2，但 inspectedQty(3) 與 stockQty(2) 不一致無法追溯

### 4.4 規則分流 — 編輯已歸檔的單

同 #31–#34 陷阱：processInstanceId 空且歸檔 → 擋；非空且歸檔 → 不擋。

### 4.5 異常情境 — 自動入庫失敗

若 `selectStockInData` 回空（line 217-219） → return，不會入庫，但單頭已經是「已歸檔」狀態。**資料不一致**：驗收歸檔但庫存未動（見 §11）。

---

## 5. 操作流程

```
[#34 結轉驗收結轉操作]
  └─ 自動建立驗收確認單

[驗收人員進入「驗收確認作業」]
  │
  ├─ 1. 建立 POST /pmm/pur-acceptance/create
  │    ├─ signCode 為空則自動生成
  │    ├─ insert 單頭 + 明細
  │    └─ 啟動 BPM 流程
  │
  ├─ 2. 更新 PUT /pmm/pur-acceptance/update
  │    ├─ 檢查存在 + 未歸檔
  │    ├─ 更新明細（刪舊插新）
  │    ├─ updateById 單頭
  │    └─ 若 processStatus="已歸檔" → processStockIn
  │         ├─ 建入庫單頭（stockReason="SW05"）
  │         ├─ 建入庫明細
  │         ├─ 逐筆 insert
  │         └─ batchProcessStockRecords 更新庫存
  │
  ├─ 3. 刪除 DELETE /pmm/pur-acceptance/delete?id=
  │
  ├─ 4. 取單筆 GET /pmm/pur-acceptance/get?id=
  │    ├─ 補 mfrName + mfrCode（查 vendor_quote_maintenance）
  │    └─ 明細補 ingredientName（join 食材）
  │
  ├─ 5. 分頁 / 待簽分頁 GET /page、/todo-page
  │
  ├─ 6. 取明細 GET /pur-acceptance-detail/list-by-pur-acceptance-id?purAcceptanceId=
  │
  ├─ 7. 廠商報價下拉 GET /vendor-quote-dropdown
  │
  └─ 8. 匯出 Excel GET /export-excel
```

---

## 6. 欄位規格

### 6.1 單頭（`pmm_pur_acceptance`）

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| signCode | 單據編號 |
| mfrId | 廠商 ID（指向報價維護內部 ID） |
| mfrName | 廠商名稱 |
| warehouse / warehouseName | 交貨地點 |
| forwardSignCode | 對應結轉驗收單號 |
| acceptDate | 驗收日期 |
| subject | 主旨 |
| processStatus / processInstanceId | BPM |

### 6.2 明細（`pmm_pur_acceptance_detail`）

| 欄位 | 中文業務語 |
|---|---|
| purAcceptanceId | 主表 ID |
| orderSignCode | 採購單號 |
| prodCode | 品號 |
| mfrUnit / mfrUnitName | 廠商單位 |
| inspectedQty | 本次驗收數量 |
| stockQty | 入庫數量 |
| shortageQty | 短缺數量 |
| warehouseId | 倉庫 ID |
| remark | 備註 |

---

## 7. 商業邏輯

### 7.1 三量

inspectedQty / stockQty / shortageQty — 預設 stockQty=inspectedQty、shortageQty=0

### 7.2 已歸檔保護

`processInstanceId 空且歸檔` → 拒絕

### 7.3 自動入庫流程

略，見 §3.4。重點：

- stockReason 固定 "SW05"
- 入庫單直接已歸檔
- 逐筆 insert（效能差）

### 7.4 取單筆補 mfrCode / 食材名

兩個 SQL 補資料（mfrCode 用 selectById、食材名用 mapper SQL join）

---

## 8. 使用角色與權限

| 角色 | 可操作 | 對應權限字串 |
|---|---|---|
| 驗收人員 / 倉儲人員 | CRUD / 查詢 / 匯出 | `pmm:pur-acceptance:create`、`update`、`delete`、`query`、`export` |
| 簽核主管 | 待簽 + 簽核 | `query` + BPM |

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節。建議：

### 9.1 編輯頁

- 主表：單據編號、廠商（顯示 mfrCode + 名稱）、交貨地點、forwardSignCode 連結、驗收日期、主旨
- 明細表格：品號（連結食材名）、本次驗收量、入庫量（input）、短缺量（input）、倉庫、備註
- 「歸檔」按鈕：透過 BPM 流程節點觸發

### 9.2 分頁

- 條件：流程狀態、forwardSignCode、廠商、acceptDate 區間
- 表格：單據編號、廠商、forwardSignCode、acceptDate、流程狀態

---

## 10. 功能範圍

### 10.1 包含的功能

- 驗收確認 CRUD
- 已歸檔保護
- 歸檔自動建入庫單 + 更新庫存
- 取單筆時補 mfrCode + 食材名稱
- 廠商報價下拉
- BPM 流程整合
- 待簽分頁、Excel 匯出

### 10.2 缺陷

- **三量無校驗**：stockQty + shortageQty 不必等於 inspectedQty
- **逐筆 insert 而非 batch**：line 306
- **若 selectStockInData 回空，單頭已歸檔但無入庫**：line 217-219 靜默 return
- **stockReason "SW05" 字面值硬編**
- **mfrId 命名混亂**：同 #33

### 10.3 不包含

- 結轉驗收（#34，本功能上游）
- 入庫單管理（WHS #40，本功能歸檔自動建立）
- 庫存更新（WHS）
- 安全存量設定（#36/#37）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| 三量無校驗，可能產生資料不一致 | inspectedQty ≠ stockQty + shortageQty | DO + service 無檢查 |
| stockReason="SW05" 硬編，業務含義未文件化 | 字典化 | line 249、283 |
| 逐筆 insert 而非 batch | 效能 | line 306 |
| selectStockInData 回空時靜默 return，單頭已歸檔但無入庫 | 資料不一致風險 | line 217-219 |
| 自動建立的入庫單 processStatus="已歸檔"，跳過 WHS 入庫簽核 | 是否符合內控？ | line 248 |
| 入庫單頭只取「第一筆有完整倉庫資訊」的記錄做主表資訊 | 若多倉庫，會落到第一個 | line 240-244 |
| mfrId 命名混亂（同 #33） | 命名 | line 189-192 |
| 已歸檔保護同 #31-#34 陷阱 | line 129 |
| 編輯刪舊插新導致明細 id 變動 | line 169-173 |
| 「驗收入庫」subject 中文 + signCode | i18n | line 253 |
| 重複歸檔是否會二次入庫？ | processStatus="已歸檔" 的 update 會再次 processStockIn | line 105-107 — **無 archivedBefore 檢查！** ⚠️ 與 #31-33 設計不一致，可能重複入庫 |
| `selectStockInData` SQL 邏輯複雜 | xml 未讀 | line 216 |
| stockType=1 字面 | 字典 / enum 化 | line 251 |
| 廠商報價下拉 `getVendorQuoteDropdownList` 撈全表 | 大量資料時效能 | line 204 |
| 「短缺數量」是否在驗收歸檔後可作為索賠依據？ | 業務流程缺失，目前只記不行動 | DO `shortageQty` |
