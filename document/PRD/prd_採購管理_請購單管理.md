# PRD｜採購管理 — 請購單管理

> 來源：逆向自 `kingmaker-module-pmm` 後端程式碼（`controller/admin/purreq/PurReqController.java`、`service/purreq/PurReqServiceImpl.java`、`dal/dataobject/purreq/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **採購人員 / 採購助理 / 店長**。當需求預測（#24 / #25）或行事曆（#30）顯示某品號需要補貨，我會建一張「請購單」：

> 「2026-05-25 北一區 1 號店要進牛肉餅 LB-04 50 公斤、起司片 PKG-CHEESE 30 包；交貨地點 北一倉；加權係數 1.10；需求原因『預測量加 10%』」

請購單送出後走簽核，**核准（已歸檔）後系統自動產生對應的報價單**（PRD #32），由採購進入下一步詢價 / 比價。

### 1.2 我要做什麼

- 建立請購單（單頭 + 多筆品號明細）
- 系統根據品號 + 倉庫查當前庫存量 / 安全存量，並用加權係數試算「請購計數」
- 編輯、刪除請購單
- 分頁查詢、待簽分頁、單筆查詢（含明細）
- 取單筆庫存資訊（依品號 + 倉庫）
- 取某品號的所有倉庫庫存明細（小工具）
- 簽核流程驅動（待處理 → 待簽核 → 已歸檔）
- **歸檔瞬間自動產生報價單**（幂等保護）

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 看到品號當前庫存 / 安全存量 | 不能憑空填數量；要看「現在還有多少 / 安全水位多少」 |
| 自動算建議請購量 | (安全存量 - 當前) × 加權係數，避免人工算錯 |
| 走簽核 | 採購支出需審核 |
| 已歸檔不能改 | 否則 audit 與下游報價會錯亂 |
| 歸檔後自動產生報價單 | 不要採購助理再手動「依請購單建報價單」 |
| 簽核不能重複生成報價單 | 幂等：同請購單最多一張報價單 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 請購單 CRUD（單頭 + 明細） | 一站式建單 |
| 即時取庫存試算 | 給編輯頁的「自動計算建議量」 |
| 跨倉庫查同品號 | 助理可以看「全公司哪裡有貨」決定要不要請購 |
| BPM 流程整合 | 簽核 |
| 已歸檔保護 | 鎖定定案 |
| 歸檔自動生成報價單（幂等） | 銜接 #32 |
| 待簽分頁 | 主管處理 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 請購單管理 |
| 所屬模組 | PMM（採購管理） |
| 兄弟功能 | 廠商資料 (#27)、廠商報價 (#28)、原料物需求行事曆 (#30)、報價管理 (#32)、採購單管理 (#33)、結轉驗收 (#34)、驗收確認 (#35) |
| 主要頁面 | 請購單編輯頁（含庫存試算）、單頭分頁、待簽分頁 |
| 簽核流程 | 有：`FormPathUniqueEnum.PURCHASE_REQUISITION` |
| 自動觸發下游 | 歸檔瞬間建立 #32 報價單（幂等） |

---

## 2. 功能目的

請購單是「**需求方（店 / 區）→ 採購方**」的正式內部請款，扮演：

1. **採購支出的入口** — 所有採購活動都應從請購單發起，避免拍腦袋下單
2. **庫存試算** — 編輯時即時看當前庫存 + 安全存量，自動算建議請購量
3. **簽核管控** — 透過 BPM 流程，主管核准後才能進入報價
4. **自動銜接報價** — 歸檔自動建立報價單（同 signCode 為對外鍵），減少人工轉錄

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `pmm_pur_req`（單頭 / `PurReqDO`） | 單據編號、請購原因、交貨地點代號 / 名稱、需求日期、主旨、加權係數、流程狀態、流程實例 ID |
| `pmm_pur_req_detail`（明細 / `PurReqDetailDO`） | purReqId、品號（食材）、目前庫存量、安全存量、請購計數、單位、需求備註、倉庫 ID |

### 3.2 加權係數與請購計數

`getStockCurrentPage` 取庫存後，公式：

```
建議請購計數 = (安全存量 - 目前庫存量) × 加權係數
```

- 加權係數來自 `StockCurrentPageReqVO.weightFactor`（單頭傳入）
- 結果寫入 `standardQuantity`
- 任一欄位為 null → 不算（保持空）

來源：`PurReqServiceImpl.java:297-304`。

⚠️ **數值可能為負**：若當前庫存高於安全存量，公式會給負值。程式無檢查（見 §11）。

### 3.3 已歸檔保護的奇特邏輯

`validatePurReqExists`：

```java
if (StrUtil.isEmpty(purReqDO.getProcessInstanceId())
    && ARCHIVED.equals(purReqDO.getProcessStatus())) {
    throw exception(PUR_ARCHIVED_CANNOT_UPDATE);
}
```

判斷 `processInstanceId 為空 **且** 已歸檔` → 拒絕修改。**有 processInstanceId 的歸檔不被擋** — 與 #26 臨時需求審核設計相同（也有同樣陷阱，見該 PRD §11）。

### 3.4 歸檔瞬間自動產生報價單

`updatePurReq`：

```
1. validatePurReqExists 取舊單
2. 更新明細（刪舊插新）
3. updateById
4. 若 archivedNow = true 且 archivedBefore = false → 觸發 createQuoteFromPurReq
```

`createQuoteFromPurReq`：

```
1. 取請購單
2. 幂等：用 signCode 查 quote 表是否已存在 → 有則 return
3. 取請購明細
4. 建立 QuoteDO：
   - signCode = generateSignCode("報價管理")
   - reqSignCode = 請購單號（對外鍵）
   - status = "1"
   - processStatus = 待處理
5. 對每筆明細建 QuoteDetailDO：
   - reqItem = 流水號 1, 2, 3...
   - reqSignCode = 請購單號
   - 帶入 standardQuantity / totalStandardQuantity / remark
6. batch insert
7. 啟動報價單流程
```

關鍵：**僅在「首次轉成已歸檔」瞬間觸發**（`archivedNow && !archivedBefore`） — 重複歸檔不會重複建。

來源：`PurReqServiceImpl.java:108-182`。

### 3.5 庫存試算的小工具

兩個查詢端點：

- `GET /stock-current-page`：依「品號 + 倉庫」查當前庫存 + 安全存量；填入加權係數可同時試算建議量
- `GET /stock-list-by-prod-code`：依「品號」查所有倉庫的庫存明細

實際 SQL 查 `purReqDetailMapper.selectStockCurrentPage` / `selectStockListByProdCode`（跨模組依賴 WHS 倉儲表）。

### 3.6 編輯子表的策略

`updatePurReqDetailList`：刪舊插新（與 #27 / #28 一致）。

### 3.7 待簽分頁的彈性

`getToDoPurReqPageByFlow` 在 `processInstanceStatus` 為空時，會根據 `processStatus` 推斷：

- 若 processStatus = "全部" → processInstanceStatus = null
- 否則 → processInstanceStatus = processStatus

代表前端可以單獨傳 `processStatus` 來過濾「我的待簽 + 特定狀態」。

### 3.8 跨模組依賴

| 依賴 | 用途 |
|---|---|
| `IngredientSpecsMapper`（PDM） | 取食材名稱（雖然 getPurReqWithDetails 已用 SQL join 不再呼叫，但程式碼仍有 import） |
| `WarehouseService`（WHS） | 取交貨地點 / 倉庫資訊（雖然 `getWarehouseIdByZoneName` 邏輯似乎被棄用） |
| `QuoteMapper` / `QuoteDetailMapper`（PMM 內） | 歸檔時自動建立報價單 |
| `MenuFlowProcessInstanceHelper`、`MenuService` | BPM 流程 |

---

## 4. 情境說明

### 4.1 正常流程 — 店長建請購單

店長小王在 5/20 進入請購單管理，要為下週備料建單：

1. 主表：
   - 請購原因：依預測量補貨
   - 交貨地點：北一倉（warehouse code）
   - 需求日期：2026-05-25
   - 主旨：信義店 5/25 補貨
   - 加權係數：1.10
2. 明細加入「牛肉餅 LB-04」：
   - 點該行「載入庫存」按鈕 → GET /stock-current-page?prodCode=LB-04&warehouse=北一倉&weightFactor=1.10
   - 系統回：當前 30 公斤、安全存量 50 公斤、(50-30)×1.10 = 22.00 公斤
   - 寫入 standardQuantity 欄位
3. 加更多品號…
4. POST /create
5. 系統：
   - signCode = generateSignCode("請購單管理")
   - processStatus = 「待處理」
   - insert 單頭、批次 insert 明細
   - 啟動 BPM 流程
6. 進主管待簽

### 4.2 典型業務 — 主管核准 → 自動建報價單

採購主管在「待簽分頁」看到該請購單，核准後 BPM 推進狀態：

- 流程節點呼叫 PUT /update（processStatus="已歸檔"）
- service：archivedNow=true, archivedBefore=false → 觸發 createQuoteFromPurReq
- 建立報價單（同 reqSignCode），啟動報價單 BPM 流程
- 採購進入 #32 詢價

### 4.3 異常情境 — 庫存查不到

某新品號在倉庫表還沒有記錄。GET /stock-current-page 回 null → 回 PurReqDetailVO with prodCode=null（**不拋錯**，靜默回空物件）。

⚠️ 使用者無法分辨「品號不存在」與「品號在該倉庫沒庫存」（見 §11）。

### 4.4 規則分流 — 庫存高於安全存量

「果汁 PKG-J01」當前庫存 100，安全存量 30：

- 公式：(30 - 100) × 1.10 = -77.00
- 寫入 standardQuantity = -77.00
- 負值意義不明，前端應顯示警示或修正為 0（見 §11）

### 4.5 異常情境 — 編輯已歸檔且 processInstanceId 空

某請購單已歸檔但無 processInstanceId（推測為「未啟用 BPM 流程」場景）：

- validatePurReqExists 拋 `PUR_ARCHIVED_CANNOT_UPDATE`

若 processInstanceId 非空且已歸檔 → 仍允許編輯（可能不合理，見 §11）。

### 4.6 規則分流 — 重複歸檔

BPM 流程節點意外二次觸發 `processStatus = 已歸檔` 的 update：

- archivedBefore=true → 不再呼叫 createQuoteFromPurReq
- 保護幂等

即使第一道幂等失效，createQuoteFromPurReq 內也用 `QuoteDO::getReqSignCode` 二次檢查。

---

## 5. 操作流程

```
[使用者進入「請購單管理」]
  │
  ├─ 1. 建立 POST /pmm/pur-req/create
  │    ├─ 權限：pmm:pur-req:create
  │    ├─ signCode + processStatus 系統填
  │    ├─ insert 單頭 → purReqId
  │    ├─ batch insert 明細
  │    └─ 啟動 BPM 流程
  │
  ├─ 2. 更新 PUT /pmm/pur-req/update
  │    ├─ 權限：pmm:pur-req:update
  │    ├─ 檢查存在 + 未歸檔 (processInstanceId 空且歸檔則擋)
  │    ├─ 更新明細（刪舊插新）
  │    ├─ updateById 單頭
  │    └─ 若首次歸檔 → createQuoteFromPurReq
  │         ├─ 幂等檢查（reqSignCode 是否已有 quote）
  │         ├─ 建立報價單頭
  │         ├─ 批次建立報價單明細
  │         └─ 啟動報價單 BPM 流程
  │
  ├─ 3. 刪除 DELETE /pmm/pur-req/delete?id=
  │    ├─ 檢查存在
  │    ├─ 軟刪除單頭
  │    └─ 軟刪除明細
  │
  ├─ 4. 取單筆 GET /pmm/pur-req/get?id=
  │    └─ 主表 + 明細（含食材名稱 join）
  │
  ├─ 5. 分頁 / 待簽分頁 GET /page、/todo-page
  │    └─ 待簽分頁含 processInstanceStatus 推斷邏輯
  │
  ├─ 6. 取明細列表 GET /pmm/pur-req/pur-req-detail/list-by-pur-req-id?purReqId=
  │
  ├─ 7. 取庫存試算 GET /pmm/pur-req/stock-current-page?prodCode=&warehouse=&weightFactor=
  │    └─ 回 PurReqDetailVO（含當前庫存、安全存量、試算的請購計數）
  │
  └─ 8. 取多倉庫庫存 GET /pmm/pur-req/stock-list-by-prod-code?prodCode=
       └─ 回所有倉庫的庫存明細
```

---

## 6. 欄位規格

### 6.1 單頭（`pmm_pur_req`）

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| signCode | 單據編號 |
| reqReason | 請購原因 |
| warehouse / warehouseName | 交貨地點代號 / 名稱 |
| reqDate | 需求日期 |
| subject | 主旨 |
| weightFactor | 加權係數（字串） |
| processStatus | 流程狀態 |
| processInstanceId | 流程實例 ID |

### 6.2 明細（`pmm_pur_req_detail`）

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| purReqId | 主表 ID |
| prodCode | 品號（食材） |
| currentStockNum | 目前庫存量 |
| safeStock | 安全存量 |
| standardQuantity | 請購計數 |
| unit | 單位 ID |
| remark | 需求備註 |
| warehouseId | 倉庫表 ID |

### 6.3 庫存試算回傳（`PurReqDetailVO`）

含：prodCode、currentStockNum、safeStock、unitName、singleSpec、singleSpecUnitName、standardQuantity（試算結果）。

### 6.4 驗證規則

- VO 上**無 `@NotNull` / `@NotEmpty`**，後端不強制必填
- 必填靠前端 / Service 內個別檢查（validatePurReqExists 只查存在 + 歸檔）

---

## 7. 商業邏輯

### 7.1 建立 / 更新

略，見 §3.4、§4.1。

### 7.2 庫存試算公式

```
建議請購計數 = (安全存量 - 當前庫存量) × 加權係數
任一參數 null → 不寫入（保持空）
```

### 7.3 歸檔自動建報價單（雙層幂等）

- 第一層：archivedBefore 檢查 — 防止重複歸檔事件觸發
- 第二層：createQuoteFromPurReq 內查 quote.reqSignCode — 防止繞過第一層的呼叫

### 7.4 待簽分頁的 processInstanceStatus 推斷

- 前端傳 processStatus="全部" → 過濾條件設為 null
- 前端傳 processStatus="待簽核" → 過濾條件設為 "待簽核"
- 前端只傳 processInstanceStatus → 直接用

---

## 8. 使用角色與權限

| 角色 | 可操作 | 對應權限字串 |
|---|---|---|
| 店長 / 採購助理 | 建立 / 編輯 / 刪除 / 查詢 | `pmm:pur-req:create`、`update`、`delete`、`query` |
| 採購主管 | 待簽分頁 + 簽核 | `query` + BPM 角色 |

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節。建議：

### 9.1 編輯頁

- 主表：請購原因、交貨地點下拉（來源 WHS 倉庫）、需求日期、主旨、加權係數（數字 1.0–2.0 常見）
- 明細表格：每行品號 + 「載入庫存」按鈕、當前 / 安全存量顯示、建議請購計數（自動算）、可人工修改、單位、備註
- 「跨倉查庫存」工具按鈕（呼叫 stock-list-by-prod-code）

### 9.2 分頁

- 條件：流程狀態、單據編號、需求日期區間、建立時間
- 表格：單據編號、主旨、交貨地點、需求日期、加權係數、狀態、建立人 / 時間、操作

---

## 10. 功能範圍

### 10.1 包含的功能

- 請購單 CRUD（單頭 + 明細）
- 庫存試算 API（即時查 + 自動算建議量）
- BPM 流程整合
- 已歸檔保護
- 歸檔瞬間自動產生報價單（雙層幂等）
- 待簽分頁的 status 推斷

### 10.2 預留但尚未實作

- **建議量負值處理**：(safe - current) × factor 可為負，無校正
- **品號不存在 vs 庫存為 0** 的提示分流：均回空物件
- **必填驗證**：VO 完全沒 `@NotNull`
- **getWarehouseIdByZoneName** 似被棄用（呼叫被註解）

### 10.3 不包含

- 報價管理 / 詢價（屬於 #32，由本功能歸檔自動建立）
- 採購單 / 下單（屬於 #33）
- 驗收（屬於 #34 / #35）
- 倉庫主檔（屬於 WHS）
- 食材主檔（屬於 PDM）
- 安全存量本身的設定（屬於 #36 / #37）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| 已歸檔保護條件「processInstanceId 空且歸檔」是否合理？ | 有流程實例的歸檔反而不被擋（同 #26 陷阱） | `PurReqServiceImpl.java:201-203` |
| 庫存查不到時靜默回空，使用者無法分辨原因 | 應分流「品號不存在」「該倉無庫存」 | line 273-278 |
| 建議請購量可為負值 | (safe - current) × factor < 0 沒檢查 | line 297-304 |
| 加權係數 weightFactor 為字串但用 BigDecimal 計算 | 型別不一致 | DO 字串 vs Service 用 BigDecimal |
| VO 無任何必填 | 易產生髒資料 | PurReqSaveReqVO 無 @NotNull |
| 編輯刪舊插新導致明細 id 變動 | 同 #27 / #28 | line 251-256 |
| `getWarehouseIdByZoneName` 邏輯似乎被棄用（呼叫已註解） | 死代碼 | line 309-327 |
| `getPurReq` 方法回單頭但對明細只是查出來不放回 | 註解寫「需要在Controller層組裝到RespVO中」，但實際上 Controller 用的是 getPurReqWithDetails — 此方法是死代碼 | line 207-216 |
| 「總標準量」(`totalStandardQuantity`) 在 quote 明細與 `standardQuantity` 相同 | 兩個欄位的差異未文件化 | line 164、166 |
| 重複歸檔的幂等檢查（兩層）— 是否需要記錄「跳過的歸檔事件」？ | 操作 audit 不完整 | line 108-112、129-133 |
| 「請購計數」`standardQuantity` 的 scale 與 RoundingMode 未統一 | 公式直接 multiply 不設 scale | line 300-302 |
| 跨倉庫查 prodCode 是否該限制使用者權限（區域 / 門店）？ | 目前無過濾 | `getStockListByProdCode` |
| signCode 是用「請購單管理」生成的 `generateSignCode` 規則 | 規格 / 前綴需確認 | line 68 |
| 自動產生報價單時 status="1" 是「啟用」？ — 字面字串 | 字典 / enum 化 | line 169 |
| 編輯時若改了交貨地點，當初基於該倉的庫存試算數據是否同步刷新？ | 程式無自動重算 | 業務邏輯 |
| `materialProductId` / `storeCode` 等明細 VO 上的欄位是否真有用？ | 與請購業務看似無關 | RawMaterialDemandIngredientDetailVO（被 join 過來） |
