# PRD｜採購管理 — 廠商資料維護作業

> 來源：逆向自 `kingmaker-module-pmm` 後端程式碼（`controller/admin/vdm/`、`service/vdm/VendorMaintenanceServiceImpl.java`、`dal/dataobject/vdm/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **採購部維護人員 / 財會 / 行政**。每當公司要跟一家新廠商開始往來，我需要在系統建立這家廠商的完整檔案：

- **誰：** 廠商代號、簡稱、全名、統一編號、負責人
- **聯絡方式：** 多個聯絡人、電話、Email、傳真
- **怎麼付款：** 結賬日、付款代碼、付款方式、付款條件、付款週期
- **錢付到哪：** 多個收款銀行帳號、銀行名稱、帳號、戶名
- **管制狀態：** 是否為管制廠商、是否為總公司、計稅方式（營業稅 / 零稅率 / 免稅）

建好後送簽核，核准後這家廠商才能被「廠商報價」「採購單」「驗收」等下游使用。

### 1.2 我要做什麼

- 新建廠商主檔（一站式：主資料 + 聯絡 + 交易 + 收款）
- 編輯既有廠商（含子表）
- 軟刪除廠商（含子表）
- 變更單據狀態（驅動簽核流程）
- 分頁查詢、待簽分頁、單筆查詢
- 取下拉選項：公司群（總公司=Y 的廠商）、付款代碼（從付款代碼維護表）、單據編號清單
- 給「廠商報價維護作業」（#28）取「該廠商的付款方式 + 最近一筆交易資料」
- 匯出 Excel 模板、匯入廠商 Excel（支援更新 / 不更新模式）

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 一張單建好廠商所有資訊 | 採購、財會、行政在不同模組要查不同資訊，但建檔應該是一次完成 |
| 同一個廠商代號不能重複維護 | 否則下游報價、採購單會撈到兩筆 |
| 多筆聯絡人 / 收款銀行 / 交易資料 | 同一家廠商可能有多個聯絡人、多個銀行帳號、多種付款條件 |
| 預設標記 | 多個聯絡人 / 銀行中標一個為預設，下游自動帶 |
| 走簽核流程 | 開廠商與付款帳號是高風險操作 |
| 已歸檔的不能再改 | 否則 audit 與下游採購會錯亂 |
| Excel 匯入 | 一次匯入大量舊系統的廠商主檔（移轉用） |
| 匯出 Excel 模板 | 給使用者下載模板，照規格填好再匯入 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 建立廠商（主表 + 三張子表一次寫入） | 一站式建檔 |
| 廠商代號唯一性檢查 | 防重複維護 |
| 編輯（子表採「軟刪舊 + 插新」） | 簡化前端，不必逐筆 diff |
| 批次軟刪除 | 廢棄不再往來的廠商 |
| 變更單據狀態 | 簽核流程驅動 |
| 分頁查詢、待簽分頁 | 找回 / 處理 |
| 公司群下拉、付款代碼下拉、單據編號下拉 | 編輯頁面的選單來源 |
| 付款 + 交易資料 API | 給 #28 廠商報價即時拿到付款條件 |
| Excel 匯出模板 / 匯入 | 大量資料遷移 |
| BPM 流程整合 | 自動發起簽核 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 廠商資料維護作業 |
| 所屬模組 | PMM（採購管理） |
| 兄弟功能 | 廠商報價維護作業（#28）、請購計劃管理（#29）、原料物需求行事曆（#30）、請購單管理（#31）、報價管理（#32）、採購單管理（#33）、結轉驗收作業（#34）、驗收確認作業（#35） |
| 主要頁面 | 廠商維護編輯頁（4 段：主資料 / 聯絡 / 交易 / 收款）、單頭分頁、待簽分頁、匯出 / 匯入 |
| 簽核流程 | 有：`FormPathUniqueEnum.VENDOR` |

---

## 2. 功能目的

廠商資料維護作業是 PMM 模組的**根級主檔**，所有「跟外部公司有錢往來」的下游流程（報價、請購、採購、驗收、付款）都引用這份資料。

設計理念：

1. **一個廠商一張完整單** — 主資料 + 多筆聯絡 + 多筆交易 + 多筆收款，1+N+N+N 結構
2. **廠商代號（mfrId）為對外鍵** — 下游用 mfrId 字串引用，不是主鍵 id
3. **唯一性保護在 mfrId 而非 id** — 程式邏輯檢查未刪除資料中 mfrId 不重複
4. **必經簽核流程** — 高風險主檔
5. **已歸檔不可改 + 流程實例驅動狀態** — 變更狀態用獨立端點
6. **支援 Excel 匯入** — 大批量遷移
7. **下游報價可即時取付款條件 + 最新交易資料**

---

## 3. 業務邏輯背景

### 3.1 四張表（1 主 + 3 子）

| 表 | 用途 |
|---|---|
| `pmm_mfr_basic_final`（主 / `PmmMfrBasicFinalDO`） | 廠商基本資訊：mfrId、單據編號、單據狀態、簡稱、全名、類別、是否管制、是否總公司、統編、計稅方式、電話、傳真、負責人、公司群、地址、供應物品、結賬日、備註、幣別、流程實例 ID |
| `pmm_mfr_basic_lcn_final`（聯絡 / `PmmMfrBasicLcnFinalDO`） | mfrBasicId、項次、聯絡人、分機、電話、Email、是否預設 |
| `pmm_mfr_basic_trd_final`（交易 / `PmmMfrBasicTrdFinalDO`） | mfrBasicId、項次、付款代碼、付款方式、付款條件、週期（DAY/MONTH）、週期乘數、週期屬日、狀態 |
| `pmm_mfr_basic_rcb_final`（收款 / `PmmMfrBasicRcbFinalDO`） | mfrBasicId、項次、銀行代碼、銀行名稱、銀行帳號、銀行戶名、銀行地址、是否預設 |

設計理念：

- 主表存「廠商整體」資訊
- 三張子表分別處理「人 / 錢條件 / 錢帳號」三大維度
- 每張子表自有「項次」（item）做排序、有「是否預設」（isDefault）做下游 fallback
- 子表透過 `mfrBasicId` 指向主表 id（**主表內部 ID**，不是 mfrId 廠商代號）

### 3.2 mfrId 與內部 id 的差別

| 欄位 | 用途 | 例 |
|---|---|---|
| `id`（主鍵 Long） | 系統內部用、子表 FK | 12345 |
| `mfrId`（字串） | 業務語意上的「廠商代號」、下游引用用 | MFR001 |

**唯一性約束**：在 mfrId 上（程式邏輯檢查），不是 id 上。

### 3.3 廠商類別與狀態

| 欄位 | 合法值 | 說明 |
|---|---|---|
| `mfrType` | 0=供應商、1=一般行政廠商 | 為 Integer，無 enum 固化 |
| `isControlled` | true=管制廠商 / false=否 | 管制廠商可能有額外簽核 / 採購限制 |
| `isHeadOffice` | true=總公司 / false=否 | 總公司會出現在「公司群下拉」 |
| `tax` | 0=營業稅 / 1=零稅率 / 2=免稅 | Integer，無 enum |
| `processStatus` | 待處理 / 待簽核 / 已歸檔 | 字面字串，未字典化 |

### 3.4 「公司群」概念

`companyGroup` 欄位記錄該廠商所屬的「公司群」。下拉選項來源 = 所有 `isHeadOffice=true` 的廠商。

語意：

- 一家集團有多個子公司各自登記為「廠商」
- 其中總公司一個被標 isHeadOffice=true
- 其他子公司在 `companyGroup` 欄位填總公司的代號 / 簡稱
- 報表彙整可依公司群 group by

### 3.5 子表的「預設」與「項次」

- 聯絡與收款表有 `isDefault`：多筆中只能 / 應該標一個為預設
- 但程式邏輯**未檢查「只能一個 isDefault=true」** — 多個都 true 是合法的
- 交易表沒有 isDefault，而是用 `status`（停用 0 / 啟用 1）

### 3.6 唯一性檢查

`createVendorMaintenance` 與 `updateVendorMaintenance` 都檢查：

- 新增：mfrId 非空 → `vendorBasicMapper.existsByMfrId(mfrId)` 為 true 則拋錯
- 更新：mfrId 非空 → `selectIdByMfrId(mfrId)` 回傳的 id 與當前 id 不同則拋錯

錯誤訊息用 inline ErrorCode（2_002_000_001）+ 自訂訊息「該廠商 (mfr_id: xxx) 已維護資料，無法重複維護」（來源：`VendorMaintenanceServiceImpl.java:134、167`）— **不走 ErrorCodeConstants**，與框架慣例不符（見 §11）。

### 3.7 編輯子表的策略

更新流程：

1. 軟刪除三張子表所有相關記錄（by mfrBasicId）
2. 重新插入新子表

優點：簡單，前端不必逐筆 diff
缺點：

- 子表 id 變動，外部若有引用會壞
- 軟刪除累積大量歷史記錄
- 並發更新可能造成 race condition

### 3.8 已歸檔保護

`validateVendorMaintenanceExists`（未完整列出）會檢查單據狀態 = 已歸檔 → 拋 `VENDOR_ARCHIVED_CANNOT_UPDATE`。

### 3.9 BPM 流程整合

- 表單路徑：`FormPathUniqueEnum.VENDOR.getPath()`
- 建立時自動啟動流程：`createProcessInstanceIfFlowOpen` → 回填 processInstanceId
- 更新狀態：獨立端點 `/update-status/{id}/{processStatus}`，**不檢查歸檔**（直接覆寫）— 給 BPM 流程驅動用

### 3.10 給下游使用的 API

| 端點 | 用途 |
|---|---|
| `/payment-and-trd/{mfrId}` | 給 #28 廠商報價拿「該廠商的付款方式 + 最新一筆交易資料」 |
| `/company-groups` | 公司群下拉（只回 isHeadOffice=true 的廠商） |
| `/pay-codes` | 付款代碼下拉（從 BHM 的付款代碼維護表） |
| `/sign-codes` | 單據編號清單（給查詢條件用） |

### 3.11 跨模組依賴

- 付款代碼來源：BHM 模組的 `paymentmethod` 表（注意 BHM 是凍結模組，依賴它意味本功能依賴一個不會再變的主檔）
- 流程：依賴 system 模組的 BPM
- mfrId：給 PMM 內所有下游使用

### 3.12 Excel 模板與匯入

- `/export`：匯出空白模板，含主表 + 三張子表的 sheet
- `/import`：上傳 Excel，逐 sheet 解析、跑 converter（YesNo、廠商類別、計稅方式、付款代碼字串轉 ID、狀態啟停）
- `updateSupport=true` → 允許覆蓋既有廠商；`false`（預設）→ 重複的 mfrId 視為失敗
- 回傳 `MfrImportResult`（成功 / 失敗筆數、錯誤明細）

匯入用 EasyExcel + ReadListener 設計，**程式碼 1338 行**，含許多儲存格樣式（POI）、欄位驗證、批次寫入；屬於本功能最複雜的部分。

### 3.13 與框架慣例的偏離

| 項目 | 偏離點 |
|---|---|
| URL 路徑 | `/pmm/vdm` 短碼，其他模組多用 hyphen 完整字 |
| 錯誤碼 | 多處用 `new ErrorCode(2_002_000_001, "...")` inline 而非 ErrorCodeConstants 常數 |
| 更新採 PathVariable | `PUT /update/{id}`，與 PDM 模組多用 body 不一致 |
| 批次刪除用 body | `DELETE /delete` 帶 List body |
| 變更狀態用 PathVariable | `PUT /update-status/{id}/{processStatus}` 把狀態放在 URL |
| ProcessStatusEnums import | 程式有 import 但訊息字串仍硬編 | 未充分使用 |

---

## 4. 情境說明

### 4.1 正常流程 — 新建一家供應商

採購助理小張要新建「冷凍肉商 FROZEN-MEAT-001」。

1. 進入廠商維護編輯頁，分四段填表：

   **主資料**：
   - mfrId: `FROZEN-MEAT-001`
   - 簡稱: 冷凍肉商
   - 類別: 0（供應商）
   - 統編: 12345678
   - 計稅: 0（營業稅）
   - 總公司: false
   - 公司群: 選下拉「冷凍食品總公司」
   - 結賬日: 25
   - 幣別: TWD

   **聯絡資訊**：
   - 第 1 項：聯絡人 王經理 / 電話 02-xxx / Email wang@... / 預設=true
   - 第 2 項：聯絡人 李業務 / 電話 02-yyy / 預設=false

   **交易資料**：
   - 第 1 項：付款代碼 PAY01 / 付款方式 月結 / 條件 30天 / 週期 MONTH / 乘數 1 / 屬日 25 / 啟用

   **收款銀行**：
   - 第 1 項：銀行代碼 008 / 銀行名稱 華南 / 帳號 1234-... / 戶名 冷凍肉商 / 預設=true

2. POST /create
3. 系統：
   - 檢查 mfrId 不重複
   - signCode = generateSignCode("廠商資料維護作業")
   - processStatus = 「待處理」
   - insert 主表 → 拿 basicId
   - insert 三張子表（每張用 mfrBasicId = basicId）
   - 啟動 BPM 流程 → 回填 processInstanceId
4. 進入主管待簽分頁

### 4.2 典型業務 — 編輯廠商（換聯絡人）

王經理離職，新聯絡人為陳經理。小張進入該廠商編輯：

1. 在聯絡資訊段：刪掉第 1 項，新增「陳經理 / 預設=true」、保留「李業務」
2. PUT /update/{id}
3. 系統：
   - 檢查 mfrId 唯一性（排除自己）
   - 軟刪除舊聯絡子表記錄（by mfrBasicId）
   - 插入新聯絡子表
   - 同時把交易、收款都刪舊插新（即使沒改也會跑一次）
4. 之後該廠商的所有聯絡子表 id 都變了

⚠️ **副作用**：即使只改聯絡，交易 / 收款的 id 也會變動，若有外部 reference 會失效。

### 4.3 異常情境 — 重複維護

某新進人員不知道「FROZEN-MEAT-001」已存在，重新建檔：

- POST /create
- existsByMfrId 回 true → 拋錯「該廠商 (mfr_id: FROZEN-MEAT-001) 已維護資料，無法重複維護」
- 訊息含使用者輸入，可能造成 XSS 風險（低，但需注意）

### 4.4 異常情境 — 編輯已歸檔的單

「FROZEN-MEAT-001」已被簽核流程跑到「已歸檔」。試圖編輯：

- `validateVendorMaintenanceExists` 偵測 → 拋 `VENDOR_ARCHIVED_CANNOT_UPDATE`

### 4.5 規則分流 — 變更狀態獨立端點

BPM 流程節點推進時呼叫 `PUT /update-status/{id}/{processStatus}`：

- 不檢查歸檔
- 直接 updateById
- 用於系統間呼叫，不給使用者直接用

### 4.6 規則分流 — 取付款與交易

#28 廠商報價在建立報價時，要知道該廠商當前的付款方式與最新交易條件：

- 打 GET /payment-and-trd/{mfrId}
- 系統撈該廠商的付款代碼資訊 + trdFinalList（最新一筆）
- 回 `PaymentAndQuoteResultVO`

### 4.7 規則分流 — 匯出模板 + 匯入

財會要從舊系統匯入 50 家廠商：

1. 點「匯出模板」→ 下載空白 Excel（含主表 sheet + 三張子表 sheet）
2. 照模板填寫
3. 上傳：POST /import?file=xxx.xlsx&updateSupport=false
4. 系統：
   - 解析每個 sheet
   - 跑 converter 轉換字面值（如「供應商」→ 0、「Y」→ true）
   - 對每筆主表記錄：
     - existsByMfrId 重複 → 視 updateSupport 決定（false→失敗；true→更新）
   - 批次寫入主表 + 對應子表（透過 sheet 中的「廠商代號」關聯）
5. 回 `MfrImportResult`：成功筆數、失敗清單、錯誤訊息

⚠️ 匯入流程**未走 BPM 流程**（推測） — 大量匯入若每筆都跑簽核會卡死。需與 PM 確認此設計（見 §11）。

### 4.8 使用者鍵入錯誤 — 漏填主資料

`PmmVendorMaintenanceSaveReqVO` 上 `basicFinal` 的 `@NotNull` 註解被**註解掉**（`PmmVendorMaintenanceSaveReqVO.java:20`）。代表後端不檢查主表是否存在，極端情況可送出空 basicFinal。實際是 NPE 風險（見 §11）。

---

## 5. 操作流程

```
[使用者進入「廠商資料維護作業」]
  │
  ├─ 1. 建立 POST /pmm/vdm/create
  │    ├─ 權限：pmm:mfr-basic-final:create
  │    ├─ mfrId 唯一性檢查（未刪除）
  │    ├─ signCode = generateSignCode("廠商資料維護作業")
  │    ├─ processStatus = 「待處理」
  │    ├─ insert 主表 → basicId
  │    ├─ insert 三張子表
  │    └─ 啟動 BPM 流程 → 回填 processInstanceId
  │
  ├─ 2. 更新 PUT /pmm/vdm/update/{id}
  │    ├─ 權限：pmm:mfr-basic-final:update
  │    ├─ 檢查存在 + 未歸檔
  │    ├─ mfrId 唯一性（排除自己）
  │    ├─ 更新主表
  │    ├─ 軟刪除三張子表所有相關記錄
  │    └─ 重新插入三張子表
  │
  ├─ 3. 變更狀態 PUT /pmm/vdm/update-status/{id}/{processStatus}
  │    ├─ 權限：pmm:mfr-basic-final:update
  │    ├─ 檢查存在 / 未刪除
  │    └─ updateById（不檢查歸檔）
  │
  ├─ 4. 批次刪除 DELETE /pmm/vdm/delete  (body: List<Long>)
  │    ├─ 權限：pmm:mfr-basic-final:delete
  │    └─ 軟刪除主表 + 三張子表
  │
  ├─ 5. 分頁查詢 GET /pmm/vdm/page
  │    ├─ 權限：pmm:mfr-basic-final:query
  │    └─ 過濾：單據狀態、單據編號（多選）、建立時間區間、mfrId
  │
  ├─ 6. 待簽分頁 GET /pmm/vdm/todo-page
  │    └─ 取 BPM 分派給我的 processInstanceIds
  │
  ├─ 7. 取單筆 GET /pmm/vdm/get/{id}
  │    └─ 回主表 + 三張子表
  │
  ├─ 8. 公司群下拉 GET /pmm/vdm/company-groups
  │    └─ 回 isHeadOffice=true 的廠商
  │
  ├─ 9. 付款代碼下拉 GET /pmm/vdm/pay-codes
  │    └─ 取 BHM 付款代碼維護表
  │
  ├─ 10. 單據編號清單 GET /pmm/vdm/sign-codes
  │
  ├─ 11. 給 #28 用 GET /pmm/vdm/payment-and-trd/{mfrId}
  │    └─ 回付款 + 最新交易資料
  │
  ├─ 12. 匯出模板 GET /pmm/vdm/export
  │    └─ 寫出含 4 sheet 的空白 Excel
  │
  └─ 13. 匯入 POST /pmm/vdm/import?file=&updateSupport=
       ├─ 解析四個 sheet
       ├─ 跑欄位 converter
       ├─ 唯一性檢查（依 updateSupport）
       ├─ 批次寫入
       └─ 回 MfrImportResult（成功 / 失敗筆數）
```

---

## 6. 欄位規格

### 6.1 主表（`pmm_mfr_basic_final`）

| 欄位 | 中文業務語 | 型別 | 必填 |
|---|---|---|---|
| id | 內部 ID | Long | 系統 |
| signCode | 單據編號 | 字串 | 系統 |
| processStatus | 單據狀態 | 字串 | 系統 |
| mfrId | 廠商代號 | 字串 | （建議必填，唯一） |
| mfrAbrname | 廠商簡稱 | 字串 | （建議必填） |
| mfrType | 廠商類別 | Integer | 0=供應商 / 1=一般行政 |
| isControlled | 管制廠商 | Boolean | |
| isHeadOffice | 總公司 | Boolean | |
| mfrName | 廠商全名 | 字串 | |
| taxIdNo | 統一編號 | 字串 | |
| tax | 計稅方式 | Integer | 0=營業稅 / 1=零稅率 / 2=免稅 |
| tel / fax | 公司電話 / 傳真 | 字串 | |
| boss | 公司負責人 | 字串 | |
| companyGroup | 公司群 | 字串 | 引用其他總公司廠商 |
| address | 公司地址 | 字串 | |
| supplies | 供應物品 | 字串 | |
| paymentDate | 結賬日 | Integer | |
| remarks | 備註 | 字串 | |
| moneyType | 幣別 | 字串 | |
| processInstanceId | 流程實例 ID | 字串 | BPM 系統 |

### 6.2 聯絡子表（`pmm_mfr_basic_lcn_final`）

mfrBasicId、item、contactPerson、telExtension、telPhone、email、isDefault

### 6.3 交易子表（`pmm_mfr_basic_trd_final`）

mfrBasicId、item、payId、payMeth、payTerm、cycle（DAY/MONTH）、cycleMultiplier、cycleDay、status（0/1）

### 6.4 收款子表（`pmm_mfr_basic_rcb_final`）

mfrBasicId、item、bankId、bankName、bankAcct、bankAcctHolderName、bankAddr、isDefault

### 6.5 查詢條件（`PmmVendorMaintenancePageQueryVO`）

| 條件 | 比對 |
|---|---|
| queryCategory | 等於（推測：history / current） |
| processStatus | 等於 |
| signCode | IN（陣列） |
| createTime | 區間 |
| mfrId | 等於 |
| processInstanceStatus | 流程實例狀態 |
| taskIds | 待簽用 |

### 6.6 驗證規則

- VO 上的 `basicFinal` `@NotNull` 註解被註解掉 — **後端不強制必填**
- mfrId 唯一性檢查在 Service 內
- 子表用 `@Valid` 但子表 VO 內部具體欄位驗證未詳列

---

## 7. 商業邏輯

### 7.1 建立

```
1. mfrId 不重複（未刪除）
2. signCode + processStatus 系統填入
3. insert 主表 → basicId
4. createLcnFinalList / createTrdFinalList / createRcbFinalList（每張子表 setMfrBasicId(basicId) 後 batch insert）
5. 啟動 BPM 流程（選單綁定時）
```

### 7.2 更新（刪舊插新）

```
1. 檢查存在 + 未歸檔
2. mfrId 唯一性（排除自己）
3. updateById 主表
4. 軟刪除三張子表
5. insert 三張子表
```

### 7.3 變更狀態（給 BPM 用）

```
1. 檢查存在 + 未刪除（不檢查歸檔）
2. updateById（只改 processStatus）
```

### 7.4 批次刪除

軟刪除主表 + 三張子表（with @Transactional）。

### 7.5 BPM 整合

- 啟動：`createProcessInstanceIfFlowOpen(userId, FormPathUniqueEnum.VENDOR, basicId)`
- 待簽：`listProcessInstanceIdsForAssigneeTodoPage`
- 狀態：由 `/update-status` 端點驅動

### 7.6 Excel 匯入細節

- EasyExcel 多 sheet 解析
- 多個 converter：YesNoConverter、MfrTypeConverter、TaxTypeConverter、StatusConverter、PaymentCodeToIdStringConverter
- 重複 mfrId 行為依 updateSupport flag
- 批次寫入後回 MfrImportResult

---

## 8. 使用角色與權限

| 角色 | 可看 / 可操作 | 對應權限字串 |
|---|---|---|
| 採購維護人員 | 建立 / 編輯 / 刪除 / 查詢 / 匯出匯入 / 變更狀態 | `pmm:mfr-basic-final:create`、`update`、`delete`、`query` |
| 簽核主管 | 待簽分頁、簽核流程 | `query` + BPM 角色 |
| 廠商報價人員（#28） | 查詢 + 取付款交易 API | `query` |
| 其他下游（採購單、驗收） | 查詢公司群 / 廠商清單 | `query` |

> 注意：權限名 `pmm:mfr-basic-final:*` 用了「英文 final 表名」當權限段，與業務「廠商」語意脫節 — 角色設定難讀（見 §11）。

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節，**待前端對照**。建議：

### 9.1 編輯頁

- Tab 1（主資料）：mfrId（建立後唯讀）、簡稱、全名、類別（下拉）、統編、計稅（下拉）、電話、傳真、負責人、公司群（下拉，來源 /company-groups）、地址、供應物品、結賬日（數字 1–31）、幣別（下拉）、備註、管制廠商（switch）、總公司（switch）
- Tab 2（聯絡）：表格，加 / 改 / 刪聯絡人；標一個為預設
- Tab 3（交易）：表格，加 / 改 / 刪交易條件；付款代碼（下拉，來源 /pay-codes）、週期 DAY/MONTH（下拉）、狀態 0/1（switch）
- Tab 4（收款）：表格，加 / 改 / 刪銀行帳號；標一個為預設
- 底部：儲存按鈕（送出 BPM 流程）

### 9.2 分頁

- 條件：單據狀態、單據編號（多選）、建立時間區間、廠商代號
- 表格：單據編號、廠商代號、簡稱、類別、狀態、建立人、建立時間、操作

### 9.3 待簽分頁

- 同上但只顯示我的待簽單

### 9.4 匯入頁

- 下載模板按鈕
- 上傳 Excel
- 「重複時更新」開關（updateSupport）
- 匯入後顯示 MfrImportResult

---

## 10. 功能範圍

### 10.1 包含的功能

- 廠商資料的 CRUD（含三張子表）
- mfrId 唯一性檢查
- BPM 流程整合（建立時自動啟動）
- 變更狀態獨立端點（給 BPM 用）
- 已歸檔保護
- 公司群 / 付款代碼 / 單據編號 下拉
- 給 #28 用的付款 + 交易 API
- Excel 模板匯出 / 匯入（含 converter）
- 待簽分頁

### 10.2 預留但尚未實作 / 不完整

- **主表 `@NotNull` 被註解掉** — 後端可接受空 basicFinal，NPE 風險
- **isDefault 唯一性**（聯絡 / 收款）— 多筆 isDefault=true 不檢查
- **錯誤碼結構化** — 多處用 inline `new ErrorCode(2_002_000_001, "...")` 重複錯誤碼
- **訊息含使用者輸入** — XSS 風險
- **匯入是否走 BPM** — 推測不走，但未明確
- **子表項次（item）自動填充規則** — 程式邏輯未詳列

### 10.3 不包含

- 廠商報價（屬於 #28）
- 採購單、請購單、驗收單（屬於 #31、#33、#35）
- 付款代碼本身的維護（屬於 BHM 模組，且 BHM 凍結）
- 廠商評鑑、廠商分級

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| `basicFinal` 的 `@NotNull` 為何被註解掉？ | 後端可接受空 basicFinal，造成 NPE | `PmmVendorMaintenanceSaveReqVO.java:20` |
| 多處用 inline ErrorCode（如 2_002_000_001）而非常數 | 錯誤碼重複、訊息硬編、難多語化 | `VendorMaintenanceServiceImpl.java:134、167、192` |
| 訊息含使用者輸入（mfrId） | XSS 風險（低，但應 escape） | 同上 |
| isDefault 是否該強制唯一 | 多筆 isDefault=true 下游 fallback 不明確 | DO 無唯一性檢查 |
| 編輯刪舊插新導致子表 id 變動 | 外部 reference（若存在）會壞 | `VendorMaintenanceServiceImpl.java:178-185` |
| 變更狀態端點 `/update-status/{id}/{processStatus}` 不檢查歸檔 | 是否會被誤用導致狀態跳回？ | `VendorMaintenanceServiceImpl.java:189-199` |
| 匯入流程是否走 BPM 簽核 | 大批量匯入若都跑簽核會卡；但若不跑，主檔可能未經審核 | 程式碼未啟動流程於 import 路徑 |
| 公司群下拉「總公司=Y」是否需限制狀態 | 若某總公司已歸檔，仍會出現在下拉嗎？ | `getCompanyGroups` 未讀完整邏輯 |
| 子表的「項次」(item) 如何分配 | 是前端填還是系統自動？多筆 item 是否能重複？ | DO 無唯一性 |
| `mfrType`、`tax` 用 Integer 字面值 | 0/1/2 未 enum 化，前端易誤填 | `PmmMfrBasicFinalDO.java:34、44` |
| `processStatus` 字典化 | 字面字串「待處理 / 待簽核 / 已歸檔」未固化 | 多處硬編 |
| `paymentDate`（結賬日）為 Integer 1–31，2 月 30 號如何處理 | 與付款條件 cycle 對齊邏輯需確認 | 主表欄位 |
| 「公司群」與「總公司」的關係是否要保護 | 若把作為公司群引用的總公司刪除，子公司資料會孤兒 | 無外鍵保護 |
| 權限名 `pmm:mfr-basic-final:*` 用英文表名 | 角色設定時難讀，應改為業務詞 `pmm:vendor:*` | Controller `@PreAuthorize` |
| 是否需「啟用 / 停用」廠商整體 | 目前只有 processStatus 與軟刪除 | 主表欄位 |
| 收款銀行的銀行代碼是否有字典 | 純字串可亂填 | `PmmMfrBasicRcbFinalDO.java:28` |
| 「幣別」是否字典化 | 同上 | 主表 moneyType |
| 1338 行的 Service 包含太多 Excel 處理邏輯，是否該拆出 | 維護性 / 測試性差 | `VendorMaintenanceServiceImpl.java` 整體 |
| 編輯時，無 mfrId 變動也會跑唯一性檢查（雖然會排除自己） | 多一次 DB query | `VendorMaintenanceServiceImpl.java:163-169` |
| 三張子表是否都需要在無變動時也刪舊插新 | 浪費資源，且影響歷史 | `updateVendorMaintenance` |
| 軟刪除主表時是否同步軟刪除子表 | 程式邏輯未完整列出 | `deleteVendorMaintenanceBatch` |
