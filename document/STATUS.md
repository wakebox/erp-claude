# 各模組完成度狀態

> 最後更新：2026-05-12
> 判斷依據：程式碼掃描 + 訪談確認

## 圖例

| 符號 | 意義 |
|---|---|
| ✅ | 已完成（Controller + Service + Mapper 均存在，無 TODO） |
| 🔶 | 部分完成（核心功能可運作，有 TODO 或細節缺失） |
| ❌ | 未完成（骨架存在但實作缺失，或完全未做） |
| ❓ | 未知（無法從程式碼判斷完成度，需人工確認） |
| 🧊 | 凍結（暫時不開發） |

---

## SYSTEM — 系統管理模組

| 功能 | 狀態 | 備註 |
|---|---|---|
| 用戶管理 | ✅ | |
| 角色管理 | ✅ | |
| 部門管理 | ✅ | |
| 選單管理 | ✅ | 含 `flowPath` BPM 流程配置 |
| 資料字典 | ✅ | |
| OAuth2 | ✅ | |
| 通知管理 | ✅ | |
| 簡訊管理 | ✅ | |
| 門店管理（Store） | ✅ | |
| 租戶管理 | ✅ | |

---

## INFRA — 基礎設施模組

| 功能 | 狀態 | 備註 |
|---|---|---|
| 檔案管理 | ✅ | |
| 程式碼生成器 | ✅ | 可用，建議新功能先用此工具產生骨架 |
| 定時任務（Quartz） | ✅ | |
| API 存取日誌 | ✅ | |
| 系統配置（Key-Value） | ✅ | |
| 資料源配置 | ✅ | |

---

## BPM — 工作流模組

| 功能 | 狀態 | 備註 |
|---|---|---|
| 流程模型設計 | ✅ | Flowable 可視化設計器 |
| 流程定義部署 | ✅ | |
| 流程實例（發起/查詢/取消） | ✅ | |
| 用戶任務審批（通過/拒絕） | ✅ | |
| 審批人候選策略（15+ 種） | ✅ | |
| 待辦/已辦查詢 | ✅ | |

---

## PDM — 商品資料 + 需求預測模組

| 功能 | 狀態 | 備註 |
|---|---|---|
| 物料編碼管理（CodeCategory / CodeItem / CodeStructure） | ✅ | |
| BOM 配方管理（CodeBom） | ✅ | |
| 食材管理（Ingredient） | ✅ | |
| 食材規格（IngredientSpecs） | ✅ | |
| 食材相容性（IngredientCompat） | ✅ | |
| 食材小類（IngredientSubcategoryType） | ✅ | 最新 commit 剛加入 |
| 食材營養成分（IngredientNutritionalContents） | 🔶 | 營養成分「刪除」邏輯 TODO：待食材/食譜子表建立後補上 |
| 包材管理（PackingMaterials） | ✅ | |
| 食譜管理（PdmRecipe） | 🔶 | 營養成分關聯 TODO：同上 |
| 營養成分定義（NutritionalDefinitions） | 🔶 | 刪除邏輯 TODO：待食材/食譜子表建立後補上 |
| 餐類管理（MealType） | 🔶 | 刪除邏輯 TODO：同上 |
| 物流類型（LogisticsType） | ✅ | |
| 單位定義（PdmUnitDef） | ✅ | |
| 單位換算（PdmUnitConv） | ✅ | |
| 臨時需求（TempReq） | ✅ | |
| 原物料物流（RawMaterialLogistics） | ✅ | |
| 需求預測（DemandForecast）— 計算 | ✅ | 從中繼拉銷售資料、計算需求 |
| 需求預測（DemandForecast）— 發起審批 | ✅ | |
| 需求預測（DemandForecast）— 歸檔後生成原料需求 | ❌ | `processDemandForecastArchived()` 為空 TODO，核心業務邏輯缺失 |
| 需求預測配置（DemandForecastConfig） | ✅ | |
| 原物料需求明細（RawMaterialDemand） | ❓ | Controller 存在，但與需求預測歸檔的串接邏輯未實作 |
| 原物料需求表頭（RawMaterialDemandHead） | ❓ | 同上 |
| DemandForecastMapper — 廠商歸檔條件 | ❌ | 被 TODO 標記為缺少已歸檔廠商過濾條件 |

---

## WHS — 庫存管理模組

| 功能 | 狀態 | 備註 |
|---|---|---|
| 倉庫管理（Warehouse） | 🔶 | Service 有實作，但部分驗證用 `IllegalArgumentException`（非框架規範） |
| 庫存查詢（Stock） | 🔶 | 依門市計算庫存的中繼 API 尚未對接（TODO） |
| 出入庫記錄（StockRecord / StockRecordHead） | ✅ | |
| 調拨單（StockTransfer） | 🔶 | BPM 簽核待辦頁（`/todo-page`）需確認實作完整度 |
| 安全庫存設定（StockSafe） | 🔶 | 計算用總銷量而非日平均銷量（TODO），數字不準確 |
| 不良品管理（BadProduct） | 🔶 | BPM 簽核待辦頁（`/todo-page`）需確認實作完整度 |
| 盤點計劃（CheckPlan） | 🔶 | BPM 簽核待辦頁（`/todo-page`）需確認實作完整度 |
| 盤點執行（CheckPlanDetail） | 🔶 | BPM 簽核待辦頁（`/todo-page`）需確認實作完整度 |
| 盤點驗收（CheckTake） | ✅ | |
| 每日盤點（DailyInventory） | 🔶 | BPM 簽核待辦頁（`/todo-page`）需確認實作完整度 |
| 倉庫名稱（WarehouseName） | ❌ | DO + Mapper 存在，但沒有 Controller 和 Service |
| 庫存異常處理 | ❌ | 架構文件描述有此功能，但程式碼中完全找不到對應實作 |

---

## PMM — 採購管理模組

| 功能 | 狀態 | 備註 |
|---|---|---|
| 廠商資料（VendorMaintenance） | ✅ | 基本完整，bug 收尾中 |
| 廠商報價維護（VendorQuoteMaintenance） | ✅ | 基本完整 |
| 請購單（PurReq） | ✅ | 含 BPM 流程、幂等性校驗已修 |
| 報價單（Quote） | ✅ | 含廠商比價、BPM 流程 |
| 採購單（PurOrder） | ✅ | 含 BPM 流程、歸檔生成結轉驗收單 |
| 結轉驗收（PurForward） | ✅ | 含部分結轉邏輯 |
| 驗收確認（PurAcceptance） | ✅ | 確認後觸發入庫 |
| 全模組 BPM 待辦頁（`/todo-page`） | 🔶 | 7 個 controller 均有此端點，需確認 Service 實作是否完整 |

---

## BHM — 漢堡王基礎資料模組

| 功能 | 狀態 | 備註 |
|---|---|---|
| 客戶資料（CustomerData） | 🧊 | 暫時凍結，不開發 |
| 付款方式（PaymentMethod） | 🧊 | 暫時凍結，不開發 |

---

## kingmaker-server — 主應用模組（非標準業務功能）

| 功能 | 狀態 | 備註 |
|---|---|---|
| 合約管理（BizContract） | ❓ | 整個 Controller 被 `/* */` 註解，來源和規格未知 |
| 客戶資料維護（BizCustomerInfo） | ❓ | Controller 可用，但放在 server 層不符架構規範，用途未知 |
