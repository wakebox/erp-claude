# PRD｜採購管理 — 報價管理

> 來源：逆向自 `kingmaker-module-pmm` 後端程式碼（`controller/admin/quote/QuoteController.java`、`service/quote/QuoteServiceImpl.java`、`dal/dataobject/quote/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **採購人員**。請購單（#31）核准後，系統會自動產生一張對應的「報價單」（同 `reqSignCode`）。我接著要：

> 「依每筆品號的需求量，從廠商報價維護（#28）中挑選最適合的廠商（價格、配送、MOQ）→ 設定『預設廠商』→ 送簽核 → 歸檔時系統自動產生採購單（依廠商分群）」

「報價管理」是請購 → 採購之間的**比價 / 選廠商**橋樑。

### 1.2 我要做什麼

- 建立報價單（多為系統自動建，但 Controller 也接受手動建）
- 編輯報價單（單頭 + 明細）
  - 為每筆明細指定「預設廠商」（`defaultSupplier`）
  - 帶入「最新報價(NTD/包裝)」「最新報價(NTD/單位)」
- 刪除報價單
- 走簽核流程
- **歸檔瞬間**：
  - 把明細的 status 改為 "2"（採購中）
  - 按廠商分群，**自動產生採購單**（一個廠商一張採購單）
  - 計算未稅金額、稅額、稅後金額（依廠商計稅方式）
  - 啟動每張採購單的 BPM 流程
- 分頁查詢、待簽分頁、單筆查詢（含明細）
- 取某品號的歷史採購記錄（給選廠商時參考）
- 匯出 Excel

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 從多家廠商挑一家 | 同一品號常有 2–5 家廠商報價，要比價 |
| 看品號的歷史採購記錄 | 上次跟誰買的、價格多少、品質如何（隱含） |
| 必須選定預設廠商才能歸檔 | 否則下游採購單無法建立 |
| 按廠商分群建採購單 | 每家廠商一張，方便分別下單 |
| 自動算稅 | 不同廠商計稅方式不同（營業稅 5% / 零稅 / 免稅） |
| 採購量按單一包裝量無條件進位 | 廠商只接受「整箱」訂單 |
| 已歸檔不能改 | 防止 audit 損壞 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 報價單 CRUD（單頭 + 明細） | 主要由 #31 自動建，但保留手動建立彈性 |
| 預設廠商必填校驗（歸檔時） | 沒選廠商不能歸檔 |
| 歷史採購記錄查詢 API | 比價輔助 |
| 歸檔瞬間自動：按廠商分群建採購單、算稅、啟動採購流程 | 一鍵把比價結果落地 |
| 採購量整箱進位 | `purQuantity / singlePackCount` HALF_UP 0 位小數，**ROUND_UP** |
| 簽核流程整合 | BPM |
| 已歸檔保護 | 鎖定 |
| 待簽分頁 | 主管處理 |
| Excel 匯出 | 對照 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 報價管理（程式碼 Tag「請採報價管理」） |
| 所屬模組 | PMM（採購管理） |
| 兄弟功能 | 請購單管理 (#31)、採購單管理 (#33)、廠商報價維護 (#28)、廠商資料 (#27) |
| 主要頁面 | 報價編輯頁、單頭分頁、待簽分頁、歷史採購記錄查詢 |
| 簽核流程 | 有：`FormPathUniqueEnum.QUOTATION`（注意：建立時用 `PURCHASE_REQUISITION` — 疑似 bug，見 §11） |
| 自動觸發下游 | 歸檔時按廠商分群建立 #33 採購單 |

---

## 2. 功能目的

報價管理是 PMM 流程的**比價樞紐**：

1. **承接 #31 請購單** — `reqSignCode` 為對外鍵
2. **比價 + 選廠商** — 每筆品號從多家廠商報價中挑一家為 `defaultSupplier`
3. **依廠商分群下單** — 同一張報價單可能會產生多張採購單（一廠一張）
4. **整箱進位** — 廠商配送以箱為單位，計算採購量時無條件進位
5. **稅額自動計算** — 依廠商計稅方式（0/1/2）

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `pmm_quote`（單頭 / `QuoteDO`） | 單據編號、請購原因（從 #31 複製）、交貨地點、需求日期、`reqSignCode`（請購單號）、status（報價中=1 / 採購中=2）、processStatus、流程實例 ID |
| `pmm_quote_detail`（明細 / `QuoteDetailDO`） | quoteId、prodCode、請購量 standardQuantity、總採購計數 totalStandardQuantity、status、`defaultSupplier`（廠商主表 ID）、最新報價(NTD/包裝)、最新報價(NTD/單位)、請購項次 reqItem、`reqSignCode` |

### 3.2 status vs processStatus 雙狀態

兩個欄位語意不同：

| status | 業務含義 |
|---|---|
| "1" | 報價中（建立預設） |
| "2" | 採購中（歸檔後自動切換） |

| processStatus | BPM 流程含義 |
|---|---|
| 待處理 / 待簽核 / 已歸檔 | 流程節點驅動 |

歸檔瞬間（processStatus="已歸檔"）系統會把 status 改為 "2"（單頭 + 所有明細）。

### 3.3 歸檔的雙重驗證

`updateQuote` 在 processStatus="已歸檔" 時：

1. `validateQuoteDetailList`：每筆明細的 `defaultSupplier` 不可為 null → 否則拋 `QUOTE_DEFAULT_NOT_EXISTS`
2. 通過後才更新

意義：**沒選預設廠商不能歸檔**。

### 3.4 歸檔瞬間生成採購單（按廠商分群）

`generateNewPurOrder(quoteId)`：

```
1. selectQuoteDetailForOrderNewList(quoteId)
   ← join 廠商報價 + 廠商資料 + 請購單，取每筆明細 + mfrId + singlePackCount + unitPrice + taxType + requiredDate
2. 依 mfrId groupBy
3. 對每組（同廠商）：
   a. 建採購單頭 PurOrderDO
      - signCode = generateSignCode("採購單管理")
      - 從 quoteDetailForOrderVO 帶入 taxType / mfrId / warehouse 等
   b. 對每明細：
      - 採購量 purQty = ceil(purQuantity / singlePackCount)   ← 無條件進位
      - 行金額 lineAmount = purQty × unitPrice (scale=3 HALF_UP)
      - 累計 untaxedAmount
   c. batch insert 明細
   d. 計算稅：
      - taxType="0"（營業稅） → totalAmount = untaxed × 1.05
      - 其他 → totalAmount = untaxedAmount
      - taxAmount = total - untaxed
   e. updateById 採購單頭（含金額）
   f. 啟動採購單 BPM 流程
```

**注意**：

- `untaxedAmount × new BigDecimal(1.05)` 用 double 建構 BigDecimal — 會有浮點精度問題（見 §11）
- `taxAmount = total - untaxed` 用減法回推，而非 `untaxed × 0.05`
- 採購量整箱進位用 `ROUND_UP`（而非 HALF_UP）

來源：`QuoteServiceImpl.java:222-280`。

### 3.5 已歸檔保護的條件

與 #26、#31 相同：

```java
StrUtil.isEmpty(quoteDO.getProcessInstanceId()) && ARCHIVED.equals(quoteDO.getProcessStatus())
```

→ 拋 `QUOTE_ARCHIVED_CANNOT_UPDATE`

### 3.6 BPM 表單路徑的混淆

- `createQuote`（手動建）用 **`PURCHASE_REQUISITION`**（請購表單路徑）⚠️ 疑似 bug
- Controller 的 `getToDoQuotePageByFlow` 用 **`QUOTATION`**
- 兩者不一致，可能造成手動建的報價單其流程實例掛到「請購流程」上

來源：`QuoteServiceImpl.java:74` vs line 174。詳見 §11。

### 3.7 跨模組依賴

- `purOrderMapper` / `purOrderDetailMapper`（PMM 內）：建採購單
- `selectQuoteDetailForOrderNewList`：跨表查（join 廠商報價 #28、廠商主檔 #27、請購單 #31）
- BPM：`PURCHASE_REQUISITION`（誤）、`QUOTATION`、`PURCHASING`

### 3.8 編輯子表的策略

`updateQuoteDetailList`：刪舊插新（與 #27 / #28 / #31 一致）。

### 3.9 歷史採購記錄

`/getOrderHisList?prodCode=` → `purOrderDetailMapper.getOrderHisList(prodCode)`，回該品號的歷史採購明細（含廠商、價格、日期）。

**注意**：prodCode 為 null 拋 RuntimeException（非框架 ServiceException），訊息「請傳入品號，品號爲空」（line 198）。

---

## 4. 情境說明

### 4.1 正常流程 — 採購比價 + 歸檔

採購人員小李在「報價分頁」看到剛由 #31 自動產生的報價單 Q-2026-001。展開明細：

- 牛肉餅 LB-04（請購量 50 公斤）
- 起司片 PKG-CHEESE（請購量 30 包）

她點「歷史採購記錄」看牛肉餅近 6 個月的廠商與單價，決定選「冷凍肉商 FROZEN-MEAT-001」（價格較優）。為起司片選「起司商」。儲存後送出簽核。

主管核准 → BPM 推進至「已歸檔」。系統：

1. validateQuoteDetailList：兩筆 defaultSupplier 都有 → 通過
2. 單頭 status = "2"
3. 明細 status = "2"
4. updateById
5. generateNewPurOrder：
   - 按 mfrId 分群 → 兩家廠商 → 建 2 張採購單
   - 牛肉餅採購單：purQty = ceil(50/15箱裝) = 4 箱、單價 4500、行金額 18000
   - 起司片採購單：purQty = ceil(30/12包箱裝) = 3 箱、單價 600、行金額 1800
   - 兩家都是 0（營業稅）→ totalAmount = untaxed × 1.05
6. 啟動採購單 BPM
7. 採購可在 #33 看到 2 張採購單待處理

### 4.2 異常情境 — 漏選預設廠商

小李為起司片忘了選廠商就點「歸檔」：

- validateQuoteDetailList → 拋 `QUOTE_DEFAULT_NOT_EXISTS`
- 訊息「報價單明細缺少預設廠商」（推測）
- 歸檔失敗

### 4.3 異常情境 — 浮點精度

`new BigDecimal(1.05)` 用 double 建構 → BigDecimal 變成 `1.050000000000000044408920985006...`

採購單未稅金額 18000 × 1.05 = 18900 **正確**，但中間值會帶上不必要的尾數小數。實際對採購不致命，但 audit 數字可能顯示醜陋（見 §11）。

### 4.4 規則分流 — 同廠商多明細

若報價單兩筆明細都選了「冷凍肉商」，groupBy mfrId 後只會建 **1 張** 採購單，含 2 行明細。

### 4.5 規則分流 — 編輯已歸檔但有 processInstanceId

某報價單已歸檔但 processInstanceId 非空：

- validateQuoteExists 不擋
- 允許編輯（同 #31、#26 的「條件式保護」陷阱）

### 4.6 查歷史採購

「品號為空」用 RuntimeException 拋而非 ServiceException — 前端拿到的是通用 500（見 §11）。

---

## 5. 操作流程

```
[#31 請購單歸檔]
  └─ 自動建立報價單（status="1", processStatus="待處理"）

[採購人員進入「報價管理」]
  │
  ├─ 1. 取單筆 GET /pmm/quote/get?id=
  │    └─ 主表 + QuoteDetailVO 明細列表
  │
  ├─ 2. 分頁 / 待簽分頁 GET /page、/todo-page
  │    └─ 待簽分頁用 QUOTATION 表單路徑
  │
  ├─ 3. 取明細列表 GET /pmm/quote/quote-detail/list-by-quote-id?quoteId=
  │
  ├─ 4. 查歷史採購 GET /pmm/quote/getOrderHisList?prodCode=
  │
  ├─ 5. 編輯（選預設廠商）PUT /pmm/quote/update
  │    ├─ 權限：pmm:quote:update
  │    ├─ validateQuoteExists（檢查存在 + 未歸檔）
  │    ├─ validateQuoteDetailList（若歸檔，明細 defaultSupplier 必填）
  │    ├─ 若歸檔 → 單頭 status="2"
  │    ├─ 更新單頭
  │    ├─ 若歸檔 → 明細 status="2"
  │    ├─ 更新明細（刪舊插新）
  │    └─ 若歸檔 → generateNewPurOrder（按廠商分群建採購單）
  │
  ├─ 6. 建立（手動）POST /pmm/quote/create
  │    ├─ insert 主 + 明細
  │    └─ ⚠️ 啟動流程用 PURCHASE_REQUISITION 路徑（疑似 bug）
  │
  ├─ 7. 刪除 DELETE /pmm/quote/delete?id=
  │
  └─ 8. 匯出 Excel GET /export-excel

[generateNewPurOrder 子流程]
  │
  ├─ 撈明細（join 廠商報價 / 廠商 / 請購）
  ├─ 按 mfrId groupBy
  └─ 對每組：
       ├─ 建 PurOrderDO（signCode="採購單管理"）
       ├─ 對每明細：
       │   ├─ purQty = ceil(purQuantity / singlePackCount)  ROUND_UP
       │   └─ lineAmount = purQty × unitPrice  (scale=3 HALF_UP)
       │   └─ 累計 untaxedAmount
       ├─ batch insert 明細
       ├─ 計算稅：營業稅 → ×1.05；其他 → 不加
       ├─ updateById 單頭
       └─ 啟動採購單 BPM 流程
```

---

## 6. 欄位規格

### 6.1 單頭（`pmm_quote`）

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| signCode | 單據編號 |
| reqReason | 請購原因 |
| warehouse / warehouseName | 交貨地點 |
| reqDate | 需求日期 |
| reqSignCode | 對應的請購單號 |
| status | 1=報價中 / 2=採購中 |
| processStatus | 待處理 / 待簽核 / 已歸檔 |
| processInstanceId | BPM |

### 6.2 明細（`pmm_quote_detail`）

| 欄位 | 中文業務語 |
|---|---|
| quoteId | 主表 ID |
| prodCode | 品號 |
| standardQuantity | 請購量 |
| totalStandardQuantity | 總採購計數 |
| status | 1/2 |
| defaultSupplier | **預設廠商**（歸檔必填，廠商主表 ID） |
| latestQuotePerPack | 最新報價 NTD/包裝 |
| latestQuotePerKgL | 最新報價 NTD/單位 |
| reqItem | 請購項次 |
| reqSignCode | 請購單號 |

### 6.3 驗證規則

- 歸檔時 `defaultSupplier` 必填（service 端檢查）
- 其他必填靠前端

---

## 7. 商業邏輯

### 7.1 整箱進位公式

```
purQty = ROUND_UP(purQuantity / singlePackCount, 0)
```

例：50 公斤 / 15 公斤/箱 = 3.33 → 4 箱

### 7.2 行金額

```
lineAmount = purQty × unitPrice  scale=3 HALF_UP
```

### 7.3 稅額計算

```
taxType="0"（營業稅 5%）：
  totalAmount = untaxedAmount × 1.05
其他：
  totalAmount = untaxedAmount
taxAmount = totalAmount - untaxedAmount
```

⚠️ 用 `new BigDecimal(1.05)` 浮點建構，精度問題。

### 7.4 歸檔同步狀態切換

- 單頭 status = "2"
- 所有明細 status = "2"

### 7.5 按廠商分群建採購單

每個 mfrId 一張 PurOrderDO，同廠商的多筆明細合併到同一張採購單。

---

## 8. 使用角色與權限

| 角色 | 可操作 | 對應權限字串 |
|---|---|---|
| 採購人員 | 編輯（選廠商）、刪除、查詢、匯出 | `pmm:quote:create`、`update`、`delete`、`query`、`export` |
| 採購主管 | 待簽分頁 + 簽核 | `query` + BPM 角色 |

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節。建議：

### 9.1 編輯頁

- 主表：單據編號（唯讀）、reqSignCode（連結到 #31）、交貨地點、需求日期
- 明細表格：品號、廠商下拉（**必選**，廠商來源由 #28 報價提供 + 帶最新單價）、最新報價、單位、請購量、操作
- 「歷史採購」按鈕：點某品號叫出近 N 筆歷史採購（不同廠商、不同時間的價格）

### 9.2 分頁

- 條件：流程狀態、status、reqSignCode、建立時間
- 表格：單據編號、reqSignCode、status（報價中/採購中）、processStatus、操作

---

## 10. 功能範圍

### 10.1 包含的功能

- 報價單 CRUD（單頭 + 明細）
- 預設廠商歸檔必填校驗
- 歷史採購記錄查詢
- 歸檔自動產生採購單（按廠商分群、整箱進位、稅額計算）
- BPM 流程整合
- 待簽分頁、Excel 匯出

### 10.2 預留但尚未實作 / 缺陷

- **createQuote 用 PURCHASE_REQUISITION 表單路徑**：疑似 bug，應為 QUOTATION
- **`new BigDecimal(1.05)`**：浮點精度問題
- **歷史採購用 RuntimeException** 拋空品號
- **VO 無 `@NotNull`**：必填靠前端
- **已歸檔保護的「processInstanceId 空且歸檔」條件**：同 #31 陷阱

### 10.3 不包含

- 請購單（屬於 #31）
- 採購單（屬於 #33，由本功能歸檔產生）
- 廠商主檔（屬於 #27）
- 廠商報價維護（屬於 #28，作為廠商下拉資料源）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| createQuote 啟動流程用 `PURCHASE_REQUISITION` 而非 `QUOTATION` | 疑似 bug，手動建立的報價單流程實例可能掛錯路徑 | `QuoteServiceImpl.java:74` |
| `new BigDecimal(1.05)` 浮點精度 | 應改為 `new BigDecimal("1.05")` 或 `BigDecimal.valueOf(1.05)` | line 262 |
| 稅額用減法回推 vs 直接 untaxed × 0.05 | 兩者結果可能差 1 分（捨入） | line 266 |
| 整箱進位用 ROUND_UP — 廠商若可接受零頭量，會超買 | 業務邏輯需確認 | line 247 |
| 「歸檔必填預設廠商」訊息是 `QUOTE_DEFAULT_NOT_EXISTS` — 中文訊息？ | ErrorCode 內容需確認 | line 141 |
| status 值「1/2」字面，未 enum 化 | 字典 / enum | DO `status` |
| 同廠商多筆明細合併採購單 — 倉庫不同的情況怎麼處理？ | 程式取第一筆 quoteDetailForOrderVO 的 warehouse | line 229-234 |
| `singlePackCount` 為 Long，但用 `new BigDecimal(singlePackCount)` 建構 | 應該可接受，但與 BigDecimal(int) 不同 | line 247 |
| 為何 generateNewPurOrder 在 service 內公開呼叫，外部能否被誤觸發？ | private 方法，安全 | line 222 |
| 已歸檔保護條件同 #31 / #26 陷阱 | processInstanceId 非空且歸檔不被擋 | line 129-131 |
| 編輯刪舊插新導致明細 id 變動 | 採購單明細的 reqItem 對外鍵會錯亂？ | line 208-212 |
| 同一張 QuoteDO 二次歸檔（重複 update） | 系統會二次 generateNewPurOrder 嗎？無檢查 | line 107-109 |
| 預設廠商如何挑：UI 是顯示「該品號所有有效廠商」嗎？ | 程式未實作此查詢端點，前端應呼叫 #28 的 vendor-quote-by-product-page | 邏輯歸前端 |
| getOrderHisList 對 prodCode=null 用 RuntimeException | 與框架慣例不符 | line 197-199 |
| `selectQuoteDetailForOrderNewList` 的 SQL 是否有正確 join `mfr_basic_final`、`vendor_quote_maintenance_detail` 對應到 `defaultSupplier`？ | 跨模組 join，邏輯複雜 | mapper xml 未讀 |
| 「採購單」signCode 規則「採購單管理」與 #33 一致 | menuService.generateSignCode 規則需確認 | line 232 |
| `taxType` 從哪取（廠商主檔的 tax 欄位） | 與 #27 `tax` 對應，0=營業稅 / 1=零稅 / 2=免稅 | line 260 + #27 DO |
| 1.05 倍率硬編 — 若稅率變動需改程式 | 應設定檔化 | line 262 |
| 已歸檔的單能否「重新發起採購單生成」？ | 目前無此入口 | 業務需求 |
