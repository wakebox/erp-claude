# PRD：採購管理模組（PMM）— 逆向規格分析

> 本文件透過逆向分析 `erp-spring/kingmaker-module-pmm` 程式碼，還原採購管理模組的完整業務規格、資料表設計、ER Model 與功能清單。
> 對應 `erp-claude/document/excel.md` 中「採購管理模組」業務主模組（序號 27 ~ 35）共 9 個系統主功能。

---

## Problem Statement

漢堡王台灣的採購管理模組（PMM）是 ERP 整個「需求集合 → 採購 → 入庫」鏈條的中段：把上游的請購需求轉成正式採購單，再經結轉驗收後送入 WHS 庫存。但目前：

1. **業務 ↔ 程式對照斷裂**：Excel 業務清單用「請購計劃管理 / 原料物需求行事曆 / 結轉驗收作業」等中文功能名，但程式碼用 `vdm / vqm / purreq / quote / purorder / purforward / puracceptance` 七個英文子域，業務方無法逐項對照確認。
2. **Excel 兩項業務無對應實作**：序號 29「請購計劃管理」與序號 30「原料物需求行事曆」在 PMM 內找不到對應 Controller，這兩支功能實際是 PDM 模組的「需求預測 / 原物料需求行事曆」（`crg_demand_forecast` / `pdm_raw_material_demand_*`），目前只串了「字串掛載」（sign_code），沒有真的自動生成請購單。
3. **完整 7 階段採購鏈無書面說明**：請購 → 報價 → 採購 → 結轉 → 驗收 → 入庫的單據轉換規則、自動生成觸發點、稅金計算公式、結轉部分驗收邏輯，全部埋在 `*ServiceImpl.java` 內，業務方與新人都看不懂。
4. **跨模組鬆耦合無 ER 圖**：PMM 內各單據之間透過 **`signCode` 字串**（而非 FK）鬆耦合（請購 signCode → Quote.reqSignCode → PurOrder.quoteSignCode → PurForward.orderSignCode → PurAcceptance.forwardSignCode）。沒有 ER 圖把這條鏈呈現出來，導致誤刪、誤改、誤對應的風險。
5. **狀態機與 BPM 綁定散落**：四種狀態 `待處理 / 待簽核 / 已歸檔 / 已作廢`（`ProcessStatusEnums`）的流轉條件、每個單據獨立的 BPM Listener、`businessKey = path:headerId` 的格式約定都沒有集中文件。
6. **稅金與採購量計算公式只活在程式碼**：報價歸檔生成採購單時的「採購量 = 請購量 ÷ 每箱量（向上取整）」、稅後金額 = 未稅 × 1.05（營業稅）」等規則沒有寫入規格。

---

## Solution

產出本 PRD 作為 PMM 採購管理模組的**權威逆向規格**：

1. Excel 業務名稱 ↔ 程式碼對照表（含「不在 PMM 內」的兩項功能去向說明）
2. 完整 7 階段採購流程 ER Model（含跨表 signCode 鬆耦合關係）
3. 13 張 PMM 資料表的完整欄位清單
4. 每個單據的狀態機（待處理 / 待簽核 / 已歸檔 / 已作廢）與 BPM 觸發時機
5. 跨單據的自動生成規則（請購歸檔 → 報價單；報價歸檔 → 採購單；採購歸檔 → 結轉驗收單；結轉「轉驗收」→ 驗收確認單；驗收歸檔 → WHS 入庫單）
6. 採購量、稅金、結轉部分驗收等核心公式還原
7. 模組的 API 端點與權限碼清單
8. 已知缺口（包含 Excel 上有但 PMM 沒做的兩項）

---

## 功能 ↔ 程式碼對照表

| Excel 序號 | Excel 名稱 | 程式對應（PMM）| 表 | 狀態 |
|---|---|---|---|---|
| 27 | 廠商資料維護作業 | `VendorMaintenanceController` + `VendorMaintenanceServiceImpl` + `VendorMaintenanceListener` | `pmm_mfr_basic_final`<br/>`pmm_mfr_basic_lcn_final`（聯絡人）<br/>`pmm_mfr_basic_rcb_final`（收款銀行）<br/>`pmm_mfr_basic_trd_final`（交易資料 / 付款條件） | ✅ 含匯入匯出、BPM |
| 28 | 廠商報價維護作業 | `VendorQuoteMaintenanceController` + `VendorQuoteMaintenanceServiceImpl` + `VendorQuoteMaintenanceStatusListener` | `pmm_vendor_quote_maintenance`<br/>`pmm_vendor_quote_maintenance_detail` | ✅ 含匯入、自動單價試算、BPM |
| 29 | 請購計劃管理 | **PMM 內無對應** — 實作在 PDM `crg_demand_forecast_config`（[`DemandForecastConfigController`](DEMAND_AGGREGATION_PRD.md)）| — | ⚠️ 不屬於 PMM；見 [Out of Scope](#out-of-scope) |
| 30 | 原料物需求行事曆 | **PMM 內無對應** — 實作在 PDM `pdm_raw_material_demand_head` / `pdm_raw_material_demand_date_list` / `pdm_raw_material_demand_detail` | — | ⚠️ 不屬於 PMM；下游字串掛載 `demand_relation_doc`、`temp_relation_doc` 才會出現在 PMM 範疇內 |
| 31 | 請購單管理 | `PurReqController` + `PurReqServiceImpl` + `PmmPurReqStatusListener` | `pmm_pur_req` / `pmm_pur_req_detail` | ✅ 含庫存試算、BPM、歸檔自動生成報價單（幂等） |
| 32 | 報價管理 | `QuoteController` + `QuoteServiceImpl` + `QuoteStatusListener` | `pmm_quote` / `pmm_quote_detail` | ✅ 含選定廠商、BPM、歸檔自動生成採購單（依廠商分組） |
| 33 | 採購單管理 | `PurOrderController` + `PurOrderServiceImpl` + `PurOrderStatusListener` | `pmm_pur_order` / `pmm_pur_order_detail` | ✅ 含稅金計算、BPM、歸檔自動生成結轉驗收單（幂等） |
| 34 | 結轉驗收作業 | `PurForwardController` + `PurForwardServiceImpl` + `PurForwardStatusListener` | `pmm_pur_forward` / `pmm_pur_forward_detail` | ✅ 含部分結轉、強制結案、BPM、結轉→驗收手動轉單 |
| 35 | 驗收確認作業 | `PurAcceptanceController` + `PurAcceptanceServiceImpl` + `PurAcceptanceStatusListener` | `pmm_pur_acceptance` / `pmm_pur_acceptance_detail` | ✅ 含 BPM、歸檔自動生成 WHS 入庫單頭/單身、`stock_reason=SW05` |

跨模組相關引用（不屬於本模組但有資料流）：

- **下游**：`PurAcceptance` 歸檔 → `whs_stock_record_head` + `whs_stock_record`（入庫單，stock_reason='SW05'），並呼叫 `StockRecordService.batchProcessStockRecords()` 更新庫存
- **跨模組依賴**：`PurReqDetail` 試算庫存時 join `whs_stock` 與 `pdm_ingredient_specs`；報價單試算 `latestQuotePerKgL` 時走 `pmm_vendor_quote_maintenance_detail` 撈最新報價
- **BPM 綁定**：每個單據透過 `MenuFlowProcessInstanceHelper.createProcessInstanceIfFlowOpen(userId, pathEnum, headerId)` 啟動流程；businessKey 格式 `{path}:{headerId}`，path 來自 [`FormPathUniqueEnum`](#bpm-form-path-對照)

---

## User Stories

### 廠商資料維護作業（Excel #27）

1. 作為**採購人員**，我想建立**廠商主檔（PmmMfrBasicFinal）**，填寫廠商代號、簡稱、全名、統一編號、計稅方式、公司電話/傳真/地址、負責人、結帳日、幣別。
2. 作為**採購人員**，我想標記廠商為**管制廠商（isControlled）**或**總公司（isHeadOffice）**；標記為總公司的廠商會在「公司群下拉」中作為選項。
3. 作為**採購人員**，我想為廠商新增多筆**聯絡人（PmmMfrBasicLcnFinal）**，包含聯絡人姓名、分機、電話、Email，並可指定一筆為**預設聯絡人**。
4. 作為**採購人員**，我想為廠商新增多筆**收款銀行（PmmMfrBasicRcbFinal）**，包含銀行代碼、銀行名稱、銀行帳號、戶名、銀行地址，並可指定一筆為**預設銀行**。
5. 作為**採購人員**，我想為廠商新增多筆**交易資料（PmmMfrBasicTrdFinal）**，包含付款代碼、付款方式、付款條件、週期（DAY / MONTH）、週期乘數、週期屬日、狀態（啟用/停用）。
6. 作為**採購人員**，我想送出廠商單據後系統依「選單是否綁定流程」（`FormPathUniqueEnum.VENDOR.path = "vdm"`）決定是否發起 BPM 簽核；BPM 通過 → 自動將 `processStatus` 更新為「已歸檔」（由 `VendorMaintenanceListener` 處理）。
7. 作為**採購人員**，我想**批次刪除**多筆廠商（軟刪除主表與子表）；已歸檔且無流程實例的廠商不可修改／不可重新流程。
8. 作為**採購人員**，我想透過 `PUT /pmm/vdm/update-status/{id}/{processStatus}` 手動切換廠商單據狀態（待處理 / 待簽核 / 已歸檔 / 已作廢）。
9. 作為**採購人員**，我想分頁查詢廠商與**簽核待辦頁**（`/page` 與 `/todo-page`），其中 todo-page 透過 `MenuFlowProcessInstanceHelper.listProcessInstanceIdsForAssigneeTodoPage()` 查出當前登入使用者的流程實例。
10. 作為**採購人員**，我想取得**公司群下拉清單**（`/company-groups`）：來源為廠商資料中 `isHeadOffice=true` 的廠商，value 為「廠商代號+簡稱+全名」、顯示「簡稱」。
11. 作為**採購人員**，我想取得**付款代碼下拉清單**（`/pay-codes`）：來源為付款代碼維護表（外部表）。
12. 作為**採購人員**，我想透過 `/payment-and-trd/{mfrId}` 取得「該廠商所有交易資料 + 對應最新報價」用於建立採購單時的付款條件預載。
13. 作為**採購人員**，我想**匯出廠商範本**（`/export`）並**匯入廠商**（`/import?file=...&updateSupport=false`）：四個子表透過 `MfrMainImportExcelVO` / `MfrLcnImportExcelVO` / `MfrRcbImportExcelVO` / `MfrTrdImportExcelVO` 各自映射，匯入結果包成 `MfrImportResult`。

### 廠商報價維護作業（Excel #28）

14. 作為**採購人員**，我想建立**廠商報價主檔（PmmVendorQuoteMaintenance）**，含主旨、廠商代號（mfrId）、幣別、報價有效起訖（quoteEffectDateSt/Ed）。
15. 作為**採購人員**，我想新增多筆**報價明細（PmmVendorQuoteMaintenanceDetail）**：每筆對應一個品號（prodCode）、類別（食材/包材）、廠商品名、廠商包裝單位、最新報價（NTD/包裝）、最新報價（NTD/單位 = kg.l）、單一包裝量（singlePackCount）、單一規格（singleCountMeasure）、適用門市、預設物流類型（useDeliveryType）、採購前置日期（beforePurchaseDate）、保存日期、最小報價量（moq）。
16. 作為**採購人員**，我想呼叫 `POST /pmm/vqm/calculate-unit-quote` **自動計算每單位報價** = 包裝報價 ÷ 單一包裝量。
17. 作為**採購人員**，我想呼叫 `POST /pmm/vqm/calculate-single-count-quote` **自動計算單一計數報價** = 包裝報價 ÷ 單一包裝量（用於計件報價）。
18. 作為**採購人員**，我想呼叫 `POST /pmm/vqm/calculate-single-count-measure` **自動計算單一計數計量(g, ml)** = 單一包裝計量 ÷ 單一包裝量（含單位換算）。
19. 作為**採購人員**，我想為報價單發起 BPM；通過後 `VendorQuoteMaintenanceStatusListener` 將狀態更新為「已歸檔」。
20. 作為**採購人員**，我想以 `processStatus` 與 `mfrId` 篩選分頁查詢，並有 `/todo-page` 簽核分頁、`/sign-codes` 與 `/mfr-ids` 用於下拉。
21. 作為**採購人員**，我想 `GET /pmm/vqm/basic-mfr-ids` 取得「廠商資料維護裡已存在的廠商代號」清單作為新建報價時的下拉資料。
22. 作為**包材維護人員**，我想 `GET /pmm/vqm/vendor-quote-by-product-page?prodCode=XXX` 查詢某品號的所有廠商報價（用於包材維護的「貨源明細」）。
23. 作為**採購人員**，我想**匯出報價範本**（`/get-import-template`）與**匯入廠商報價**（`/import`），匯入結果包成 `VqmImportResult`。

### 請購單管理（Excel #31）

24. 作為**門市/採購人員**，我想建立**請購申請單（PurReq）**，含主旨、請購原因、需求日期（reqDate）、交貨地點代號（warehouse）、加權係數（weightFactor）。
25. 作為**門市/採購人員**，我想新增多筆**請購明細（PurReqDetail）**：每筆對應品號（prodCode）、目前庫存量（currentStockNum）、安全存量（safeStock）、請購計數（standardQuantity）、單位、需求備註、倉庫 ID。
26. 作為**門市/採購人員**，我想呼叫 `GET /pmm/pur-req/stock-current-page?prodCode=...&warehouse=...&weightFactor=N` **自動試算請購計數**：
    - 系統從 `whs_stock` join `pdm_ingredient_specs` 取目前庫存量、安全存量、單位名稱、單一規格；
    - 公式：`standardQuantity = (safeStock - currentStockNum) × weightFactor`（當三個值都不為 null 時生效）。
27. 作為**門市/採購人員**，我想 `GET /pmm/pur-req/stock-list-by-prod-code?prodCode=...` 查所有倉庫對該品號的庫存清單。
28. 作為**門市/採購人員**，我想送出請購單，系統會：
    - 自動產生 signCode（呼叫 `MenuService.generateSignCode("請購單管理")`）；
    - 初始 `processStatus = 待處理`；
    - 依選單是否綁定 BPM（`FormPathUniqueEnum.PURCHASE_REQUISITION.path = "prm"`）決定是否發起 Flowable 流程；流程 ID 寫回 `processInstanceId`。
29. 作為**簽核人**，我想在 `/pmm/pur-req/todo-page` 看到我的待辦請購單；通過後 `PmmPurReqStatusListener` 自動將狀態切為「已歸檔」並觸發**自動生成報價單**。
30. 作為**系統**，當請購單首次（且僅一次）從非「已歸檔」→「已歸檔」時，我必須**幂等地生成一張報價單**（`pmm_quote`）：
    - 幂等保護：若 `pmm_quote.req_sign_code = 請購單.sign_code` 已存在，則直接 return；
    - 報價單頭欄位來自請購單頭（reqReason / warehouse / warehouseName / reqDate / reqSignCode）；
    - 報價單明細逐筆對應請購明細：reqItem 從 1 累加、`status=1`（報價中）；
    - 報價單頭 status = "1"（報價中）、`processStatus = 待處理`；
    - 若報價選單也綁定流程（`FormPathUniqueEnum.QUOTATION.path = "pbp"`）→ 同步發起 BPM 流程。
31. 作為**請購單管理員**，已歸檔的請購單若 `processInstanceId 為空` 不可再修改（拋 `PUR_ARCHIVED_CANNOT_UPDATE`）；若仍有流程實例，依然可由 listener 來覆寫狀態。

### 報價管理（Excel #32）

32. 作為**採購人員**，我想看到由請購單自動生成的報價單，並為每筆明細**選定預設廠商（defaultSupplier）** 與**單價（latestQuotePerPack / latestQuotePerKgL）**。
33. 作為**採購人員**，我想呼叫 `GET /pmm/quote/getOrderHisList?prodCode=...` 查該品號的歷史採購記錄（`pmm_pur_order_detail` 中的歷史單價），輔助議價判斷。
34. 作為**採購人員**，我想在報價歸檔前，系統必須校驗每一筆明細都已選定 `defaultSupplier`，否則拋 `QUOTE_DEFAULT_NOT_EXISTS`。
35. 作為**採購人員**，我想送出報價單；通過 BPM 後 `QuoteStatusListener` 觸發歸檔。
36. 作為**系統**，當報價單歸檔（`processStatus = 已歸檔`）時，我必須：
    - 將報價單頭 `status` 更新為 "2"（採購中）、所有明細的 `status` 也更新為 "2"；
    - **依廠商分組（mfrId）拆出多張採購單**（`pmm_pur_order`）；
    - 每張採購單頭從報價組第一筆生成（quoteSignCode、mfrId、mfrName、付款資訊等），呼叫 `MenuService.generateSignCode("採購單管理")`；
    - 每筆採購明細：
      - `purQty = ⌈purQuantity ÷ singlePackCount⌉`（請購量 ÷ 每箱量，**向上取整**）；
      - `lineAmount = purQty × unitPrice`（小數 3 位、四捨五入）；
      - `expectedDeliveryDate = requiredDate`（請購需求日期 → 採購預定交期）；
    - 採購單頭 `untaxedAmount = Σ lineAmount`；
    - 稅金計算：`taxType` 為 `0`（營業稅）→ `totalAmount = untaxedAmount × 1.05`；`1`（零稅率）/ `2`（免稅）→ `totalAmount = untaxedAmount`；`taxAmount = totalAmount − untaxedAmount`；
    - 若採購選單綁定流程（`FormPathUniqueEnum.PURCHASING.path = "pmt"`）→ 為每張採購單同步發起 BPM。

> **注意（程式現況）**：`QuoteServiceImpl.createQuote()` 在建立報價單時呼叫的是 `PURCHASE_REQUISITION.path`（請購單流程鍵），看起來是 bug；正常應為 `QUOTATION.path = "pbp"`。記錄於 [Further Notes](#further-notes)。

### 採購單管理（Excel #33）

37. 作為**採購人員**，我想看到由報價單依廠商拆分的採購單清單（`/pmm/pur-order/page`），每筆顯示 `mfrCode`（從 `mfrId` 查 `pmm_vendor_quote_maintenance` 取廠商代號）。
38. 作為**採購人員**，我想修改採購單明細的數量、單價、預定交期、運費、稅型等資訊。
39. 作為**採購人員**，我想送出採購單；通過 BPM 後 `PurOrderStatusListener` 觸發歸檔。
40. 作為**系統**，當採購單歸檔（`processStatus = 已歸檔`）時，我必須**幂等地生成一張結轉驗收單**（`pmm_pur_forward`）：
    - 幂等保護：若 `pmm_pur_forward.order_sign_code = 採購單.sign_code` 已存在，則 return；
    - 結轉單頭由 `purOrderDetailMapper.generateForwardHead(orderId)` 產生（mfrId、warehouse、預定交期區間 expectedStartDate/EndDate、orderSignCode、reqSignCode）；
    - 結轉明細由 `purOrderDetailMapper.generateForwardDetail(orderId)` 產生：核心欄位 `purQty`（採購數量）、`approvedQty = 0`、`unapprovedQty = purQty`、`transitQty = purQty`（在途數量）、`inspectedQty = 0`、`acceptanceStatus = "0"`（待結轉）；
    - 結轉單號 `signCode = generateSignCode("結轉驗收作業")`；
    - 若結轉選單綁定流程（`FormPathUniqueEnum.PUR_FORWARD.path = "irc"`）→ 同步發起 BPM。
41. 作為**採購單管理員**，已歸檔的採購單若 `processInstanceId 為空` 不可再修改（拋 `PUR_ORDER_ARCHIVED_CANNOT_UPDATE`）。
42. 作為**採購人員**，我想匯出採購單 Excel（`/export-excel`），匯出時 `pageSize = NONE`（取全部）。

### 結轉驗收作業（Excel #34）

43. 作為**驗收人員**，我想分頁查看待結轉的結轉驗收單，含廠商、交貨地點、預定交期區間。
44. 作為**驗收人員**，我想為每筆結轉明細填寫**本次驗收數量（inspectedQty）**；可分批多次結轉同一張採購單。
45. 作為**驗收人員**，我想呼叫 `PUT /pmm/pur-forward/transformPurForwardToAcceptance?id=...` 將結轉單轉成驗收確認單；系統會：
    - 為每筆 `inspectedQty > 0` 的結轉明細生成一筆 `pmm_pur_acceptance_detail`，其中 `stockQty = inspectedQty`、`shortageQty = 0`；
    - 結轉明細更新：
      - `transitQty = transitQty − inspectedQty`（在途數量扣減）；
      - `approvedQty = purQty − transitQty`（已驗收 = 採購 − 在途）；
      - `inspectedQty = 0`（清空本次）；
      - `acceptanceStatus`：`purQty == approvedQty → "2"`（已關閉）；`purQty > approvedQty → "1"`（驗收中）；其他 → `"0"`；
    - 若所有明細皆變為「已關閉」（closedAcceptStatus == detailDOList.size），結轉單頭 `acceptanceStatus = "2"`；
    - 同時建立驗收確認單頭（`pmm_pur_acceptance`），`subject = "由結轉驗收單生成 - {結轉signCode}"`、`forwardSignCode = 結轉signCode`、`processStatus = 待處理`；
    - 若驗收選單綁定流程（`FormPathUniqueEnum.PUR_ACCEPTANCE.path = "pam"`）→ 同步發起 BPM。
46. 作為**驗收人員**，我想對某筆明細按下**強制結案（forceClosed = "1"）**並填寫理由（forceClosedReason）；當該結轉單的「所有」明細都被標記強制結案時，結轉單頭 `acceptanceStatus` 設為「2」（已關閉）。
47. 作為**簽核人**，我想在 `/pmm/pur-forward/todo-page` 看到我的結轉待辦；通過後 `PurForwardStatusListener` 將狀態切為「已歸檔」。
48. 作為**結轉單管理員**，已歸檔的結轉單若 `processInstanceId 為空` 不可再修改（拋 `PUR_FORWARD_ARCHIVED_CANNOT_UPDATE`）。
49. 作為**驗收人員**，我想匯出結轉單 Excel（`/export-excel`）— **目前匯出資料源固定為空 ArrayList，待修復**（記於 [Further Notes](#further-notes)）。

### 驗收確認作業（Excel #35）

50. 作為**驗收人員**，我想看到由結轉單自動生成的驗收確認單（`pmm_pur_acceptance`），與其明細（`pmm_pur_acceptance_detail`）；明細含 prodCode、本次驗收數量、入庫數量、短缺數量、倉庫 ID。
51. 作為**驗收人員**，我想修改驗收明細，例如調整 `stockQty`、補填 `shortageQty`、`remark`。
52. 作為**驗收人員**，我想送出驗收確認單；通過 BPM 後 `PurAcceptanceStatusListener` 觸發歸檔。
53. 作為**系統**，當驗收確認單歸檔（`processStatus = 已歸檔`）時，我必須**自動觸發 WHS 入庫**：
    - 透過 `purAcceptanceDetailMapper.selectStockInData(id)` 一次性查出驗收頭/明細/倉庫資訊（`PurAcceptanceStockInVO`）；
    - 建立**入庫單頭（`whs_stock_record_head`）**：
      - `signCode = generateSignCode("入庫作業管理")`、`processStatus = 已歸檔`、`stockReason = "SW05"`、`stockType = 1`（入庫）、`sourceSignCode = 驗收 signCode`、`subject = "驗收入庫 - {驗收 signCode}"`、`remark = "由驗收單自動生成"`；
      - 倉庫資訊（area / areaName / warehouseType / warehouseTypeName / warehouse / warehouseName / warehouseId）取自第一筆有完整倉庫資料的明細；
    - 為每筆驗收明細建立**入庫明細（`whs_stock_record`）**：`stockReason = "SW05"`、`stockType = 1`、`standardQuantity = stockQty`、`invNumChange = stockQty`；
    - 批次 `stockRecordMapper.insert()` + `stockRecordService.batchProcessStockRecords()` 更新庫存。
54. 作為**驗收人員**，我想 `GET /pmm/pur-acceptance/vendor-quote-dropdown` 取得所有廠商報價維護的下拉清單。
55. 作為**驗收人員**，我想分頁查看驗收清單、`/todo-page` 我的待辦，並可匯出 Excel。

### 共同行為（橫切）

56. 作為**任何 PMM 單據**，狀態都遵循同一個枚舉 `ProcessStatusEnums`：`待處理 / 待簽核 / 已歸檔 / 已作廢`。
57. 作為**任何 PMM 單據**，BPM 流程啟動皆由 `MenuFlowProcessInstanceHelper.createProcessInstanceIfFlowOpen(userId, formPath, headerId)` 統一處理；如選單未綁定流程則直接略過 BPM。
58. 作為**任何 BPM Listener**，businessKey 格式皆為 `"{formPath}:{headerId}"`；Listener 內以前綴判斷是否屬於自己的業務。
59. 作為**任何 PMM 單據**，「已歸檔」且 `processInstanceId 為空」者皆禁止再次更新（避免人工繞過流程）。
60. 作為**API 消費者**，所有列表 `/page` 與 `/todo-page` 都接收 `PageParam`、`processStatus`、`processInstanceStatus` 等參數；匯出時將 `pageSize` 設為 `PAGE_SIZE_NONE`。

---

## Implementation Decisions

> 本節不重複貼程式碼路徑（會過時）。要找實作位置請見「[功能 ↔ 程式碼對照表](#功能--程式碼對照表)」。

### 1. 模組邊界與子域劃分

PMM 模組固定切成 7 個子域，每個子域有自己的 `controller / service / dal/dataobject / dal/mysql / listener` 五段結構：

| 子域 | 業務語言 | API 前綴 | 權限碼前綴 |
|---|---|---|---|
| `vdm` | 廠商資料 | `/pmm/vdm` | `pmm:mfr-basic-final:*` |
| `vqm` | 廠商報價 | `/pmm/vqm` | `pmm:vendor-quote-maintenance:*` |
| `purreq` | 請購 | `/pmm/pur-req` | `pmm:pur-req:*` |
| `quote` | 報價 | `/pmm/quote` | `pmm:quote:*` |
| `purorder` | 採購 | `/pmm/pur-order` | `pmm:pur-order:*` |
| `purforward` | 結轉驗收 | `/pmm/pur-forward` | `pmm:pur-forward:*` |
| `puracceptance` | 驗收確認 | `/pmm/pur-acceptance` | `pmm:pur-acceptance:*` |

新增第 8 個子域以前，先確認其無法被現有 7 個吸收。

### 2. ER Model — 7 階段採購鏈

```
┌───────────────────────────────────────────────────────────────┐
│  廠商主檔 (pmm_mfr_basic_final)                                │
│   ├─ pmm_mfr_basic_lcn_final  (聯絡人, mfr_basic_id)           │
│   ├─ pmm_mfr_basic_rcb_final  (收款銀行, mfr_basic_id)         │
│   └─ pmm_mfr_basic_trd_final  (交易資料 / 付款條件, mfr_basic_id)│
└───────────────────────────────────────────────────────────────┘
                       ▲ mfr_id（字串代號，鬆耦合）
                       │
┌───────────────────────────────────────────────────────────────┐
│  廠商報價 (pmm_vendor_quote_maintenance)                       │
│   └─ pmm_vendor_quote_maintenance_detail (vendor_quote_id)     │
└───────────────────────────────────────────────────────────────┘
                       ▲ prod_code / mfr_id
                       │
┌───────────────────────────────────────────────────────────────┐
│  ┌─ 請購 (pmm_pur_req)──────signCode──┐                        │
│  │   └─ pmm_pur_req_detail            │                        │
│  ▼                                    │                        │
│  ┌─ 報價單 (pmm_quote)                │                        │
│  │   req_sign_code  ──────────────────┘                        │
│  │   └─ pmm_quote_detail (default_supplier = 廠商 mfrId)        │
│  ▼  (依廠商分組)                                                │
│  ┌─ 採購單 (pmm_pur_order)                                      │
│  │   quote_sign_code, mfr_id, payment_id                       │
│  │   └─ pmm_pur_order_detail (req_sign_code, req_item)         │
│  ▼                                                              │
│  ┌─ 結轉驗收單 (pmm_pur_forward)                                │
│  │   order_sign_code, req_sign_code, mfr_id                    │
│  │   └─ pmm_pur_forward_detail (pur_qty, approved_qty,         │
│  │                              transit_qty, inspected_qty,    │
│  │                              acceptance_status, force_closed)│
│  ▼ (PUT /transformPurForwardToAcceptance)                       │
│  ┌─ 驗收確認單 (pmm_pur_acceptance)                             │
│  │   forward_sign_code, mfr_id                                 │
│  │   └─ pmm_pur_acceptance_detail (order_sign_code,            │
│  │                                 inspected_qty, stock_qty,   │
│  │                                 shortage_qty, warehouse_id) │
│  ▼ (歸檔自動入庫)                                                │
└──┴─→  whs_stock_record_head + whs_stock_record  (stock_reason=SW05)
```

**關鍵 — 用 `signCode` 字串鬆耦合，不用 FK**：
- `pmm_quote.req_sign_code` → `pmm_pur_req.sign_code`
- `pmm_pur_order.quote_sign_code` → `pmm_quote.sign_code`
- `pmm_pur_order_detail.req_sign_code` → `pmm_pur_req.sign_code`（保留請購回溯）
- `pmm_pur_forward.order_sign_code` → `pmm_pur_order.sign_code`
- `pmm_pur_forward.req_sign_code` → `pmm_pur_req.sign_code`
- `pmm_pur_acceptance.forward_sign_code` → `pmm_pur_forward.sign_code`
- `pmm_pur_acceptance_detail.order_sign_code` → `pmm_pur_order.sign_code`
- `whs_stock_record.source_sign_code` → `pmm_pur_acceptance.sign_code`

> **設計理由（推測）**：signCode 字串化讓單據可跨模組引用，無需把外鍵反向暴露到所有上游表；但代價是「改 signCode 規則」要全鏈搜尋。

### 3. 完整資料表清單

#### 廠商主檔 4 表

##### `pmm_mfr_basic_final`（廠商主表）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK（pmm_mfr_basic_final_id_seq） | 主鍵 |
| sign_code | VARCHAR | 單據編號 |
| process_status | VARCHAR | 單據狀態（`ProcessStatusEnums`）|
| mfr_id | VARCHAR | 廠商代號（業務唯一鍵）|
| mfr_abrname | VARCHAR | 廠商簡稱 |
| mfr_type | INT | 廠商類別（0=供應商, 1=一般行政廠商）|
| is_controlled | BOOLEAN | 是否為管制廠商 |
| is_head_office | BOOLEAN | 是否為總公司（影響「公司群下拉」）|
| mfr_name | VARCHAR | 廠商全名 |
| tax_id_no | VARCHAR | 統一編號 |
| tax | INT | 計稅方式（0=營業稅, 1=零稅率, 2=免稅）|
| tel / fax | VARCHAR | 公司電話 / 傳真 |
| boss | VARCHAR | 公司負責人 |
| company_group | VARCHAR | 公司群（連結到 isHeadOffice=true 的廠商）|
| address | VARCHAR | 公司地址 |
| supplies | VARCHAR | 供應物品 |
| payment_date | INT | 結帳日（每月幾日）|
| remarks | VARCHAR | 備註 |
| money_type | VARCHAR | 幣別 |
| process_instance_id | VARCHAR | Flowable 流程實例 ID |

##### `pmm_mfr_basic_lcn_final`（聯絡人）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| mfr_basic_id | BIGINT FK→`pmm_mfr_basic_final` | 主表 ID |
| item | INT | 項次 |
| contact_person | VARCHAR | 聯絡人 |
| tel_extension | VARCHAR | 電話分機 |
| tel_phone | VARCHAR | 電話 |
| email | VARCHAR | Email |
| is_default | BOOLEAN | 是否預設 |

##### `pmm_mfr_basic_rcb_final`（收款銀行）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| mfr_basic_id | BIGINT FK→`pmm_mfr_basic_final` | 主表 ID |
| item | INT | 項次 |
| bank_id | VARCHAR | 銀行代碼 |
| bank_name | VARCHAR | 銀行名稱 |
| bank_acct | VARCHAR | 銀行帳號 |
| bank_acct_holder_name | VARCHAR | 戶名 |
| bank_addr | VARCHAR | 銀行地址 |
| is_default | BOOLEAN | 是否預設 |

##### `pmm_mfr_basic_trd_final`（交易資料 / 付款條件）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| mfr_basic_id | BIGINT FK→`pmm_mfr_basic_final` | 主表 ID |
| item | INT | 項次 |
| pay_id | VARCHAR | 付款代碼 |
| pay_meth | VARCHAR | 付款方式 |
| pay_term | VARCHAR | 付款條件 |
| cycle | VARCHAR | 週期（DAY / MONTH）|
| cycle_multiplier | INT | 週期乘數 |
| cycle_day | INT | 週期屬日 |
| status | INT | 啟用旗標（0=停用, 1=啟用，預設 1）|

#### 廠商報價 2 表

##### `pmm_vendor_quote_maintenance`（報價主表）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| sign_code | VARCHAR | 單據編號 |
| process_status | VARCHAR | 狀態 |
| mfr_id | VARCHAR | 廠商代號 |
| mfr_name | VARCHAR | 廠商名稱（冗餘）|
| subject | VARCHAR | 主旨 |
| money_type | VARCHAR | 幣別 |
| quote_effect_date_st / ed | TIMESTAMP | 報價有效起訖 |
| process_instance_id | VARCHAR | Flowable 流程實例 ID |

##### `pmm_vendor_quote_maintenance_detail`（報價明細）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| vendor_quote_id | BIGINT FK→`pmm_vendor_quote_maintenance` | 主表 ID |
| item | INT | 項次 |
| category | INT | 類別（食材/包材）|
| prod_code | VARCHAR | 品號 |
| mfr_product_name | VARCHAR | 廠商品名 |
| mfr_pack_unit | BIGINT | 廠商包裝單位 ID |
| latest_quote_per_pack | DECIMAL | 最新報價（NTD/包裝）|
| latest_quote_per_kg_l | DECIMAL | 最新報價（NTD/單位 kg.l）|
| single_pack_count | DECIMAL | 單一包裝量 |
| single_pack_count_unit | BIGINT | 單位 ID |
| single_count_measure | DECIMAL | 單一規格 |
| single_count_measure_unit | BIGINT | 單一規格單位 ID |
| status | INT | 狀態 |
| create_department | BIGINT | 建立人員部門 |
| use_store_region_id | VARCHAR | 適用門市 ID |
| use_store_region | VARCHAR | 適用門市名稱 |
| use_delivery_type | VARCHAR | 預設物流類型（連結 `pdm_logistics_type`）|
| before_purchase_date | INT | 採購前置日期 |
| save_date | INT | 保存日期 |
| moq | DECIMAL | 最小報價量 |

#### 請購 2 表

##### `pmm_pur_req`（請購單頭）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| sign_code | VARCHAR | 單據編號（"請購單管理" 規則）|
| req_reason | VARCHAR | 請購原因 |
| warehouse | VARCHAR | 交貨地點代號 |
| warehouse_name | VARCHAR | 交貨地點名稱 |
| req_date | TIMESTAMP | 需求日期 |
| subject | VARCHAR | 主旨 |
| weight_factor | VARCHAR | 加權係數（試算時使用）|
| process_status | VARCHAR | 流程狀態 |
| process_instance_id | VARCHAR | Flowable 流程實例 ID |

##### `pmm_pur_req_detail`（請購明細）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| pur_req_id | BIGINT FK→`pmm_pur_req` | 所屬請購單 |
| prod_code | VARCHAR | 品號 |
| current_stock_num | DECIMAL | 目前庫存量（試算填入）|
| safe_stock | DECIMAL | 安全存量（試算填入）|
| standard_quantity | DECIMAL | 請購計數 |
| unit | BIGINT | 單位 ID |
| remark | VARCHAR | 備註 |
| warehouse_id | BIGINT FK→`whs_warehouse` | 倉庫 ID |

#### 報價 2 表

##### `pmm_quote`（報價單頭）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| sign_code | VARCHAR | 單據編號（"報價管理" 規則）|
| req_reason | VARCHAR | 請購原因（從請購複製）|
| warehouse / warehouse_name | VARCHAR | 交貨地點 |
| req_date | TIMESTAMP | 需求日期 |
| req_sign_code | VARCHAR | 對應請購單 sign_code（鬆耦合）|
| status | VARCHAR | 狀態（"1"=報價中, "2"=採購中）|
| process_status | VARCHAR | 流程狀態 |
| process_instance_id | VARCHAR | Flowable 流程實例 ID |

##### `pmm_quote_detail`（報價明細）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| quote_id | BIGINT FK→`pmm_quote` | 所屬報價單 |
| prod_code | VARCHAR | 品號 |
| standard_quantity | DECIMAL | 請購量 |
| total_standard_quantity | DECIMAL | 總採購計數 |
| remark | VARCHAR | 備註 |
| status | VARCHAR | 狀態 |
| default_supplier | BIGINT | 預設廠商（指向 `pmm_vendor_quote_maintenance.id`）— 歸檔前必填 |
| latest_quote_per_pack | DECIMAL | 最新報價（NTD/包裝）|
| latest_quote_per_kg_l | DECIMAL | 最新報價（NTD/單位）|
| req_item | VARCHAR | 對應請購單項次 |
| req_sign_code | VARCHAR | 對應請購單 sign_code |

#### 採購 2 表

##### `pmm_pur_order`（採購單頭）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| sign_code | VARCHAR | 單據編號 |
| purchase_date | TIMESTAMP | 採購日期 |
| subject | VARCHAR | 主旨 |
| remark | VARCHAR | 備註 |
| quote_sign_code | VARCHAR | 對應報價單 sign_code |
| mfr_id | BIGINT | 廠商 ID（指向 `pmm_vendor_quote_maintenance.id`）|
| mfr_name | VARCHAR | 廠商名稱 |
| untaxed_amount | DECIMAL | 未稅金額 |
| tax_type | VARCHAR | 計稅方式（0=營業稅, 1=零稅率, 2=免稅）|
| tax_amount | DECIMAL | 稅額 |
| total_amount | DECIMAL | 稅後金額 |
| payment_id | BIGINT | 付款代碼 ID（指向 `pmm_mfr_basic_trd_final.id`）|
| cycle / cycle_multiplier / cycle_day | VARCHAR/INT/INT | 付款週期 |
| delivery_cost | DECIMAL | 運費 |
| process_status | VARCHAR | 流程狀態 |
| process_instance_id | VARCHAR | Flowable 流程實例 ID |

##### `pmm_pur_order_detail`（採購明細）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| pur_order_id | BIGINT FK→`pmm_pur_order` | 所屬採購單 |
| req_sign_code | VARCHAR | 請購單 sign_code |
| req_item | VARCHAR | 請購項次 |
| prod_code | VARCHAR | 品號 |
| standard_quantity | DECIMAL | 請購量 |
| single_count_measure / unit | — | 單一計數計量 |
| pur_amount / pur_amount_unit | — | 採購計量 |
| pur_quantity / pur_quantity_unit | — | 採購計數 |
| pur_single_count_measure / unit | — | 採購單一計數計量 |
| mfr_unit | VARCHAR | 廠商單位 |
| unit_price | DECIMAL | 單價 |
| pur_qty | DECIMAL | 採購數量（箱數，向上取整）|
| line_amount | DECIMAL | 金額（未稅）|
| required_date | TIMESTAMP | 需求日期 |
| expected_delivery_date | TIMESTAMP | 預定交期 |
| warehouse / warehouse_name | VARCHAR | 交貨地點 |
| remark | VARCHAR | 備註 |

#### 結轉驗收 2 表

##### `pmm_pur_forward`（結轉單頭）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| sign_code | VARCHAR | 單據編號（"結轉驗收作業"）|
| mfr_id | BIGINT | 廠商 ID |
| mfr_name | VARCHAR | 廠商名稱 |
| expected_start_date / end_date | TIMESTAMP | 預定交期區間 |
| warehouse / warehouse_name | VARCHAR | 交貨地點 |
| req_sign_code | VARCHAR | 請購單 sign_code |
| order_sign_code | VARCHAR | 採購單 sign_code |
| process_status | VARCHAR | 流程狀態 |
| process_instance_id | VARCHAR | Flowable 流程實例 ID |
| acceptance_status | VARCHAR | 結轉狀態（"0"=待結轉, "1"=部分, "2"=已關閉）|
| attribute | VARCHAR | 屬性（業務語意待補）|

##### `pmm_pur_forward_detail`（結轉明細）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| pur_forward_id | BIGINT FK→`pmm_pur_forward` | 所屬結轉單 |
| req_sign_code / order_sign_code | VARCHAR | 上游 signCode |
| attribute | VARCHAR | 屬性 |
| warehouse / warehouse_name | VARCHAR | 交貨地點 |
| prod_code | VARCHAR | 品號 |
| mfr_unit / mfr_unit_name | BIGINT / VARCHAR | 廠商單位 |
| pur_qty | DECIMAL | 採購數量（總量）|
| approved_qty | DECIMAL | 已驗收數量 |
| unapproved_qty | DECIMAL | 未驗收數量 |
| transit_qty | DECIMAL | 在途數量 |
| inspected_qty | DECIMAL | 本次驗收數量（轉驗收後清空）|
| force_closed | VARCHAR | 強制結案（"1" = 強制結案）|
| force_closed_reason | VARCHAR | 強制結案理由 |
| acceptance_status | VARCHAR | 明細狀態（"0/1/2"）|

#### 驗收 2 表

##### `pmm_pur_acceptance`（驗收單頭）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| sign_code | VARCHAR | 單據編號（"驗收確認作業"）|
| mfr_id | BIGINT | 廠商 ID |
| mfr_name | VARCHAR | 廠商名稱 |
| warehouse / warehouse_name | VARCHAR | 交貨地點 |
| forward_sign_code | VARCHAR | 來源結轉單 sign_code |
| accept_date | TIMESTAMP | 驗收日期 |
| subject | VARCHAR | 主旨（預設 "由結轉驗收單生成 - {forwardSignCode}"）|
| process_status | VARCHAR | 流程狀態 |
| process_instance_id | VARCHAR | Flowable 流程實例 ID |

##### `pmm_pur_acceptance_detail`（驗收明細）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| pur_acceptance_id | BIGINT FK→`pmm_pur_acceptance` | 所屬驗收單 |
| order_sign_code | VARCHAR | 來源採購單 sign_code |
| prod_code | VARCHAR | 品號 |
| mfr_unit / mfr_unit_name | BIGINT / VARCHAR | 廠商單位 |
| inspected_qty | DECIMAL | 本次驗收數量 |
| stock_qty | DECIMAL | 入庫數量（預設 = inspected_qty）|
| shortage_qty | DECIMAL | 短缺數量（預設 = 0）|
| warehouse_id | BIGINT FK→`whs_warehouse` | 倉庫 ID |
| remark | VARCHAR | 備註 |

### 4. 狀態機（四狀態）與 BPM 綁定

```
                ┌──────────┐
                │  待處理   │  ←─ 新建單時的初始狀態（除「轉驗收」生成的單也是「待處理」）
                └─────┬────┘
   送出簽核（若選單綁定流程）       直接歸檔（若選單未綁流程）
                │                       │
                ▼                       ▼
        ┌──────────┐               ┌──────────┐
        │  待簽核   │ ──→ Listener  │  已歸檔   │ ←┐ 已歸檔且無 process_instance_id 不可再改
        └────┬─────┘  APPROVE      └────┬─────┘  │
             │                                    │
             │ REJECT / CANCEL（目前 Listener 預留空）│
             ▼                                    │
        ┌──────────┐                              │
        │  待處理   │ ─────────────────────────────┘
        └──────────┘

        手動切換（vdm 有 /update-status 端點）：─→ 已作廢
```

每個 PMM 單據獨立綁定一條 Flowable 流程，businessKey 格式 `"{formPath}:{headerId}"`；APPROVE 時 Listener 自動將 `processStatus` 寫成「已歸檔」，並觸發下一段業務（請購→生成報價單、報價→生成採購單、採購→生成結轉、結轉→無自動、驗收→入庫）。

### 5. BPM Form Path 對照

| 子域 | `FormPathUniqueEnum` | path 值 |
|---|---|---|
| 廠商 | `VENDOR` | `vdm` |
| 廠商報價 | `VENDOR_QUOTE_MAINTENANCE` | `vendor-quote-maintenance` |
| 請購 | `PURCHASE_REQUISITION` | `prm` |
| 報價 | `QUOTATION` | `pbp` |
| 採購 | `PURCHASING` | `pmt` |
| 結轉驗收 | `PUR_FORWARD` | `irc` |
| 驗收確認 | `PUR_ACCEPTANCE` | `pam` |

### 6. 自動生成規則（幂等性）

| 觸發 | 目標 | 幂等鍵 | 失敗策略 |
|---|---|---|---|
| 請購歸檔 → 報價單 | `pmm_quote` | `quote.req_sign_code = purReq.sign_code` 已存在則 return | 程式碼層 if-check（非 DB unique）|
| 報價歸檔 → 多張採購單 | `pmm_pur_order`（依 mfrId 分組）| 程式碼層無顯式校驗（依 listener 只在 archived 翻轉時觸發）| 需業務確認 |
| 採購歸檔 → 結轉驗收單 | `pmm_pur_forward` | `purForward.order_sign_code = purOrder.sign_code` 已存在則 return | 程式碼層 if-check |
| 結轉「轉驗收」(API) → 驗收確認單 | `pmm_pur_acceptance` | 無幂等鍵（每按一次 API 都建立一張新驗收單） | 業務上由 `inspected_qty > 0` 控制；無 inspected_qty 的明細不生成驗收明細 |
| 驗收歸檔 → WHS 入庫 | `whs_stock_record_head` + `whs_stock_record` | 無幂等鍵 | 倚賴使用者只歸檔一次；若多次更新 archived 將重複入庫（風險見 [Further Notes](#further-notes)） |

### 7. 採購量與稅金公式還原

```
# 報價歸檔 → 採購明細（QuoteServiceImpl.generateNewPurOrder）
purQty       = ⌈purQuantity ÷ singlePackCount⌉   （向上取整）
lineAmount   = purQty × unitPrice                 （scale=3, HALF_UP）
untaxedAmount = Σ lineAmount

# 稅金（taxType）
if taxType == "0":               # 營業稅
    totalAmount = untaxedAmount × 1.05
else:                            # 1=零稅率, 2=免稅
    totalAmount = untaxedAmount
taxAmount = totalAmount - untaxedAmount
```

```
# 請購試算（PurReqServiceImpl.getStockCurrentPage）
if weightFactor != null and safeStock != null and currentStockNum != null:
    standardQuantity = (safeStock - currentStockNum) × weightFactor
```

```
# 結轉「轉驗收」（PurForwardServiceImpl.transformPurForwardToAcceptance）
for detail in details:
    if inspectedQty > 0:
        new acceptance_detail:
            stockQty   = inspectedQty
            shortage   = 0
        transitQty   = transitQty - inspectedQty
        approvedQty  = purQty - transitQty
        inspectedQty = 0
    acceptance_status:
        purQty == approvedQty → "2"  (已關閉)
        purQty  > approvedQty → "1"  (驗收中)
        else                  → "0"
if closedCount == len(details):  pur_forward.acceptance_status = "2"
```

### 8. 跨模組依賴清單

| PMM 子域 | 依賴模組 | 用途 |
|---|---|---|
| `purreq` | WHS (`whs_stock`, `whs_warehouse`)、PDM (`pdm_ingredient_specs`) | 試算庫存與安全存量、單位 |
| `vqm` | PDM (`pdm_unit_def`, `pdm_unit_conv`, `pdm_logistics_type`, `pdm_packing_materials_dtl`)、BurgerKing 中繼 API (`AreaGroupHierarchyVO`) | 換算單一計數計量、適用門市下拉 |
| `quote` | PDM (`pdm_ingredient_specs`)（撈食材名）| 歷史採購記錄關聯 |
| `purorder` | PMM 自身（`pmm_mfr_basic_trd_final`, `pmm_vendor_quote_maintenance`）| 付款條件、廠商代號 |
| `puracceptance` | WHS (`whs_stock_record_head`, `whs_stock_record`, `StockRecordService`) | 驗收歸檔 → 自動入庫 |

### 9. 不要再做的事

- **不要把 7 個子域合併** — 它們各自有獨立的狀態機與 BPM 流程，合併會破壞「APPROVE → listener → 下一張單」的單一職責。
- **不要把 signCode 換成 FK** — 跨模組鬆耦合是目前設計選擇；若要強約束，先評估 WHS 入庫與 BPM Listener 的引用。
- **不要在 PMM 內補建「請購計劃管理」與「原料物需求行事曆」** — 它們屬於 PDM/需求集合（見 [`DEMAND_AGGREGATION_PRD.md`](DEMAND_AGGREGATION_PRD.md)）。本模組只負責下游消費。

---

## Testing Decisions

### 好測試的判準

- 測**外部行為**而非實作細節：給定一個請購單頭+明細，呼叫 `updatePurReq` 並把 `processStatus` 設為「已歸檔」→ 驗證 `pmm_quote` 多了一筆且明細數對齊；驗證重複呼叫不會二度生成（幂等）。
- **不要**測 BeanUtils 轉換、Mapper insertBatch 內部細節、ProcessStatusEnums 的 toString。
- 寫**整合測試**而非單元測試：PMM 的核心價值在「跨單據聯動」，mock 掉 mapper 就失去意義。

### 應測模組（建議優先序）

| 優先序 | 模組 | 場景 |
|---|---|---|
| P0 | 請購歸檔 → 報價單 | 幂等性（重複歸檔不重生）、明細映射、BPM 流程實例 ID 回寫 |
| P0 | 報價歸檔 → 多張採購單 | 依 mfrId 分組正確、`purQty` 向上取整、`untaxedAmount` 與 `taxType=0/1/2` 三種稅金 |
| P0 | 採購歸檔 → 結轉驗收單 | 幂等性、結轉明細的 transitQty / approvedQty 初值 |
| P1 | 結轉「轉驗收」API | 部分結轉（inspected < pur）、強制結案、acceptance_status 三種狀態 |
| P1 | 驗收歸檔 → WHS 入庫 | StockRecordHead + StockRecord 寫入、`stockReason=SW05`、stock 更新 |
| P2 | 廠商匯入 | Excel 4 sheet 匯入後子表完整、updateSupport 覆蓋邏輯 |
| P2 | 廠商報價匯入與單價計算 | calculate-unit-quote 等 3 個計算端點 |
| P3 | BPM REJECT / CANCEL | 目前 Listener 為預留空，需先補實作再寫測試 |

### 既有測試參考

目前 `erp-spring` 無自動化測試（見 CLAUDE.md「測試 — 目前無自動化測試，靠手動 Swagger UI 驗證」）。可參照 PDM 的 `DemandForecastServiceImpl` 試算邏輯被 Swagger UI 驗證的模式：先用 `application-local.yaml` 連測試庫，再以 Postman/Swagger 跑 7 階段的端到端 happy path。

---

## Out of Scope

以下項目雖在 Excel 採購管理模組清單中，但**不屬於 PMM 程式碼模組**，**不在本 PRD 範圍**：

- **Excel #29「請購計劃管理」** — 實際對應 PDM 的「需求預測設定」（`crg_demand_forecast_config` / `crg_demand_forecast_config_scope` / `DemandForecastConfigController`），規格見 [`DEMAND_AGGREGATION_PRD.md`](DEMAND_AGGREGATION_PRD.md)。
- **Excel #30「原料物需求行事曆」** — 實際對應 PDM 的「原物料需求行事曆」（`pdm_raw_material_demand_head` / `pdm_raw_material_demand_date_list` / `pdm_raw_material_demand_detail`），規格見 [`DEMAND_AGGREGATION_PRD.md`](DEMAND_AGGREGATION_PRD.md)；目前 PMM 與其鬆耦合方式為 signCode 字串掛載至 `demand_relation_doc` / `temp_relation_doc`，**但沒有「自動把需求行事曆轉成 PMM 請購單」的程式碼**，需另列規格。
- **Excel #1～#26、#36～#69** — 屬於系統管理、PDM、需求集合、庫存、物流、店長功能模組，分別由 SYSTEM_PRD、PDM_PRD、DEMAND_AGGREGATION_PRD 與待寫的 WHS_PRD、LOGISTICS_PRD、STORE_PRD 處理。
- **前端 UI 規格** — 本 PRD 僅還原後端規格與 API；UI 流程、欄位顯示邏輯、按鈕權限等由前端 PRD 另行整理。
- **BPM 流程模型本身** — 各單據的審批節點、簽核人選擇策略（15+ 種 candidate strategy）屬於 BPM 模組職責。
- **BHM 模組（已凍結）** — 不在本 PRD 範圍。

---

## Further Notes

### 已知 bug / 待修

1. **`QuoteServiceImpl.createQuote()` 啟動 BPM 時誤用請購流程 path** — 程式碼帶入的是 `FormPathUniqueEnum.PURCHASE_REQUISITION.getPath()`，看似應為 `QUOTATION.getPath()`。需與業務確認後修正。
2. **`PurForwardController.exportPurForwardExcel()` 匯出資料源固定為空 `new ArrayList<>()`** — 真實 query 被註解掉。需補回 `purForwardService.getPurForwardPage(pageReqVO).getList()` 或同等資料來源。
3. **驗收歸檔 → 入庫無幂等鍵** — 若 BPM 多次回送 APPROVE 事件或 listener 多次處理 same `businessKey`，會重複寫入庫單。建議：以 `whs_stock_record_head.source_sign_code = 驗收 signCode` 為幂等鍵。
4. **`getOrderHisList(prodCode)` 拋 `RuntimeException`** — 違反「使用 ServiceExceptionUtil」框架規範（CLAUDE.md §關鍵開發規範 1）。
5. **`PurReqController` 與 `QuoteController` 等多支 GET 端點的 `@RequestParam` 名稱含尾隨空白**（如 `"purReqId "`、`"quoteId "`、`"purForwardId "`、`"purAcceptanceId "`、`"purOrderId "`） — 嚴格說可能造成前端串接困擾，建議統一去除。
6. **報價歸檔 → 採購單**目前**未做幂等保護**（不像請購→報價有 `selectOne` 預檢）— 若 listener 重複觸發 APPROVE 會重生採購單。建議補上 `selectOne(PurOrderDO::getQuoteSignCode, quoteDO.getSignCode())` 預檢。

### 程式碼異味

- 多處 `@TableId` + `@KeySequence(...)` 並用，且明顯被「程式碼生成器」批量產出（DO 檔頭 @author "管理员"、被註解的 Builder field、import 重覆等），維護時請整體清理而非局部編輯。
- `PurAcceptanceDetailDO.warehouseId` 與 `PurForwardDetailDO` 不一致（一個 Long、一個無）— ER 圖時統一指向 `whs_warehouse.id`。
- 多個 Controller 的 `@PreAuthorize` 權限碼跨子域共用同一前綴（例如 `pmm:mfr-basic-final:*`、`pmm:vendor-quote-maintenance:*`）— 與 SYSTEM 模組 `{模組}:{資源}:{動作}` 命名規則一致，無需調整。

### 與 UNKNOWNS.md 的關聯

- **U-2**「DemandForecast 與廠商已歸檔過濾」直接影響 PMM 報價試算的廠商候選；本 PRD 暫保留現況（不過濾），待業務確認後可在 `pmm_vendor_quote_maintenance` query 加 `process_status = '已歸檔'` 條件。
- **U-11**「PMM 各模組 `/todo-page` 端點完整性」— 本 PRD 已列出全部 7 個 `/todo-page` 端點及其 listener，但 BPM 待辦顯示是否正確仍需手動驗證。

### 後續可能擴充（不在本 PRD 範圍）

- 加入「採購歷史價格趨勢」分析（Quote 已有 `getOrderHisList` 雛形）。
- 加入「結轉驗收 → 自動入庫（驗收歸檔 → 直接觸發部分入庫）」省略人工歸檔步驟。
- 加入「請購單合併」：多張請購單合併成一張報價單，提升議價空間。
- 為「請購計劃管理」與「原料物需求行事曆」（PDM）→ PMM 自動轉請購單 建立完整管道。
