# PRD｜庫存管理 — 盤點計劃執行管理

> 來源：逆向自 `kingmaker-module-whs` 後端程式碼（`controller/admin/checkplandetail/CheckPlanDetailController.java`、`service/checkplandetail/`、`dal/dataobject/checkplandetail/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **倉儲主管 / 執行盤點的倉儲員**。「盤點計劃製定」(#44) 通過簽核後，計劃會落到本表 `whs_check_plan_detail` 變成「具體執行單列」 — 一筆計劃可能拆出多筆執行列（依日期 / 倉位 / 負責人）。

> 「Q3 計劃 CP-2026-001 通過後 → 拆成 12 筆執行列（每週一筆）→ 每筆派指定倉儲員執行」

### 1.2 我要做什麼

- 建立 / 編輯計劃執行列
- 走簽核流程
- 透過 `/get-by-opposite-stock-type` 找對向出入庫單
- 透過 `/get-stock-record-batch-by-sign-code` 反查出入庫批次（給 #40/#41）
- 透過 `/check-plan-item/list-by-plan-detail-id` 取該執行列的品類清單
- 分頁查詢、待簽分頁、Excel 匯出（**目前 hardcode 空 list，明確 bug**）

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 計劃 → 執行的橋接 | 一張計劃拆多筆執行單 |
| 依日期 / 倉位 / 負責人分派 | 排班 |
| 走簽核 | 執行細節再次確認 |
| stockType 與 #40/#41 串接 | 盤點結果直接調整庫存 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 計劃執行列 CRUD | 主要建單 |
| 與 #44 計劃串接 | signCode 或外鍵 |
| 與 #40/#41 出入庫串接 | 透過 signCode 前綴 CE |
| BPM 簽核 | 核可 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 盤點計劃執行管理 |
| 所屬模組 | WHS（庫存管理） |
| 兄弟功能 | 計劃製定 (#44)、盤點作業 (#43)、每日盤點 (#46) |
| 主要頁面 | 執行列編輯頁、單頭分頁、待簽分頁 |
| 簽核流程 | 有：`/todo-page` 存在 |
| signCode 前綴 | `CE`（與 #43 共用，由 batchProcessStockRecords 透過 `updateCheckTakeStatus` 回寫 stockType） |

---

## 2. 功能目的

計劃執行是「**計劃與盤點結果的中間橋樑**」：

1. **承接 #44** — 計劃落到具體執行單
2. **承下 #43** — 倉儲員實際盤點時建 CheckTake
3. **與 #40/#41 連動** — 盤盈盤虧調整庫存
4. **stockType 旗標** — 記錄是否已完成出入庫調整

---

## 3. 業務邏輯背景

### 3.1 表

`whs_check_plan_detail`（單頭 / `CheckPlanDetailDO`） — 計劃執行的具體單據。

### 3.2 stockType 回寫

由 #40/#41 觸發 `updateCheckTakeStatus(signCode, stockType)`：

```java
LambdaQueryWrapperX<CheckPlanDetailDO> wrapper = ...
  .eq(CheckPlanDetailDO::getSignCode, signCode);
CheckPlanDetailDO checkPlanDetailDO = checkPlanDetailMapper.selectOne(wrapper);
if (checkPlanDetailDO != null) {
  checkPlanDetailDO.setStockType(stockType);
  checkPlanDetailMapper.updateById(checkPlanDetailDO);
}
```

來源：#40 `StockRecordServiceImpl.java:245-259`。

### 3.3 與 #44 的關係

未明確：可能透過 `planId` 外鍵或 `signCode` 字串對應。

### 3.4 Excel 匯出 bug

```java
// List<CheckPlanDetailDO> list = checkPlanDetailService.getCheckPlanDetailPage(pageReqVO).getList();
List<CheckPlanDetailDO> list = null;
```

**永遠寫出 null list**（line 102-103）— 與 #34 結轉驗收同樣 bug。

### 3.5 跨模組依賴

- #44（上游）、#43（下游記錄）、#40/#41（庫存調整）

---

## 4. 情境說明

### 4.1 正常流程

#44 簽核 → 系統拆出多筆 #45 執行列 → 各倉儲員執行盤點（#43 建 CheckTake）→ 結果歸檔 → 觸發 #40/#41 → stockType 回寫到 #45。

---

## 5. 操作流程

```
[使用者進入「盤點計劃執行管理」]
  │
  ├─ POST /whs/check-plan-detail/create
  ├─ PUT /whs/check-plan-detail/update
  ├─ DELETE /whs/check-plan-detail/delete?id=
  ├─ GET /whs/check-plan-detail/get?id=（CheckPlanDetailAndDetailVO）
  ├─ GET /whs/check-plan-detail/page、todo-page、export-excel ⚠️
  ├─ POST /whs/check-plan-detail/get-by-opposite-stock-type
  ├─ GET /whs/check-plan-detail/get-stock-record-batch-by-sign-code?signCode=&stockType=
  └─ GET /whs/check-plan-detail/check-plan-item/list-by-plan-detail-id?planDetailId=
```

---

## 6. 欄位規格

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| signCode | 單據編號（前綴 CE） |
| processStatus | 流程狀態 |
| stockType | 出入庫旗標（0/1，由 #40/#41 回寫） |
| 其他 | 規劃日期、倉位、負責人等（DO 未深查） |

---

## 7. 商業邏輯

CRUD + BPM 簽核 + stockType 回寫

---

## 8. 使用角色與權限

| 角色 | 對應權限字串 |
|---|---|
| 倉儲主管 / 倉儲員 | `whs:check-plan-detail:create/update/delete/query/export` |

---

## 9. 畫面需求

建議：執行列分頁、編輯頁、待簽分頁

---

## 10. 功能範圍

包含：執行列 CRUD、與 #44/#43/#40/#41 串接

不包含：計劃製定（#44）、盤點記錄（#43）、每日盤點（#46）

---

## 11. 待確認事項

| 議題 | 證據 |
|---|---|
| Excel 匯出 hardcode null list — 明確 bug | line 102-103 |
| 與 #44 計劃製定的對應方式（planId vs signCode） | 跨表設計 |
| stockType 雙狀態（0/1）對「未盤」「盤完已出庫」「盤完已入庫」的表達能力不足 | DO `stockType` |
| `CheckTake`（#43）與本表的對應關係未明確 — #43 是否衍生自本表的 signCode？ | 跨表設計 |
| 「盤點計劃所有計劃列」Tag 命名繁雜 | Controller Tag |
| `getCheckPlanItemListByPlanDetailId` 參數名 `checkPlanDetailPageReqVO` 與 @Parameter 描述「planDetailId」不一致 | Controller line 114 |
| #43、#44、#45 三層架構是否過度設計？ | 與業務流程比對 |
