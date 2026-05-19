# PRD｜採購管理 — 採購單管理

> 來源：逆向自 `kingmaker-module-pmm` 後端程式碼（`controller/admin/purorder/PurOrderController.java`、`service/purorder/PurOrderServiceImpl.java`、`dal/dataobject/purorder/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **採購人員**。報價管理（#32）核准歸檔後，系統按廠商分群自動產生**多張採購單**（一個廠商一張）。我負責：

> 「對每張採購單檢視內容（廠商、品項、數量、單價、金額、稅）→ 確認無誤後送簽核 → 歸檔時系統自動產生『結轉驗收單』（#34），交給驗收方收貨」

### 1.2 我要做什麼

- 檢視 / 編輯系統自動產生的採購單（也可手動建立）
- 確認單頭金額（未稅、稅額、稅後）與每筆明細
- 採購備註、單價調整、付款代碼、運費
- 送簽核
- **歸檔瞬間自動產生「結轉驗收單」**（同 orderSignCode，幂等保護）
- 啟動結轉驗收單的 BPM 流程
- 分頁查詢、待簽分頁、單筆查詢、Excel 匯出
- 分頁回傳時把 mfrId（內部 ID）二次查詢補上「真實廠商代號」(mfrCode) 給前端

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 看到稅前 / 稅 / 稅後分開 | 財會與廠商對帳要分開 |
| 每筆明細顯示請購單號與項次 | 追溯這筆採購對應哪個請購需求 |
| 編輯前置條件：未歸檔 | 已歸檔的不能改 |
| 歸檔自動產生結轉驗收 | 不要採購助理再手動轉錄 |
| 多筆明細可調整 | 廠商可能臨時告知部份品項缺貨、需調整數量 |
| 付款週期與條件可帶入 | 從廠商主檔的交易條件 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 採購單 CRUD（單頭 + 明細） | 主由 #32 自動建，但保留手動建立彈性 |
| 已歸檔保護 | 鎖定 |
| 歸檔自動產生結轉驗收單（幂等） | 銜接 #34 |
| 分頁回傳補 mfrCode | 前端不必再二次查 |
| BPM 流程整合 | 簽核 |
| 待簽分頁 | 主管處理 |
| Excel 匯出 | 對廠商發送或對帳 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 採購單管理（程式碼 Tag「採購申請單」） |
| 所屬模組 | PMM（採購管理） |
| 兄弟功能 | 報價管理 (#32)、結轉驗收 (#34)、驗收確認 (#35)、廠商資料 (#27) |
| 主要頁面 | 採購單編輯頁、單頭分頁、待簽分頁、Excel 匯出 |
| 簽核流程 | 有：`FormPathUniqueEnum.PURCHASING` |
| 自動觸發下游 | 歸檔時建立 #34 結轉驗收單 |

---

## 2. 功能目的

採購單是「**正式對廠商下單**」的單據：

1. **承接 #32 報價單** — `quoteSignCode` 為對外鍵；按廠商分群已在 #32 完成
2. **金額落地** — 未稅 / 稅 / 稅後三層金額在報價歸檔時就算好
3. **簽核管控** — 採購支出最後的內部核可
4. **銜接 #34 結轉驗收** — 歸檔瞬間自動建驗收單，把單據交給驗收方

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `pmm_pur_order`（單頭 / `PurOrderDO`） | 單據編號、採購日期、主旨、備註、`quoteSignCode`、廠商 ID/名、未稅 / 稅 / 稅後金額、計稅方式、付款代碼、週期 / 乘數 / 屬日、運費、流程狀態、流程實例 ID |
| `pmm_pur_order_detail`（明細 / `PurOrderDetailDO`） | purOrderId、`reqSignCode` / `reqItem`（追溯請購）、prodCode、單一計數計量、採購計量 / 單位、採購計數 / 單位、廠商單位、單價、採購數量 `purQty`、行金額 `lineAmount`、需求日期、預定交期、交貨地點、備註 |

### 3.2 雙重身分：mfrId vs mfrCode

`PurOrderDO.mfrId` 是 **Long** — 看起來像「廠商主檔內部 ID」，但 `getPurOrderPageWithMfrId` 內用它去查 `vendorQuoteMapper.selectById(mfrId)`（廠商報價維護表 ID），再取出 `pmmMfrBasicFinalDO.getMfrId()`（**這個是廠商報價的 mfrId 字串欄位**），寫入 `mfrCode`。

這代表：

- DO 的 `mfrId` 實際是「廠商報價的內部 ID」（不是廠商主檔 ID 也不是廠商代號字串）
- 前端要顯示的「廠商代號」由分頁端在 service 端二次查詢補進 `mfrCode`

⚠️ 命名混亂：建議改名（見 §11）。

來源：`PurOrderServiceImpl.java:148-171`。

### 3.3 已歸檔保護

同 #31、#32：`processInstanceId 空且歸檔` → 拋 `PUR_ORDER_ARCHIVED_CANNOT_UPDATE`

### 3.4 歸檔瞬間自動產生結轉驗收單

`generateForward(orderId)`：

```
1. SQL 從 pur_order_detail 跨表撈：
   - generateForwardHead(orderId) → PurForwardDO（單頭，含 orderSignCode 為對外鍵）
   - generateForwardDetail(orderId) → PurForwardDetailDO 清單
2. 任一為空 → return
3. 幂等檢查：用 orderSignCode 查 pur_forward 是否已存在 → 有則 return
4. signCode = generateSignCode("結轉驗收作業")
5. insert 單頭
6. 對每明細 setPurForwardId(forwardId) → batch insert
7. 啟動結轉驗收 BPM 流程
```

關鍵：**雙層幂等保護**（archivedBefore 檢查 + orderSignCode 查 forward 表）

來源：`PurOrderServiceImpl.java:104-108、278-296`。

### 3.5 編輯子表的策略

刪舊插新（同 #27 / #28 / #31 / #32）。

### 3.6 跨模組依賴

- `vendorQuoteMapper`（#28）：分頁時補 mfrCode
- `purForwardMapper` / `purForwardDetailMapper`（#34）：歸檔建驗收單
- BPM：`PURCHASING` 表單路徑

### 3.7 採購單的金額由 #32 帶來

- `untaxedAmount` / `taxAmount` / `totalAmount` 在 #32 歸檔時算好寫入
- 採購單編輯時可改？— 推測前端可改但程式無校驗，編輯後金額會落地不一致（見 §11）

### 3.8 付款 / 週期欄位

採購單上有 `paymentId / cycle / cycleMultiplier / cycleDay` — 這些通常從廠商主檔（#27）的交易條件帶入。但程式無自動填邏輯，由建立者填或從 #32 自動產生時帶入（見 §11）。

---

## 4. 情境說明

### 4.1 正常流程 — 採購人員確認 + 歸檔

採購人員小李在「待簽分頁」看到 PO-2026-001（冷凍肉商）：

- 廠商：冷凍肉商（mfrCode 由分頁自動補）
- 明細：牛肉餅 LB-04 4 箱 × 4500 = 18000
- 未稅 18000、稅 900、稅後 18900

她確認無誤，點「歸檔」（透過 BPM 流程）：

1. validatePurOrderExists 通過
2. 更新明細（刪舊插新）
3. updateById
4. archivedNow=true, archivedBefore=false → generateForward(orderId)
5. 系統：
   - SQL 撈 forward head 與 detail（從 pur_order_detail + 關聯表）
   - 幂等：未有 forward → 建立
   - signCode = generateSignCode("結轉驗收作業")
   - insert forward 單頭 + 明細
   - 啟動 forward BPM 流程
6. 驗收人員在 #34 看到新單據

### 4.2 異常情境 — 重複歸檔

BPM 二次觸發 archived update：

- archivedBefore=true → 不再呼叫 generateForward
- 即使繞過第一層，`purForwardMapper.selectOne(orderSignCode)` 也會擋

### 4.3 規則分流 — 分頁顯示廠商代號

前端打 /page：

- DB 撈 PurOrderDO（mfrId 為內部 ID）
- 對每筆 select_by_id 從 vendor_quote_maintenance 取廠商代號字串
- 寫入 RespVO.mfrCode 給前端顯示

⚠️ N+1 查詢風險：大量分頁時對每筆執行一次 selectById（見 §11）

### 4.4 規則分流 — 編輯已歸檔且 processInstanceId 為空

被擋（拋 PUR_ORDER_ARCHIVED_CANNOT_UPDATE）。若 processInstanceId 非空 → 允許編輯（同陷阱）。

---

## 5. 操作流程

```
[#32 報價單歸檔]
  └─ 自動建立採購單（按廠商分群）

[採購人員進入「採購單管理」]
  │
  ├─ 1. 建立 POST /pmm/pur-order/create
  │    ├─ insert 單頭 → orderId
  │    ├─ batch insert 明細
  │    └─ 啟動 BPM 流程
  │
  ├─ 2. 更新 PUT /pmm/pur-order/update
  │    ├─ 檢查存在 + 未歸檔
  │    ├─ 更新明細（刪舊插新）
  │    ├─ updateById 單頭
  │    └─ 若首次歸檔 → generateForward
  │         ├─ SQL 跨表撈 head + details
  │         ├─ 幂等檢查（orderSignCode）
  │         ├─ insert forward 單頭 + 明細
  │         └─ 啟動結轉驗收 BPM
  │
  ├─ 3. 刪除 DELETE /pmm/pur-order/delete?id=
  │
  ├─ 4. 取單筆 GET /pmm/pur-order/get?id=
  │    └─ 主表 + 明細
  │
  ├─ 5. 分頁 GET /pmm/pur-order/page
  │    └─ 每筆補 mfrCode（N+1 風險）
  │
  ├─ 6. 待簽分頁 GET /pmm/pur-order/todo-page
  │
  ├─ 7. 取明細列表 GET /pmm/pur-order/pur-order-detail/list-by-pur-order-id?purOrderId=
  │
  └─ 8. 匯出 Excel GET /export-excel
```

---

## 6. 欄位規格

### 6.1 單頭（`pmm_pur_order`）

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| signCode | 單據編號 |
| purchaseDate | 採購日期 |
| subject | 主旨 |
| remark | 備註 |
| quoteSignCode | 對應的報價單號 |
| mfrId | 廠商 ID（指向報價維護表內部 ID） |
| mfrName | 廠商名稱 |
| untaxedAmount / taxAmount / totalAmount | 未稅 / 稅 / 稅後金額 |
| taxType | 計稅方式（0/1/2） |
| paymentId | 付款代碼 |
| cycle / cycleMultiplier / cycleDay | 付款週期 |
| deliveryCost | 運費 |
| processStatus | 流程狀態 |
| processInstanceId | BPM |

### 6.2 明細（`pmm_pur_order_detail`）

| 欄位 | 中文業務語 |
|---|---|
| purOrderId | 主表 ID |
| reqSignCode / reqItem | 請購單號 / 項次（追溯） |
| prodCode | 品號 |
| singleCountMeasure / singleCountUnit | 單一計數計量 / 單位 |
| purAmount / purAmountUnit | 採購計量 / 單位 |
| purQuantity / purQuantityUnit | 採購計數 / 單位 |
| purSingleCountMeasure / purSingleCountMeasureUnit | 採購單一計數計量 / 單位 |
| mfrUnit | 廠商單位 |
| unitPrice | 單價 |
| purQty | 採購數量（箱數） |
| lineAmount | 行金額 |
| requiredDate | 需求日期 |
| expectedDeliveryDate | 預定交期 |
| warehouse / warehouseName | 交貨地點 |
| remark | 備註 |

---

## 7. 商業邏輯

### 7.1 已歸檔保護

`processInstanceId 空且歸檔` → 拒絕

### 7.2 首次歸檔觸發 generateForward

雙層幂等：archivedBefore 檢查 + orderSignCode 查 forward 表

### 7.3 分頁補 mfrCode

對每筆查 vendor_quote_maintenance 取 mfrId 字串 → 寫入 RespVO.mfrCode

### 7.4 編輯子表

刪舊插新

---

## 8. 使用角色與權限

| 角色 | 可操作 | 對應權限字串 |
|---|---|---|
| 採購人員 | CRUD / 匯出 / 查詢 | `pmm:pur-order:create`、`update`、`delete`、`query`、`export` |
| 採購主管 | 待簽 + 簽核 | `query` + BPM |

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節。建議：

### 9.1 編輯頁

- 主表：單據編號（唯讀）、quoteSignCode（連結到 #32）、廠商（顯示 mfrCode + 名）、採購日期、計稅方式、付款代碼、運費、未稅 / 稅 / 稅後（建議唯讀，避免人工改錯）
- 明細表格：品號、廠商品名、採購數量（箱）、單價、行金額、預定交期、交貨地點
- 操作：儲存、送出簽核

### 9.2 分頁

- 條件：流程狀態、廠商、採購日期區間、quoteSignCode
- 表格：單據編號、廠商代號、廠商名、採購日期、稅後金額、流程狀態

---

## 10. 功能範圍

### 10.1 包含的功能

- 採購單 CRUD
- 已歸檔保護
- 歸檔自動產生結轉驗收單（雙層幂等）
- 分頁補 mfrCode
- BPM 流程整合
- 待簽分頁、Excel 匯出

### 10.2 預留但尚未實作 / 缺陷

- **mfrId 命名混亂**：實際是廠商報價維護的內部 ID，不是業界認知的「廠商代號」
- **N+1 查詢**：分頁時對每筆 select_by_id
- **金額編輯校驗**：使用者改 untaxedAmount 但不重算 tax/total
- **付款 / 週期欄位來源**：無自動帶入邏輯
- **必填驗證**：VO 無 `@NotNull`

### 10.3 不包含

- 請購單（#31）、報價單（#32）
- 結轉驗收（#34）、驗收確認（#35）
- 廠商主檔（#27）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| `mfrId` 實際是「廠商報價」的內部 ID，不是「廠商代號」 | 命名嚴重誤導 | `PurOrderServiceImpl.java:160` 查 vendorQuoteMapper |
| 分頁 N+1 查詢 | 大量資料時慢，應改為批次 IN | line 158-167 |
| 採購單金額是否允許人工修改？若可修改，應重算稅與行金額 | 程式無檢查 | updatePurOrder |
| 付款 / 週期欄位由何處帶入？ | #32 generateNewPurOrder 從 quoteDetailForOrderVO 帶 | 上游邏輯 |
| 已歸檔保護「processInstanceId 空且歸檔」陷阱 | 同 #31 / #32 | line 132 |
| 編輯刪舊插新導致明細 id 變動 | 影響 #34 跨表 reference？ | line 201-205 |
| `taxType` 是來自單頭欄位（複製自廠商主檔的 tax），若廠商主檔的 tax 變動，採購單上的 taxType 不會跟著變 | 設計需確認 | DO `taxType` |
| signCode 由 generateSignCode("採購單管理") 生成 | 規則需確認 | #32 自動產生時 line 232 |
| 採購單能否「重新發起 generateForward」？ | 無入口 | 業務需求 |
| 結轉驗收的 SQL 撈頭 / 明細（`generateForwardHead`、`generateForwardDetail`）邏輯複雜 | xml 未讀 | line 279-280 |
| 「採購單合併」業務需求 — 同廠商不同採購單能否合併？ | 程式無此邏輯 | 業務需求 |
| Controller Tag 寫「採購申請單」但業務名「採購單管理」 | 命名不一致 | Controller line 34 |
