# 待辦功能清單（BACKLOG）

> 從程式碼 TODO、半成品、架構文件對照整理。
> 優先順序尚未由業務方決定，標注「緊急度」供參考。
>
> 開始實作前，請先確認 `UNKNOWNS.md` 中是否有相關未知事項需先釐清。

---

## 優先度說明

| 標籤 | 說明 |
|---|---|
| 🔴 高 | 功能缺失導致核心流程無法完成 |
| 🟡 中 | 功能可用但不正確或不完整 |
| 🟢 低 | 技術債或優化，不影響業務 |
| ⬜ 未知 | 需先確認規格才能評估 |

---

## PDM 模組

### B-PDM-1：需求預測歸檔後生成原物料需求明細 🔴

**相關 UNKNOWN**：U-1、U-2、U-4

**位置**：`DemandForecastServiceImpl.java:919`

**現況**：
```java
private void processDemandForecastArchived(Long headerId) {
    // TODO 歸檔業務邏輯，例如：生成原物料需求、通知等
}
```

**需要做的**：
1. 確認業務規格（見 UNKNOWNS.md U-1）
2. 實作 BOM 展開邏輯：從需求預測數量 × BOM 配方 → 計算各食材需求量
3. 將結果寫入 `RawMaterialDemand` 表
4. 觸發後續通知或 PMM 請購流程（待確認）

---

### B-PDM-2：DemandForecastMapper 廠商已歸檔過濾條件 🟡

**相關 UNKNOWN**：U-2

**位置**：`DemandForecastMapper.java:106`

**現況**：SQL 查詢缺少廠商「已歸檔」狀態的過濾，導致查詢結果可能包含無效廠商資料。

**需要做的**：確認規格後，在 Mapper SQL 中加入廠商狀態過濾條件。

---

### B-PDM-3：食材/食譜/餐類與營養成分子表的關聯刪除邏輯 🟡

**相關 UNKNOWN**：U-3

**位置**：
- `MealTypeServiceImpl.java:86`
- `NutritionalDefinitionsServiceImpl.java:84`

**需要做的**：
1. 確認 `ingredient_nutritional_contents` 子表是否已建立
2. 在 MealType、NutritionalDefinitions 刪除時，加入關聯資料的檢查或級聯刪除邏輯

---

## WHS 模組

### B-WHS-1：WarehouseName 功能實作 ⬜

**相關 UNKNOWN**：U-8

**現況**：`WarehouseNameDO` + `WarehouseNameMapper` 存在，但缺少 Service + Controller。

**需要做的**（確認規格後）：
1. 建立 `WarehouseNameService` + `WarehouseNameServiceImpl`
2. 建立 `WarehouseNameController`（參考其他 WHS Controller 格式）
3. 建立對應 VO 類

---

### B-WHS-2：庫存依門市過濾 🔴

**相關 UNKNOWN**：U-6

**位置**：`StockServiceImpl.java:109`

**現況**：目前使用測試資料，中繼 API 尚未提供門市庫存過濾介面。

**需要做的**：
1. 確認中繼 API 是否新增對應介面
2. 更新 `StockService` 中的計算邏輯

---

### B-WHS-3：安全庫存計算改用日平均銷量 🟡

**相關 UNKNOWN**：U-5

**位置**：`StockSafeServiceImpl.java:66`

**現況**：計算使用總銷量，應改為日平均銷量。

**需要做的**：
1. 確認計算公式
2. 將 `getDayAverageSales()` 替換目前的總銷量欄位

---

### B-WHS-4：庫存異常處理功能 ⬜

**相關 UNKNOWN**：U-7

**現況**：架構文件提及此功能，程式碼中完全不存在。

**需要做的**（確認規格後）：
1. 建立 `StockAbnormal` 相關 DO / Mapper / Service / Controller
2. 設計 BPM 審批流程

---

### B-WHS-5：確認各 /todo-page 端點的 Service 實作完整性 🟡

**相關 UNKNOWN**：U-11

**涉及**：BadProduct、CheckPlan、CheckPlanDetail、DailyInventory、StockRecordHead、StockTransfer

**需要做的**：
1. 手動呼叫每個 `/todo-page` 端點，確認是否返回正確的 BPM 待辦資料
2. 修復任何返回空資料或錯誤的端點

---

## PMM 模組

### B-PMM-1：確認各 /todo-page 端點的 Service 實作完整性 🟡

**相關 UNKNOWN**：U-11

**涉及**：PurAcceptance、PurForward、PurOrder、PurReq、Quote、VendorMaintenance、VendorQuoteMaintenance

**需要做的**：同 B-WHS-5

---

## kingmaker-server（待決策）

### B-SERVER-1：BizContract 合約管理的去向 ⬜

**相關 UNKNOWN**：U-9

**選項**：
- 選項 A：確認規格後解除註解，搬移至適當業務模組（建議 PMM 或新建模組）
- 選項 B：規格廢棄，刪除相關程式碼（Controller、Service、DO、Mapper）

**目前動作**：等待業務方確認，不要修改。

---

### B-SERVER-2：BizCustomerInfo 客戶資料維護的歸屬 ⬜

**相關 UNKNOWN**：U-10

**選項**：
- 選項 A：確認規格後搬移至 BHM 模組
- 選項 B：確認規格後搬移至 SYSTEM 模組
- 選項 C：屬於新模組

**目前動作**：等待業務方確認，不要移動或修改架構。

---

## 技術債（不阻礙業務但需清理）

### B-TECH-1：錯誤處理不一致 🟢

**位置**：`WHS/WarehouseServiceImpl.java`（多處使用 `IllegalArgumentException`）

**修改方式**：
```java
// 改前
throw new IllegalArgumentException("区域参数不能为空");

// 改後
throw exception(ErrorCodeConstants.WAREHOUSE_AREA_REQUIRED);
// 並在 ErrorCodeConstants 中定義對應錯誤碼
```

---

### B-TECH-2：缺少 Swagger 說明的端點 🟢

部分 Controller 的 `@Operation` 說明不完整，影響 AI 理解端點用途。建議補齊後 AI 才能準確生成前端對接程式碼。

---

### B-TECH-3：DictTypeConstants 枚舉未建立 🟢

**位置**：PDM 模組多個 VO 檔案的 `@DictFormat` 註解標有 TODO

**修改方式**：在對應的 `DictTypeConstants` 枚舉類中補上字典類型常量。
