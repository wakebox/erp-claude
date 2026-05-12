# 各模組業務流程規格

> 從現有程式碼反推。標注【推測】的部分需業務方確認。
> 完整的 API 清單請參考 Swagger UI：`http://localhost:48080/doc.html`

---

## PDM — 商品資料 + 需求預測模組

### 核心資料結構關係

```
PdmCodeCategory（物料編碼分類）
  └── CodeItem（物料品項）
        └── CodeStructure（編碼結構）
              └── CodeBom（BOM 配方）
                    └── Ingredient（食材）
                          ├── IngredientSpecs（食材規格）
                          ├── IngredientNutritionalContents（營養成分）
                          └── IngredientCompat（相容性）
PackingMaterials（包材）
PdmRecipe（食譜）
PdmUnitDef（單位定義）
PdmUnitConv（單位換算）
```

### 需求預測流程

```
1. 配置（DemandForecastConfig）
   - 設定預測周期、門店範圍

2. 拉取中繼銷售資料
   - 呼叫 BurgerKingStoreClient
   - API: /api/burgerking/admin/order/daily/product-sales
   - 計算各門店各品項銷量

3. 建立需求預測單（DemandForecast）
   - 表頭：DemandForecastDO（店別、時間區間、狀態）
   - 明細：DemandForecastDetailDO（品項、預測數量）

4. 狀態流轉
   待審核 → 審核中（BPM 發起）→ 已批准 → 已歸檔
                              ↘ 已拒絕

5. 歸檔後（⚠️ 未實作，見 UNKNOWNS.md U-1）
   - 【待實作】展開 BOM → 計算原物料需求量 → 寫入 RawMaterialDemand
   - 【待確認】是否觸發 PMM 請購流程
```

### BPM 流程綁定

選單管理（SYSTEM）中可為每個功能路由（`flowPath`）綁定 Flowable 流程定義。業務模組透過 `MenuFlowProcessInstanceHelper` 查詢當前選單是否綁定流程，再決定是否發起。

---

## PMM — 採購管理模組

### 完整採購流程（7 步驟）

```
①廠商資料維護（VendorMaintenance）
  - 廠商基本資料、聯絡人、供貨食材範圍
  - 狀態：草稿 → 已歸檔

②廠商報價維護（VendorQuoteMaintenance）
  - 廠商對各食材的報價維護
  - 狀態：草稿 → 已歸檔

③請購單（PurReq）
  - 觸發：庫存不足或需求預測結果【待確認】
  - 表頭：PurReqDO（門店、申請日期、狀態）
  - 明細：PurReqDetailDO（品項、數量、單位）
  - 流程：草稿 → 待審核 → BPM 審批 → 已批准 → 生成報價單 → 已歸檔
  - 幂等性：一張請購單只能生成一張報價單（已修）

④報價單（Quote）
  - 從請購單明細對比各廠商報價
  - 選擇最優廠商報價
  - 流程：草稿 → 待審核 → BPM 審批 → 已批准 → 生成採購單 → 已歸檔
  - 依廠商分組，一張報價單可生成多張採購單

⑤採購單（PurOrder）
  - 依廠商分組的正式採購文件
  - 流程：草稿 → 待審核 → BPM 審批 → 已批准 → 歸檔 → 生成結轉驗收單

⑥結轉驗收（PurForward）
  - 依實際到貨量（可能分批）做部分結轉驗收
  - 一張採購單可能對應多次結轉
  - 流程：待結轉 → 部分結轉 → 全部結轉

⑦驗收確認（PurAcceptance）
  - 最終確認驗收
  - 確認後【觸發 WHS 入庫】（StockRecord 入庫記錄）
```

### 狀態值（ProcessStatusEnums）

```java
// 定義於 kingmaker-module-pmm-biz
DRAFT("草稿")
PENDING("待審核")
IN_REVIEW("審核中")
APPROVED("已批准")
REJECTED("已拒絕")
ARCHIVED("已歸檔")
```

---

## WHS — 庫存管理模組

### 庫存結構

```
Warehouse（倉庫）
  └── WarehouseName（倉庫名稱）【待確認關係】
Stock（庫存）
  - 每個門店 × 每個食材 = 一筆庫存記錄
StockRecordHead（出入庫單據表頭）
  └── StockRecord（出入庫明細）
```

### 出入庫類型（StockReasonEnum）

系統支援多種出入庫原因類型，包含：
- 調拨入庫 / 調拨出庫
- 盤點調整（硬盤點 / 軟盤點）
- 採購入庫（PMM 驗收後觸發）

### 調拨單流程

```
發起調拨（StockTransfer）
  ↓ 填寫：來源倉庫、目的倉庫、食材、數量
BPM 審批
  ↓ 已批准
執行調拨
  ↓
出庫記錄（StockRecord，來源倉庫）
入庫記錄（StockRecord，目的倉庫）
庫存更新（Stock）
```

### 盤點流程

```
盤點計劃（CheckPlan）
  - 設定盤點周期（PeriodicityEnum：每日/每週/每月）
  - 設定盤點項目（CheckPlanItem）
  ↓ BPM 審批

盤點執行（CheckPlanDetail）
  - 按照計劃周期執行
  - 記錄實際數量
  ↓

盤點驗收（CheckTake）
  - 核對系統帳面庫存與實際盤點數量
  - 差異處理：調整庫存（StockRecord）

不良品管理（BadProduct）
  - 盤點中發現不良品
  - 記錄不良品明細（BadProductDetail）
  - 轉仓操作：生成調拨單
  ↓ BPM 審批
```

### 每日盤點（DailyInventory）

```
每日自動或手動觸發
  ↓
呼叫中繼 API 取得當日銷售資料
  ↓
計算理論消耗量（銷售量 × 食材用量）
  ↓
與實際庫存對比
  ↓
記錄 DailyInventory + DailyInventoryDetail
```

---

## BPM — 工作流模組

### 如何為業務模組新增 BPM 審批

1. 在 Flowable 設計器（`/bpm/model`）建立流程模型
2. 在選單管理中，為對應的前端路由設定 `flowPath`（流程路徑）
3. 業務 Service 中呼叫 `MenuFlowProcessInstanceHelper.startProcessInstance()`
4. 監聽 `BpmProcessInstanceStatusEvent` 事件，處理審批結果回調

### 流程狀態回調

當 BPM 審批完成（通過/拒絕），系統會發布 `BpmProcessInstanceStatusEvent`。各業務模組需實作對應的 Listener 來更新本身的單據狀態。

**現有 Listener 範例**：
- `DemandForecastStatusListener`（PDM）
- `BizContractStatusListener`（server，但相關功能被註解）

---

## SYSTEM — 系統管理模組

### 用戶認證流程

```
POST /system/auth/login
  ↓ 驗證帳密 + 驗證碼
  ↓ 產生 JWT Token（有效期從 application.yaml 配置）
  ↓ 回傳 BergerKingAuthLoginRsVO（含 accessToken、refreshToken）

後續請求：
Header: Authorization: Bearer {accessToken}
  ↓ JwtAuthenticationTokenFilter 解析 Token
  ↓ 注入 SecurityContextHolder
  ↓ @PreAuthorize("@ss.hasPermission('xxx:yyy:zzz')") 驗證權限
```

### 權限命名規則

```
{模組}:{資源}:{動作}
例：
  whs:bad-product:create
  pmm:pur-req:query
  pdm:ingredient:update
```
