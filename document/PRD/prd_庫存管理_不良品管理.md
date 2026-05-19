# PRD｜庫存管理 — 不良品管理

> 來源：逆向自 `kingmaker-module-whs` 後端程式碼（`controller/admin/badproduct/BadProductController.java`、`service/badproduct/`、`dal/dataobject/badproduct/BadProductDO.java`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **倉儲人員 / 店長**。冰箱裡的食材有可能：

- 過期報損
- 配送途中破損 / 解凍
- 設備故障導致整批壞掉
- 廠商交貨品質不良需退回

我建立「不良品單」記錄這些情況，**對應從庫存中扣除**（出庫，stockType=0），有些情境是「廠商換貨」需要記錄入庫（stockType=1）。

### 1.2 我要做什麼

- 建立 / 編輯不良品單（單頭：區域 / 倉名 / 回報日期 / 主旨 / stockType；明細：品號 / 數量 / 不良原因等）
- 走簽核流程
- 根據 stockType 觸發 #40/#41：
  - stockType=0 → 出庫（食材報廢）
  - stockType=1 → 入庫（廠商換貨補進）
- signCode 前綴 `BP` → 由 batchProcessStockRecords 觸發 `updateBadProductStatus` 回寫
- 分頁查詢、待簽分頁、Excel 匯出
- 出入庫來源下拉（出入互查）
- 反查 StockRecord 批次（給 #40/#41 使用）

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 紀錄不良品的來源與處置 | audit、廠商索賠依據 |
| 自動扣減庫存 | 不要再手動建出庫單 |
| 走簽核 | 損益確認 |
| 出庫 / 入庫雙向 | 報廢 vs 廠商換貨補進 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 不良品 CRUD | 主要建單 |
| 與 #40/#41 串接 | 自動扣 / 加庫存 |
| 出入庫來源下拉 | 找對應的歷史單 |
| BPM 簽核 | 內控 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 不良品管理 |
| 所屬模組 | WHS（庫存管理） |
| 兄弟功能 | 入庫 (#40)、出庫 (#41)、調撥 (#42)、盤點 (#43–#46) |
| 主要頁面 | 不良品編輯頁、單頭分頁、待簽分頁、Excel 匯出 |
| 簽核流程 | 有：`/todo-page` 端點存在 |
| signCode 前綴 | `BP`（由 #40/#41 `updateBadProductStatus` 識別） |

---

## 2. 功能目的

不良品是「**WHS 模組中的異常出入庫**」：

1. **異常報廢** — 過期 / 損壞 / 故障，stockType=0
2. **廠商換貨補進** — stockType=1
3. **與正常出入庫分離** — 用獨立單據 + BP 前綴，便於損益分析

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `whs_bad_product`（單頭 / `BadProductDO`） | 單據編號、processStatus、區域、倉名、回報日期、主旨、`stockType`（0/1）、processInstanceId |
| `whs_bad_product_detail`（明細 / `BadProductDetailDO`） | 品號 / 數量 / 不良原因等（DO 未深查） |

### 3.2 stockType 雙向設計

| stockType | 業務情境 |
|---|---|
| 0 | 報廢（食材出庫） |
| 1 | 廠商換貨補進（食材入庫） |

由使用者建單時選擇。

### 3.3 BP 前綴回寫

由 #40/#41 觸發 `updateBadProductStatus(signCode, stockType)`：

```java
BadProductDO badProductDO = badProductMapper.selectOne(BadProductDO::getSignCode, signCode);
badProductDO.setStockType(stockType);
badProductMapper.updateById(badProductDO);
```

來源：#40 `StockRecordServiceImpl.java:267-280`。

### 3.4 出入庫來源下拉

兩個 API：

- `/get-outbound-source-list`：查歷史出庫不良品（給入庫補進時參考）
- `/get-inbound-source-list`：反之

### 3.5 反查 StockRecord 批次

`/get-stock-record-batch-by-sign-code?signCode=&stockType=` → 給 #40/#41 從 BP 單反查批次。

### 3.6 跨模組依賴

- #40/#41：扣 / 加庫存
- BPM：簽核流程

---

## 4. 情境說明

### 4.1 正常流程 — 報廢

倉儲員小李發現信義店冷凍倉有 3 公斤牛肉餅過期：

1. 進入不良品編輯頁
2. 主表：區域 = 北一區、倉名 = 信義冷凍倉、回報日期 = 2026-05-19、主旨「過期報廢」、stockType=0（出庫）
3. 明細：牛肉餅 LB-04、數量 3、不良原因「保存期過期」
4. POST /create → signCode = BP-2026-...
5. 簽核 → 歸檔
6. 系統根據 BP- 反查批次 → #41 batchProcessStockRecords 扣 3 公斤
7. `updateBadProductStatus(BP-..., 0)` → 單頭 stockType 回寫 0（已扣庫）

### 4.2 規則分流 — 廠商換貨

廠商交貨後發現 5 包起司不良，請廠商換貨：

1. 先建「報廢」不良品單（stockType=0）扣 5 包
2. 廠商換 5 包進來 → 建「補進」不良品單（stockType=1）加 5 包

兩張獨立的不良品單，可透過 source-list 端點互查。

---

## 5. 操作流程

```
[使用者進入「不良品管理」]
  │
  ├─ POST /whs/bad-product/create
  ├─ PUT /whs/bad-product/update
  ├─ DELETE /whs/bad-product/delete?id=
  ├─ GET /whs/bad-product/get?id=（BadProductAndDetailVO）
  ├─ GET /whs/bad-product/page、/todo-page、/export-excel
  ├─ POST /whs/bad-product/get-outbound-source-list（出庫來源下拉）
  ├─ POST /whs/bad-product/get-inbound-source-list（入庫來源下拉）
  ├─ GET /whs/bad-product/get-stock-record-batch-by-sign-code?signCode=&stockType=
  └─ GET /whs/bad-product/bad-product-detail/list-by-bad-id?badId=

[簽核歸檔 → 自動扣 / 加庫存]
  └─ #40/#41 batchProcessStockRecords → updateBadProductStatus 回寫
```

---

## 6. 欄位規格

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| signCode | 單據編號（前綴 BP） |
| processStatus | 流程狀態 |
| area / areaName | 區域 |
| warehouse / warehouseName | 倉名 |
| returnDate | 回報日期 |
| subject | 主旨 |
| stockType | 0=報廢出庫 / 1=換貨補進 |
| processInstanceId | BPM |

---

## 7. 商業邏輯

CRUD + BPM + 與 #40/#41 串接

---

## 8. 使用角色與權限

| 角色 | 對應權限字串 |
|---|---|
| 倉儲員 / 店長 | `whs:bad-product:create/update/delete/query/export` |

---

## 9. 畫面需求

建議：編輯頁含「不良原因」字典下拉、「廠商」選擇、stockType 切換、來源單據下拉

---

## 10. 功能範圍

包含：不良品 CRUD、BPM、與 #40/#41 串接、出入互查

不包含：入出庫實際執行（#40/#41）、廠商主檔（PMM #27）、廠商索賠流程

---

## 11. 待確認事項

| 議題 | 證據 |
|---|---|
| stockType 兩值表達「報廢」與「補進」不夠 — 報廢、補進、退廠商三種應分流 | 業務 |
| 明細 DO 未深查 — 「不良原因」字典化否？廠商欄位？ | DO 未深查 |
| 與 #35 驗收的「短缺數量 shortageQty」是否該觸發不良品單？ | 跨模組 |
| signCode 前綴 `BP` 與 generateSignCode 規則對應需確認 | service 未讀 |
| 廠商索賠流程是否在系統內？ | 業務需求 |
| 與「過期食材自動報廢」的關聯（系統能否依保存日期自動建單）？ | 業務需求 |
