# PRD｜採購管理 — 結轉驗收作業

> 來源：逆向自 `kingmaker-module-pmm` 後端程式碼（`controller/admin/purforward/`、`service/purforward/PurForwardServiceImpl.java`、`dal/dataobject/purforward/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **採購助理 / 驗收人員**。採購單（#33）核准歸檔後，系統自動產生「結轉驗收單」 — 這是「**廠商承諾出貨、但還沒到貨**」的中間單據。我負責：

> 「對每筆採購數量追蹤 — 已驗收多少、未驗收多少、在途多少；當廠商分批到貨時，記錄『本次驗收數量』；確認後送出生成『驗收確認單』（#35）給入庫；某些品項廠商不會再到貨可強制結案」

### 1.2 我要做什麼

- 檢視 / 編輯結轉驗收單（單頭 + 明細）
- 對每筆明細填入「本次驗收數量」（`inspectedQty`）
- 處理「強制結案」（廠商缺貨或不再供貨）
- 點「結轉驗收」按鈕 → 系統把當前的 `inspectedQty` 轉成「驗收確認單」（#35）
- 自動更新明細狀態（已關閉 / 驗收中 / 其他）
- 自動更新單頭狀態（全部關閉 → 單頭關閉）
- BPM 簽核流程
- 分頁查詢、待簽分頁、Excel 匯出

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 看到三量（採購 / 已驗 / 未驗 / 在途） | 廠商通常分批送貨，要追蹤每筆品項的進度 |
| 填本次驗收量送出 → 自動扣在途 / 增已驗 | 不要每次手動算 |
| 強制結案 | 廠商說某品項到不齊了，需要結案不再追 |
| 全部關閉 → 單頭自動關閉 | 不用人工再去改單頭 |
| 走簽核 | 驗收涉及金額確認 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 結轉驗收單 CRUD（單頭 + 明細） | 主要由 #33 歸檔自動建，但保留手動建立彈性 |
| 「結轉驗收」獨立端點 `/transformPurForwardToAcceptance` | 把本次驗收量轉為 #35 驗收確認單 |
| 三量自動扣減：在途 -= 本次、已驗 = 採購 - 在途 | 不必人工算 |
| 狀態自動更新：已關閉 / 驗收中 / 其他 | 業務狀態驅動 |
| 強制結案 | 不再追的處理 |
| BPM 流程整合 | 簽核 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 結轉驗收作業 |
| 所屬模組 | PMM（採購管理） |
| 兄弟功能 | 採購單 (#33)、驗收確認 (#35) |
| 主要頁面 | 結轉驗收編輯頁、單頭分頁、待簽分頁、結轉操作 |
| 簽核流程 | 有：`FormPathUniqueEnum.PUR_FORWARD` |
| 自動觸發下游 | 結轉操作建立 #35 驗收確認單；明細全結案時觸發 PUR_ACCEPTANCE 流程 |

---

## 2. 功能目的

結轉驗收是「**採購到貨的進度追蹤器**」：

1. **承接 #33 採購單** — `orderSignCode` 為對外鍵
2. **追蹤分批到貨** — 每筆明細記錄「採購量 / 已驗 / 未驗 / 在途 / 本次驗收」
3. **轉到 #35 驗收確認** — 由 `transformPurForwardToAcceptance` 將「本次驗收量」變成 #35 的單據
4. **強制結案** — 廠商缺貨時手動結束
5. **單頭關閉** — 所有明細關閉時自動關閉單頭

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `pmm_pur_forward`（單頭 / `PurForwardDO`） | 單據編號、廠商 ID/名、預定交期起訖、交貨地點、reqSignCode、orderSignCode（對外鍵）、processStatus、acceptanceStatus、attribute |
| `pmm_pur_forward_detail`（明細 / `PurForwardDetailDO`） | purForwardId、reqSignCode、orderSignCode、attribute、warehouse、prodCode、mfrUnit、purQty、approvedQty、unapprovedQty、transitQty、inspectedQty、forceClosed、forceClosedReason、acceptanceStatus |

### 3.2 五量關係

| 欄位 | 中文 | 說明 |
|---|---|---|
| purQty | 採購數量 | 從 #33 帶來，固定 |
| approvedQty | 已驗收數量 | 已收貨的累計 |
| unapprovedQty | 未驗收數量 | （顯示計算用，可能 = purQty - approvedQty - transitQty） |
| transitQty | 在途數量 | 廠商已出但未到 |
| inspectedQty | 本次驗收數量 | 使用者本次填寫 |

公式：

```
轉檔時：
  transitQty -= inspectedQty
  approvedQty = purQty - transitQty
  inspectedQty 清空為 0
```

驗收狀態：

| acceptanceStatus | 含義 | 觸發條件 |
|---|---|---|
| "0" | 其他 | purQty < approvedQty（不正常） |
| "1" | 驗收中 / 部分完成 | purQty > approvedQty |
| "2" | 已完成 / 已關閉 | purQty == approvedQty |

來源：`PurForwardServiceImpl.java:196-253`。

### 3.3 結轉操作 `transformPurForwardToAcceptance`

獨立端點，不是 update 流程的一部分。流程：

```
1. 查單頭、查明細
2. 建驗收確認單頭 PurAcceptanceDO：
   - signCode = generateSignCode("驗收確認作業")
   - mfrId / mfrName 從 forward 帶
   - forwardSignCode = forward 的 signCode（對外鍵）
   - acceptDate = now
   - subject = "由結轉驗收單生成 - " + forward.signCode
   - processStatus = "待處理"
3. 對每筆明細：
   - inspectedQty 為空或 <= 0 → 跳過建驗收確認明細，但仍更新 forward 明細的狀態
   - inspectedQty > 0 → 建 PurAcceptanceDetailDO：
     - purAcceptanceId、orderSignCode、prodCode、mfrUnit、mfrUnitName
     - inspectedQty = forward 的 inspectedQty
     - stockQty = inspectedQty（入庫量預設 = 驗收量）
     - shortageQty = 0
     - warehouseId（由 selectWarehouseIdByProdCode 查）
   - 更新 forward 明細：
     - transitQty -= inspectedQty
     - approvedQty = purQty - transitQty
     - inspectedQty 清空 = 0
     - acceptanceStatus 根據 purQty vs approvedQty 設定
4. batch insert 驗收確認明細
5. batch update forward 明細
6. 若所有明細 closedAcceptStatus == 全部 → forward 單頭 acceptanceStatus="2"
7. 啟動 PUR_ACCEPTANCE BPM 流程
```

來源：`PurForwardServiceImpl.java:152-283`。

### 3.4 已歸檔保護

同 #31–#33：`processInstanceId 空且歸檔` → 拒絕修改。

### 3.5 強制結案邏輯（在 update 時）

`updatePurForwardDetailList`：對每筆明細檢查 `forceClosed`：

- "1" → 累加 allForceClosed
- 若 `allForceClosed > 0 && allForceClosed == list.size()` → 整批都強制結案 → 單頭 acceptanceStatus="2"

意義：所有明細都強制結案時，單頭也關閉。

⚠️ 但這個條件用 `allForceClosed > 0 && allForceClosed.equals(list.size())` — 用 `Integer.equals`，可能有自動裝箱問題（小 int 共享，大 int 不共享）。線上實際 Integer 由累加得來，建議用基本型別 ==（見 §11）。

來源：`PurForwardServiceImpl.java:302-318`。

### 3.6 缺陷：第一個分支也走 updateDetailList

`transformPurForwardToAcceptance` 第一個 if 分支：「沒有本次驗收數量但仍要更新狀態」，邏輯只有：

```java
if (purQty.compareTo(approvedQty) == 0) → "2"
else if (purQty.compareTo(approvedQty) > 0) → "1"
else → "0"
```

但此分支理論上不需要狀態變化（因為沒填驗收量），仍會強行設定狀態。會把舊狀態覆寫 — 雖然結果通常一樣，但語意上是 noop（見 §11）。

### 3.7 Excel 匯出顯然壞掉

`exportPurForwardExcel`：

```java
// List<PurForwardDO> list = purForwardService.getPurForwardPage(pageReqVO).getList();
List<PurForwardDO> list = new ArrayList<>();   ⚠️
```

匯出端永遠寫出空 list（來源：`PurForwardController.java:107-108`）。屬於明確 bug。

### 3.8 跨模組依賴

- `PurAcceptanceMapper` / `PurAcceptanceDetailMapper`（#35）：建驗收單
- `selectWarehouseIdByProdCode`：跨表查倉庫 ID
- BPM：`PUR_FORWARD` + `PUR_ACCEPTANCE`

---

## 4. 情境說明

### 4.1 正常流程 — 第一批到貨驗收

廠商「冷凍肉商」承諾 4 箱牛肉餅，第一次到貨 2 箱：

1. 採購助理進入結轉驗收編輯頁
2. 對該明細填 inspectedQty=2
3. 點「結轉驗收」 → transformPurForwardToAcceptance
4. 系統：
   - 建驗收確認單頭（PA-2026-001）
   - 建明細：inspectedQty=2、stockQty=2、shortageQty=0
   - 更新 forward 明細：transitQty 從 4 → 2、approvedQty 從 0 → 2、inspectedQty=0
   - acceptanceStatus：purQty(4) > approvedQty(2) → "1"（驗收中）
5. 驗收人員在 #35 看到 PA-2026-001 待處理

### 4.2 典型業務 — 第二批到貨完成

第二批到貨 2 箱：

- 填 inspectedQty=2 → 結轉
- transitQty 從 2 → 0、approvedQty 從 2 → 4、inspectedQty=0
- acceptanceStatus：purQty(4) == approvedQty(4) → "2"（已關閉）
- closedAcceptStatus++ → 若全部 detail 都關閉 → 單頭 acceptanceStatus="2"

### 4.3 強制結案

廠商告知無法供貨剩 1 箱：

- 編輯該明細，forceClosed="1"
- 儲存（update）
- updateDetailList：allForceClosed++
- 若所有明細都強制結案 → 單頭 acceptanceStatus="2"

### 4.4 異常情境 — 過量驗收

廠商實際到貨 5 箱（多送 1 箱）：

- 填 inspectedQty=5 → 結轉
- transitQty 從 4 → -1（負值！）
- approvedQty = purQty(4) - (-1) = 5
- acceptanceStatus：purQty(4) < approvedQty(5) → "0"

⚠️ 程式無檢查 inspectedQty > transitQty 的情況，會產生負在途與 status "0"（業務含義不明）。

### 4.5 規則分流 — Excel 匯出空白

點匯出 → 拿到空 Excel（明確 bug）。

---

## 5. 操作流程

```
[#33 採購單歸檔]
  └─ 自動建立結轉驗收單（PUR_FORWARD 流程啟動）

[採購助理進入「結轉驗收作業」]
  │
  ├─ 1. 建立 POST /pmm/pur-forward/create
  │
  ├─ 2. 更新 PUT /pmm/pur-forward/update
  │    ├─ 檢查存在 + 未歸檔
  │    ├─ updateById 單頭
  │    └─ 更新明細（刪舊插新）
  │         └─ 若全部強制結案 → 單頭 acceptanceStatus="2"
  │
  ├─ 3. 結轉操作 PUT /pmm/pur-forward/transformPurForwardToAcceptance?id=
  │    ├─ 建驗收確認單頭（forwardSignCode 對外鍵）
  │    ├─ 對每筆明細：
  │    │   ├─ inspectedQty <= 0 → 只更狀態
  │    │   └─ inspectedQty > 0 → 建驗收明細 + 更新 forward 明細
  │    ├─ batch insert + batch update
  │    ├─ 若全部關閉 → forward 單頭 acceptanceStatus="2"
  │    └─ 啟動 PUR_ACCEPTANCE 流程
  │
  ├─ 4. 刪除 DELETE /delete?id=
  │
  ├─ 5. 取單筆 GET /get?id=
  │    └─ purForwardHead + purForwardDetail list
  │
  ├─ 6. 分頁 / 待簽分頁 GET /page、/todo-page
  │
  ├─ 7. 取明細列表 GET /pur-forward-detail/list-by-pur-forward-id?purForwardId=
  │
  └─ 8. 匯出 Excel GET /export-excel ⚠️ 永遠空 list
```

---

## 6. 欄位規格

### 6.1 單頭（`pmm_pur_forward`）

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| signCode | 單據編號 |
| mfrId / mfrName | 廠商 ID / 名稱 |
| expectedStartDate / expectedEndDate | 預定交期起訖 |
| warehouse / warehouseName | 交貨地點 |
| reqSignCode | 請購單號 |
| orderSignCode | 採購單號（對外鍵） |
| processStatus | BPM 狀態 |
| processInstanceId | BPM 實例 |
| acceptanceStatus | 業務狀態（"2"=已關閉） |
| attribute | 屬性（未文件化） |

### 6.2 明細（`pmm_pur_forward_detail`）

| 欄位 | 中文業務語 |
|---|---|
| purForwardId | 主表 ID |
| reqSignCode / orderSignCode | 追溯 |
| warehouse / warehouseName | 交貨地點 |
| prodCode | 品號 |
| mfrUnit / mfrUnitName | 廠商單位 |
| purQty | 採購數量（從 #33 帶） |
| approvedQty | 已驗收數量 |
| unapprovedQty | 未驗收數量 |
| transitQty | 在途數量 |
| inspectedQty | 本次驗收數量（人工填） |
| forceClosed / forceClosedReason | 強制結案 + 理由 |
| acceptanceStatus | 0/1/2 |

---

## 7. 商業邏輯

### 7.1 結轉公式

```
transitQty -= inspectedQty
approvedQty = purQty - transitQty
inspectedQty = 0
```

### 7.2 狀態驅動

```
purQty == approvedQty → "2" 已關閉
purQty >  approvedQty → "1" 驗收中
purQty <  approvedQty → "0" 其他
```

### 7.3 強制結案

update 時若整批 forceClosed="1" → 單頭 acceptanceStatus="2"

### 7.4 已歸檔保護

`processInstanceId 空且歸檔` → 拒絕

---

## 8. 使用角色與權限

| 角色 | 可操作 | 對應權限字串 |
|---|---|---|
| 採購助理 / 驗收人員 | CRUD / 結轉 / 查詢 / 匯出 | `pmm:pur-forward:create`、`update`、`delete`、`query`、`export` |
| 簽核主管 | 待簽 + 簽核 | `query` + BPM |

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節。建議：

### 9.1 編輯頁

- 主表：單據編號、廠商、交貨地點、orderSignCode 連結到 #33
- 明細表格：品號、採購量、已驗、未驗、在途、本次驗收（input）、強制結案（switch + 理由）、狀態（顯示中文）
- 「結轉驗收」按鈕：彙整所有 inspectedQty 送出

### 9.2 分頁

- 條件：流程狀態、acceptanceStatus、orderSignCode
- 表格：單據編號、廠商、orderSignCode、預定交期、acceptanceStatus

---

## 10. 功能範圍

### 10.1 包含的功能

- 結轉驗收 CRUD
- 三量管理 + 本次驗收
- 強制結案
- 結轉操作（轉 #35）
- 自動狀態更新
- BPM 流程整合

### 10.2 缺陷

- **Excel 匯出永遠回空**（line 108）
- **過量驗收**（inspectedQty > transitQty）造成負值，無檢查
- **「沒填驗收量但更新狀態」分支**邏輯多餘
- **Integer.equals** 自動裝箱問題（雖然累加 Integer 不會出問題，但寫法不嚴謹）
- **已歸檔保護**同陷阱

### 10.3 不包含

- 採購單（#33）
- 驗收確認（#35，由本功能生成）
- 入庫（屬於 WHS #40）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| Excel 匯出 hardcode 空 list — bug | line 108 註解了真實邏輯 | Controller line 107-108 |
| 過量驗收的處理規則？inspectedQty > transitQty 會產生負值 | 業務需確認 | line 241-242 |
| 「沒填驗收量但更新狀態」分支多餘 | line 191-208 與後續邏輯重複 | line 191-209 |
| `allForceClosed.equals(list.size())` 用 Integer.equals | 寫法不嚴謹（用 int == 即可） | line 313 |
| acceptanceStatus 狀態的字面值未 enum 化 | "0" / "1" / "2" 字面 | 多處 |
| `attribute` 欄位用途未文件化 | DO 上有但業務語意不明 | DO `attribute` |
| `transitQty` 的初始值來源？從 #33 帶 purQty 嗎？ | 程式未明確列出 | 上游邏輯 |
| 已歸檔保護同 #31/#32/#33 陷阱 | line 115 |
| 「結轉操作」會驗證該單是否歸檔嗎？ | `transformPurForwardToAcceptance` 沒檢查 | line 152-283 |
| 同一張 PurForward 可重複「結轉」嗎？ | 程式允許多次呼叫，每次建一張新驗收確認單 | line 152 |
| 「驗收確認單號 = 由結轉驗收單生成 - {signCode}」中文主旨 | i18n 風險 | line 174 |
| `selectWarehouseIdByProdCode` 邏輯複雜 | xml 未讀 | line 216 |
| 編輯刪舊插新會丟失既有的 approvedQty/transitQty 累計值（如果使用者誤改） | 業務風險 | line 302-318 |
| `acceptanceStatus="2"` 與 BPM `processStatus="已歸檔"` 兩個關閉狀態是否該同步？ | 兩維度狀態 | DO + BPM |
