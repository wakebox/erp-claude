# 待釐清事項（UNKNOWNS）

> **AI Agent 必讀**：這份文件列出所有「規格未知」或「來源不明」的項目。
> 遇到這些項目時，**不要自行假設規格**，必須先詢問業務負責人。

---

## 業務規格未知

### U-1：需求預測歸檔後的完整業務流程

**位置**：`kingmaker-module-pdm/.../service/demand/DemandForecastServiceImpl.java:919`

**現況**：
```java
private void processDemandForecastArchived(Long headerId) {
    // TODO 归档业务逻辑，例如：生成原物料需求、通知等
    log.info("需求预测单归档处理，单头ID：{}", headerId);
}
```

**未知問題**：
- 歸檔後要生成什麼？生成到哪個表？
- 是否需要觸發 PMM 採購流程？
- 是否要發送通知？通知給誰？
- `RawMaterialDemand`（原物料需求明細）表是否由此觸發填充？

**需要確認**：需求預測歸檔 → 後續步驟的完整業務規則

---

### U-2：DemandForecast 與 RawMaterialDemand 的串接邏輯

**位置**：`kingmaker-module-pdm/.../dal/mapper/demand/DemandForecastMapper.java:106`

**現況**：
```java
// todo 对应的 厂商资料维护的已归档的条件需要加上，现在注释掉，是没有匹配的数据
```

**未知問題**：
- 需求預測查詢廠商報價時，應過濾哪些廠商狀態？
- 「已歸檔」廠商是否應排除在候選廠商之外？

---

### U-3：食材/食譜/餐類的營養成分子表關聯

**位置**：
- `MealTypeServiceImpl.java:86`
- `NutritionalDefinitionsServiceImpl.java:84`

**現況**：
```java
// TODO 待[食材維護作業]和[食譜維護作業]的營養成分子表建立之後補上此處邏輯
```

**未知問題**：
- 食材和食譜的「營養成分子表」是否已建立？（DB 有 `ingredient_nutritional_contents` 表，但關聯邏輯未實作）
- 當刪除 MealType 或 NutritionalDefinitions 時，應如何處理已關聯的食材/食譜？

---

### U-4：BOM（物料清單）與需求預測的展開規則

**背景**：BOM = Bill of Materials，定義一道餐點由哪些食材組成及用量。

**未知問題**：
- 需求預測歸檔後，BOM 展開的計算邏輯是什麼？
- 如何從銷售預測數量 → 展開 BOM → 計算各食材需求量？
- 計算結果寫入哪個表（`RawMaterialDemand`？）？以什麼格式？

---

### U-5：庫存安全警示的計算標準

**位置**：`StockSafeServiceImpl.java:66`

**現況**：
```java
// todo 获取的是所有的销量；正常应该是平局的每天的销量 productSalesStatisticsVO.getDayAverageSales()
```

**未知問題**：
- 安全庫存計算應使用「日平均銷量」還是「總銷量」？
- 計算公式是什麼？（例如：安全庫存 = 日平均銷量 × 安全天數）
- 安全天數從哪裡配置？

---

### U-6：Stock 依門市過濾的中繼 API

**位置**：`StockServiceImpl.java:109`

**現況**：
```java
// todo 中继上缺少根据传入的门市，计算门市的 库存量
```

**未知問題**：
- 中繼系統（`http://61.218.209.215:80/api`）是否有「依門市查詢庫存」的 API？
- 如果沒有，庫存量應如何從現有 API 計算？

---

### U-7：WHS 庫存異常處理功能

**背景**：架構文件描述 WHS 有「庫存異常處理：異常庫存上報，流程審批」，但程式碼中完全找不到對應實作。

**未知問題**：
- 這個功能是否已被移除？還是從未開始？
- 如果需要，業務規格是什麼？（觸發條件、上報流程、審批節點）

---

### U-8：WarehouseName（倉庫名稱）功能

**現況**：`WarehouseNameDO` 和 `WarehouseNameMapper` 存在，但無 Controller 和 Service。

**未知問題**：
- 這個功能是否需要提供 CRUD API？
- 倉庫名稱與倉庫（`WarehouseDO`）的關係是什麼？

---

## 來源不明的程式碼

### U-9：BizContract 合約管理

**位置**：`kingmaker-server/src/main/java/.../controller/contract/BizContractController.java`

**現況**：整個 Controller 被 `/* */` 註解包裹，無法編譯。相關的 Service、DO、Mapper 都存在。

**未知問題**：
- 這個功能的業務目的是什麼？
- 為什麼被整個註解掉？是廢棄、還是暫停？
- 是否應移到適當的業務模組（如 PMM 或 BHM）？
- Controller 內有 `createContractPro`（含 BPM 流程），流程定義是否存在？

**建議**：在確認規格前，**不要解除註解或修改**。

---

### U-10：BizCustomerInfo 客戶資料維護

**位置**：`kingmaker-server/src/main/java/.../controller/customerinfo/`

**現況**：Controller 可用，但放在 `kingmaker-server` 主模組（不符合架構規範，應在業務模組中）。

**未知問題**：
- 這與 BHM 模組的 `CustomerDataController` 有何不同？是同一業務的兩個版本，還是完全不同的功能？
- 應歸屬哪個業務模組？

---

## BPM 待辦頁實作狀態待確認

### U-11：各模組 `/todo-page` 端點的完整性

以下 Controller 均有 `/todo-page`（BPM 簽核待辦頁）端點，但 Service 實作是否完整未驗證：

**WHS 模組**：
- `BadProductController`
- `CheckPlanController`
- `CheckPlanDetailController`
- `DailyInventoryController`
- `StockRecordHeadController`
- `StockTransferController`

**PMM 模組**：
- `PurAcceptanceController`
- `PurForwardController`
- `PurOrderController`
- `PurReqController`
- `QuoteController`
- `VendorMaintenanceController`
- `VendorQuoteMaintenanceController`

**需要確認**：實際呼叫這些端點時是否能正確返回 BPM 待辦資料？
