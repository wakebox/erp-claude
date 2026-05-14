# PRD：PDM 商品資料模組 — 逆向規格分析

> 本文件透過逆向分析 `erp-spring/kingmaker-module-pdm` 程式碼，還原 PDM 商品資料模組的完整業務規格、資料表設計、ER Model 與功能清單。
> 對應 `erp-claude/document/excel.md` 中「PDM」業務主模組（**序號 12 ~ 23**），共 12 個系統主功能。
>
> **重要範圍切割**：原 `PDM_PRD.md`（v1）把「需求預測 / 臨時需求 / 原物料需求行事曆 / 物流單」也一併寫入 PDM，與 Excel 業務分類不符。本版（v2）已重新切割，把那些內容移交給 [`DEMAND_AGGREGATION_PRD.md`](DEMAND_AGGREGATION_PRD.md)（Excel 24~26）與未來的物流／採購 PRD（Excel 30、48~52）。

---

## Problem Statement

漢堡王台灣的 PDM 商品資料模組是整個 ERP 鏈條的**最底層主檔**（食材、食譜、包材、編碼、單位、營養成分、餐食類型、物流類型），下游所有模組（需求預測 / 採購 / 庫存 / 物流 / 店長）都消費這層資料。但目前：

1. **業務名稱與程式名稱不一致**：Excel 用「單品維護作業 / 編碼原則維護 / 門市分群維護表」等業務語言，程式碼用 `pdm_recipe / pdm_code_structure / 中繼 API 區域群組` — 業務方與新人都對不上。
2. **「門市分群維護表」(#22) 在 PDM 內無對應實作**：實際資料是從漢堡王中繼 API（`BurgerKingStoreClient.getGroupWithStoresInner` / `getAllAreasWithStores`）拉取，PDM 本身不維護這份主檔；但 Excel 把它放在 PDM 是合理的——它必須被視為「PDM 模組要消費的外部主檔」，並有 ER／規格說明。
3. **「編碼原則維護」(#17) 對應多張表**：實際上是「編碼結構 + 編碼結構明細 + 編碼 BOM + 編碼 BOM 關聯」四張表共同構成的「品號編碼原則」，沒有對應表叫做 `code_rule`。需在規格中清楚說明這條鏈如何拼出一個品號。
4. **食材的副類型與「儲存類型」（SHORT/LONG）綁定關係埋在 `pdm_ingredient_subcategory_type` 表內** — 但這張表沒有 Controller，只有 DO + Mapper，業務方完全看不到它如何維護。
5. **食材主檔分多張子表（規格、相生相剋、營養成分）**，但每張子表都有獨立 Controller、獨立刪除邏輯、各自 BPM 觸發點，沒有統一的「食材總覽 → 子表」清單。
6. **單位換算公式（base × ratio = target）零文件**：`pdm_unit_conv` 只有 ratio 欄位，沒有寫明「base→target = base × ratio」這個方向約定，新人易誤解。
7. **CodeBom（品號 BOM）與食譜 SingleServingRecipe 的關係未說明**：兩者都掛食材，前者是「品號編碼原則的展開」、後者是「實際銷售單品的食材配方」，職責容易混淆。
8. **BPM 啟動點散落**：食材／食譜／包材都有獨立流程；BPM Listener 各自監聽，businessKey 格式各自不同，沒有統一規範文件。

---

## Solution

產出本 PRD 作為 PDM 商品資料模組（Excel #12-23）的**權威逆向規格**：

1. Excel 業務名稱 ↔ 程式碼對照表（含「不在 PDM 內」的 #22 門市分群外部來源說明）
2. PDM 模組完整 ER Model（17 張資料表 + 1 張外部映射）
3. 每張資料表的完整欄位清單（含 BaseDO 共有欄位、軟刪除、樂觀鎖、Flowable 整合欄位）
4. 4 條主檔生命週期：食材（含 4 張子表 + BPM）、食譜（含 3 張子表 + BPM）、包材（含 1 張子表 + BPM）、編碼原則（4 張表 + 階層 BOM）
5. 基礎資料維護：營養成分定義、餐食類型、單位定義、單位換算、物流類型
6. 「門市分群」外部來源映射（漢堡王中繼 API）— 解釋為何 PDM 不擁有此表但需要它
7. 跨模組消費清單（PDM → PMM / PDM → WHS / PDM → Demand Aggregation）
8. API 端點 + 權限碼清單
9. 已知缺口、TODO、與 [`UNKNOWNS.md`](../UNKNOWNS.md) 對應

---

## 功能 ↔ 程式碼對照表

| Excel 序號 | Excel 名稱 | 程式對應（PDM）| 主要表 | 狀態 |
|---|---|---|---|---|
| 12 | 食材維護作業 | `IngredientController` + `IngredientSpecsController` + `IngredientCompatController` + `IngredientNutritionalContentsController` + Listener | `pdm_ingredient`、`pdm_ingredient_specs`、`pdm_ingredient_compat`、`pdm_ingredient_nutritional_contents`、`pdm_ingredient_subcategory_type` | ✅ 含 BPM（食材歸檔）；🔶 `subcategory_type` 無 Controller |
| 13 | 單品維護作業 | `PdmRecipeController` | `pdm_recipe`、`pdm_single_serving_recipe`、`pdm_recipe_nutritional_contents`、`pdm_product_recipe_rel` | ✅ 含 BPM；🔶 營養成分子表「刪除」邏輯 TODO |
| 14 | 包材維護作業 | `PackingMaterialsController` | `pdm_packing_materials`、`pdm_packing_materials_dtl` | ✅ 含 BPM、Excel 匯出 |
| 15 | 編碼類別維護 | `PdmCodeCategoryController` | `pdm_code_category` | ✅ 基礎 CRUD + Excel |
| 16 | 編碼項目維護 | `CodeItemController` | `pdm_code_item` | ✅ 基礎 CRUD + Excel |
| 17 | 編碼原則維護 | `CodeStructureController` + `CodeStructureDetailController` + `CodeBomController` | `pdm_code_structure`、`pdm_code_structure_detail`、`pdm_code_bom`、`pdm_code_bom_relation` | ✅ 含結構→明細→BOM→BOM Relation 階層 |
| 18 | 營養成分定義維護表 | `NutritionalDefinitionsController` | `pdm_nutritional_definitions` | 🔶 刪除邏輯 TODO（待食材/食譜子表完整建立後補上）|
| 19 | 餐食類型維護表 | `MealTypeController` | `pdm_meal_type` | 🔶 同上 |
| 20 | 單位定義維護表 | `PdmUnitDefController` (`/pdm/udf`) | `pdm_unit_def` | ✅ 基本 CRUD + 分頁 |
| 21 | 單位轉換維護表 | `PdmUnitConvController` | `pdm_unit_conv` | ✅ 基本 CRUD + 分頁 |
| 22 | 門市分群維護表 | **PDM 內無對應表** — 外部來源：漢堡王中繼 `BurgerKingStoreClient`（`AreaGroupHierarchyVO`、`StoreGroupVO`）| —（外部）| ⚠️ 唯讀，僅消費 |
| 23 | 物流類型維護表 | `LogisticsTypeController` | `pdm_logistics_type` | ✅ 基本 CRUD + Excel |

> 不在本 PRD 範圍但在原 v1 包含的內容（見 [Out of Scope](#out-of-scope)）：
> - Excel #24「食材需求預測試算表 (BOM)」、#25「物料需求預測試算表 (非 BOM)」、#26「臨時需求審核」 → 已移交 [`DEMAND_AGGREGATION_PRD.md`](DEMAND_AGGREGATION_PRD.md)
> - Excel #30「原料物需求行事曆」、#48-52「物流管理」 → 待寫獨立 PRD（PDM 內的 `RawMaterialDemand*` 與 `RawMaterialLogistics*` 表，下游使用）

---

## User Stories

### 食材維護作業（Excel #12）

#### 食材主檔

1. 作為**研發人員**，我想建立**食材主檔（Ingredient）**，填寫編碼結構 ID、大分類（mainCategory）、食材類型（category）、副類型（subcategory）、料源（source）、季節、建議烹調方式、前處理注意事項、建立部門、主旨。
2. 作為**研發人員**，我想送出食材主檔後系統依「選單是否綁定流程」（`FormPathUniqueEnum.INGREDIENTS.path = "ingredients"`）決定是否發起 BPM 簽核；流程實例 ID 寫回 `process_instance_id`。
3. 作為**研發人員**，我想看到食材的 `sign_code` 由系統自動生成（`MenuService.generateSignCode(...)`），毋需手填。
4. 作為**審核主管**，我想在 `GET /pdm/ingredient/todo-page` 看到當前登入使用者的食材待辦清單，逐一審核或退件。
5. 作為**系統**，當食材通過 BPM（APPROVE）時，我必須由 `IngredientStatusListener` 將 `process_status` 更新為「已歸檔」；REJECT / CANCEL 目前為預留行為。
6. 作為**研發人員**，我想**單筆刪除**食材並同步軟刪所有子表（規格、相生相剋、營養成分）；也支援**批次刪除**多筆食材。
7. 作為**商品管理員**，我想**分頁查詢**食材（按 mainCategory、category、subcategory、process_status、create_department 篩選），並可**匯出** Excel。

#### 食材規格（IngredientSpecs）

8. 作為**研發人員**，我想為一筆食材新增多筆**規格（IngredientSpecs）**，每筆規格含：規格名稱、損耗率（wastageRate，%）、食材狀態（ingredientStatus，引用 CodeItem）、基本加工方式、調味加工方式、儲存方式、序號碼 1/2、產品編號（prodCode，對應漢堡王原物料）、計量單位（unit FK→`pdm_unit_def`）、前置時間、啟用狀態、單份規格量（singleSpec）、單份規格單位、漢堡王原物料產品 ID（materialProductId）。
9. 作為**研發人員**，我想在 `GET /pdm/ingredient-specs/getList` 取得某一筆食材的所有規格；`GET /pdm/ingredient-specs/获取食材规格全部列表` 取得全部食材的規格清單；`GET /pdm/ingredient-specs/獲取食材全部列表--包含食材類型` 取得「規格 + 食材類型」聯合視圖。
10. 作為**研發人員**，我想**單筆**或**批次刪除**食材規格；當所屬食材已歸檔則不可修改（拋 `INGREDIENT_ARCHIVED_CANNOT_UPDATE`）。

#### 食材相生相剋（IngredientCompat）

11. 作為**研發人員**，我想為一筆食材設定**相生相剋（IngredientCompat）**：以「比對的類型 / 副類型 / 料源」三個 CodeItem ID 為比對目標，加上說明（description）與相容旗標（compat: 1=相容, 0=不相容）。
12. 作為**研發人員**，我想 `GET /pdm/ingredient-compat/列表` 取得某食材的所有相生相剋紀錄。
13. 作為**研發人員**，我想**單筆**或**批次刪除**相生相剋紀錄。

#### 食材營養成分（IngredientNutritionalContents）

14. 作為**研發人員**，我想為一筆食材記錄**營養成分（IngredientNutritionalContents）**，每筆對應一個營養定義 ID（`pdm_nutritional_definitions.id`）、每份含量（servingAmount）、單位（VARCHAR）。
15. 作為**研發人員**，我想 `GET /pdm/ingredient-nutrition/列表` 取得某食材的所有營養成分項；刪除時為**單筆**操作。

#### 食材副類型儲存類型（IngredientSubcategoryType — 無 Controller）

16. 作為**資料庫管理員**，我想透過 SQL 維護 `pdm_ingredient_subcategory_type` 表（detail_id → storage_type），把每個「副類型結構明細」標記為 `SHORT`（生鮮）或 `LONG`（凍品）；此標記影響**需求預測**對食材的計算分支（[`DEMAND_AGGREGATION_PRD.md`](DEMAND_AGGREGATION_PRD.md)）。
17. 作為**規格作者**，我必須在規格中聲明：**目前此表沒有 CRUD API、沒有前端維護介面**；需透過 SQL 維護或補建 Controller / Service。

### 單品維護作業 / 食譜（Excel #13）

#### 食譜主檔

18. 作為**研發人員**，我想建立**食譜主檔（PdmRecipe）**，填寫：編碼結構 ID（structure）、大分類（mainCategory）、品項類別（itemCategory）、品項名稱（itemName，FK→CodeItem）、品項子標籤（itemSubTag）、烹調方式、顯示名稱、標籤名稱、產品代碼（productCode）、餐食類型（mealType FK→`pdm_meal_type`）、單份份量（portionAmount）、份量單位（amountUnit）、單份標準成本（portionStandardCost）、烹調步驟、烹調技巧。
19. 作為**研發人員**，我想為食譜綁定**漢堡王產品 ID（recipeProductId）**，建立「食譜 ↔ 漢堡王銷售產品」的對應關係，讓需求預測能從銷售資料展開到食材。
20. 作為**研發人員**，我想送出食譜後系統依 `FormPathUniqueEnum.RECIPE.path = "recipe"` 啟動 BPM；通過後 `RecipeStatusListener` 把 `process_status` 設為「已歸檔」。
21. 作為**商品管理員**，我想在 `GET /pdm/recipe/page` 分頁查詢食譜、`/獲取食材主類分页--签核` 看待辦、`/导出食譜維護表-食譜主表 Excel` 匯出。

#### 食譜子表 — 單份用量配方（PdmSingleServingRecipe）

22. 作為**研發人員**，我想為食譜新增多筆**單份用量配方（PdmSingleServingRecipe）**，每筆對應一個食材 ID（ingredientId）、標準用量（standardAmount）、用量單位（unit）、單份規格、單份規格單位、預設廠商代碼（defaultSupplier）、最新報價（latestQuotePrice）、最後採購價格（lastPurchasePrice）、標準用量成本（standardAmountCost）、prodCode。
23. 作為**研發人員**，我想呼叫食譜詳情 API 一次取得「主表 + 單份配方列表」`/获得食譜維護子表-單份用量配方列表`、`/获得食譜-单份食谱子表信息`。

#### 食譜子表 — 營養成分（RecipeNutritionalContents）

24. 作為**研發人員**，我想為食譜記錄整道料理的營養成分，每筆對應一個營養定義 ID 與每份含量。
25. 作為**研發人員**，我想 `/获得食譜維護子表-營養成分含量列表` 取得食譜的所有營養項。

#### 食譜子表 — 產品配方關聯（PdmProductRecipeRel）

26. 作為**研發人員**，我想建立「食譜 ↔ 漢堡王產品」的多對多映射（`pdm_product_recipe_rel`），讓系統在拉取漢堡王銷售資料時能反查食譜並展開成食材需求（被 [`DEMAND_AGGREGATION_PRD.md`](DEMAND_AGGREGATION_PRD.md) 的 `product-recipe-analysis` 消費）。

### 包材維護作業（Excel #14）

27. 作為**採購人員**，我想建立**包材主檔（PackingMaterials）**，填寫包材類別（category，FK→CodeItem）、主旨。
28. 作為**採購人員**，我想為包材主檔新增多筆**包材明細（PackingMaterialsDtl）**，每筆對應一筆「包材類別、包材名稱、流水編號（6 碼）、品號（productCode）、計數單位（unitId）、單一規格（singleSpec）、單一規格單位（singleSpecUnit）、狀態」。
29. 作為**採購人員**，我想送出包材維護單後依 `FormPathUniqueEnum.PACKAGING.path = "packagingMaterials"` 啟動 BPM；通過後 listener 把狀態設為「已歸檔」。
30. 作為**採購人員**，我想分頁查詢包材、查詢簽核待辦、匯出 Excel；並提供 `/获得包材維護子表列表` 與 `/获得所有包材維護子表列表`（不分主表的全平表）。
31. 作為**廠商報價作業（PMM/VQM）**，我想以 `prodCode` 反查包材明細，找到貨源（被 PMM 的 `VendorQuoteMaintenance.getVendorQuoteByProdCode` 消費）。

### 編碼類別維護（Excel #15）

32. 作為**商品管理員**，我想維護**編碼類別（CodeCategory）**，定義類別代碼（code）、名稱（name）、此類別的碼長（len，位數）。
33. 作為**商品管理員**，我想分頁查詢、單筆與批次刪除、匯出 Excel。
34. 作為**商品管理員**，類別代碼（code）作為下游 `pdm_code_structure_detail.category_code` 與 `pdm_code_item.category` 的字串引用鍵，**不可隨意修改**——刪除前需檢查引用情況。

### 編碼項目維護（Excel #16）

35. 作為**商品管理員**，我想為每個**類別**下新增多個**編碼品項（CodeItem）**，含類別字串（category）、品項代碼（code）、父代碼（parentCode，樹形結構）、名稱（name）。
36. 作為**商品管理員**，編碼品項是整個 PDM 體系的 **CodeItem ID** 來源（被食材的 mainCategory / category / subcategory / source、食譜的 mainCategory / itemCategory / itemName、規格的 ingredientStatus / basicProcessing 等多處字串引用）。

### 編碼原則維護（Excel #17）

> 「編碼原則」是 4 張表構成的階層體系，目的是**動態定義品號編碼規則**，並支援 BOM 展開。

#### 編碼結構（CodeStructure）

37. 作為**商品管理員**，我想建立**編碼結構（CodeStructure）**，定義結構名稱與層級數（level，如 3 層）。

#### 編碼結構明細（CodeStructureDetail）

38. 作為**商品管理員**，我想為一筆結構新增多筆**明細（CodeStructureDetail）**，定義每層的 `serial_no`、`category_code`（指向 `pdm_code_category.code`）。
39. 作為**商品管理員**，我想匯出含**儲存類型**（`SHORT/LONG` from `pdm_ingredient_subcategory_type`）的結構明細 Excel — 由 `CodeStructureDetailController.導出編碼結構維護子類 Excel（含庫存類型）` 提供。

#### 編碼 BOM（CodeBom）+ BOM 關聯（CodeBomRelation）

40. 作為**商品管理員**，我想建立**編碼 BOM（CodeBom）**，定義一個產品的：名稱（name）、代碼（code）、編碼結構代碼（structure）、BOM 類別（bomCategory）、BOM 層級（bomLevel）、計量單位（unit）、備註。
41. 作為**商品管理員**，我想為 BOM 建立**關聯（CodeBomRelation）**：parentId / childId（隱含於關聯設計）、用量（qty）。
42. 作為**商品管理員**，我想呼叫 `/pdm/code-bom/获得編碼BOM明細` 取得整個 BOM 的展開明細（含 `code_bom_relation` 遞迴展開——目前展開規則為 **[UNKNOWN U-4]**，需業務確認）。

### 營養成分定義維護表（Excel #18）

43. 作為**管理員**，我想維護**營養定義（NutritionalDefinitions）**，定義熱量、蛋白質、脂肪等項目：中文名稱、英文名稱、計量單位 ID（FK→`pdm_unit_def`）、每餐建議攝取量（averageMealRecommendedIntake）、是否預設項目（defaultIngredient）、排列順序（sort）。
44. 作為**管理員**，我想分頁查詢、單筆／批次刪除、匯出 Excel；**注意目前「刪除」邏輯內標為 TODO**：刪除前需檢查是否被 `pdm_ingredient_nutritional_contents` / `pdm_recipe_nutritional_contents` 引用（[UNKNOWNS U-3](../UNKNOWNS.md#u-3)）。

### 餐食類型維護表（Excel #19）

45. 作為**管理員**，我想維護**餐食類型（MealType）**：中文名稱、英文名稱、狀態（status）。
46. 作為**管理員**，我想分頁查詢、單筆／批次刪除、匯出 Excel；同上，刪除邏輯目前為 TODO（[UNKNOWNS U-3](../UNKNOWNS.md#u-3)）— 需檢查 `pdm_recipe.meal_type` 是否引用。

### 單位定義維護表（Excel #20）

47. 作為**管理員**，我想維護**單位定義（PdmUnitDef）**：單位代碼（unit，如 `g`/`kg`/`ml`/`L`/`份`）、單位名稱（unitName）、小數位精度（precisionPlaces）、啟用狀態（status）。
48. 作為**管理員**，我想分頁查詢、批次刪除（軟刪除）；端點掛在 `/pdm/udf`（注意：路徑不是 `/pdm/unit-def`，是縮寫 udf）。

### 單位轉換維護表（Excel #21）

49. 作為**管理員**，我想維護**單位換算（PdmUnitConv）**：基礎單位（baseUnit）、目標單位（targetUnit）、換算比率（ratio）、備註。
50. 作為**所有消費者**，我必須遵守換算方向約定：**`target = base × ratio`**（例：1 kg = 1000 g，則 `base="kg", target="g", ratio=1000`）。此約定無 DB enforce，僅靠規格與程式碼一致性維持。
51. 作為**廠商報價作業（PMM/VQM）**，我想呼叫 `PdmUnitConv` 的換算邏輯計算「單一計數計量」（被 `VendorQuoteMaintenanceServiceImpl.calculateSingleCountMeasure` 消費）。

### 門市分群維護表（Excel #22）— 外部唯讀

52. 作為**所有消費者**，我必須清楚：**PDM 不擁有「門市分群」資料**。它由漢堡王中繼系統管理，本 ERP 透過 `BurgerKingStoreClient` 拉取。
53. 作為**任何模組**，我可呼叫以下 FeignClient 取得門市分群：
    - `getGroupWithStoresInner` → `/api/burgerking/admin/store/group-with-stores/inner`：群組與門市清單（內部用）
    - `getAllAreasWithStores` → `/api/burgerking/admin/area-group/all-areas-with-stores`：完整區域 → 門市層級
    結果結構：`AreaGroupHierarchyVO`（areaId, areaName, regionId, regionName, storeId, storeName, storeCode）。
54. 作為**任何模組**，當需要把門市資訊持久化到本系統時（如 `crg_demand_forecast.store_region` / `crg_demand_forecast.region_id` / `crg_demand_forecast.store_id`），我必須複製成「冗餘欄位」存放，不建立外鍵；中繼資料更新時本地副本可能過期，需在業務流程中刷新或對齊。

### 物流類型維護表（Excel #23）

55. 作為**物流管理員**，我想維護**物流類型（LogisticsType）**：物流名稱（logisticsName）、配送方式（deliveryMode，如「直送」/「配送」）、週期類型（cycleType，`weekly`/`monthly`）、物流週期日（logisticsCycle，逗號分隔的日期，例 `"1,3,5"` 或 `"5,15,25"`）、資料提供方式（dataType）、預設旗標（defaultStr：`"0"=預設, "1"=非預設`）、備註。
56. 作為**物流管理員**，我想設定某一物流類型為**預設**，讓需求行事曆與廠商報價自動套用。
57. 作為**所有消費者**（廠商報價、原物料需求行事曆、物流單），我可透過 `pdm_logistics_type.id` 引用。

### 橫切共同行為

58. 作為**所有 PDM 表**，皆繼承 `BaseDO`（`deleted` 軟刪除、`tenant_id` 多租戶、`creator` / `create_time` / `updater` / `update_time`、樂觀鎖 `revision`）。
59. 作為**所有 PDM 列表 API**，皆支援 `PageParam`（pageNo, pageSize）；匯出 Excel 時 `pageSize = PageParam.PAGE_SIZE_NONE` 取全部。
60. 作為**有 BPM 的 PDM 主檔**（食材 / 食譜 / 包材），皆遵循 `processStatus`（待處理 / 待簽核 / 已歸檔 / 已退件）+ `processInstanceId` 雙欄位模式；BPM Listener 透過 `businessKey = "{formPath}:{headerId}"` 區分業務。
61. 作為**API 消費者**，所有權限碼遵守 `pdm:{resource}:{action}` 規則（如 `pdm:ingredient:create`, `pdm:code-item:export`）。

---

## Implementation Decisions

### 1. 模組子域劃分（PDM 範圍）

| 子域 | 表 | API 前綴 | BPM | Excel |
|---|---|---|---|---|
| 編碼類別 | `pdm_code_category` | `/pdm/code-category` | — | #15 |
| 編碼項目 | `pdm_code_item` | `/pdm/code-item` | — | #16 |
| 編碼結構 | `pdm_code_structure` + `pdm_code_structure_detail` | `/pdm/code-structure`、`/pdm/code-structure-detail` | — | #17 |
| 編碼 BOM | `pdm_code_bom` + `pdm_code_bom_relation` | `/pdm/code-bom` | — | #17 |
| 食材 | `pdm_ingredient` + 4 子表 | `/pdm/ingredient`、`/pdm/ingredient-specs`、`/pdm/ingredient-compat`、`/pdm/ingredient-nutrition` | ✅ INGREDIENTS | #12 |
| 食譜 | `pdm_recipe` + 3 子表 | `/pdm/recipe` | ✅ RECIPE | #13 |
| 包材 | `pdm_packing_materials` + 1 子表 | `/pdm/packing-materials` | ✅ PACKAGING | #14 |
| 營養定義 | `pdm_nutritional_definitions` | `/pdm/nutritional-definitions` | — | #18 |
| 餐食類型 | `pdm_meal_type` | `/pdm/meal-type` | — | #19 |
| 單位定義 | `pdm_unit_def` | `/pdm/udf` ⚠️ | — | #20 |
| 單位換算 | `pdm_unit_conv` | `/pdm/unit-conv` | — | #21 |
| 物流類型 | `pdm_logistics_type` | `/pdm/logistics-type` | — | #23 |
| 門市分群 | （外部，無表）| 中繼 API 透過 `BurgerKingStoreClient` | — | #22 |

### 2. ER Model — PDM 範圍（不含需求集合 / 物流單 / 原物料需求行事曆）

```
編碼體系（4 表）
  pdm_code_category ─< pdm_code_structure_detail.category_code（字串引用）
                    ─< pdm_code_item.category（字串引用）
  pdm_code_structure ─< pdm_code_structure_detail.parent_id
                       └─ 1:1 → pdm_ingredient_subcategory_type.detail_id
                              （副類型 → SHORT/LONG 儲存類型）
  pdm_code_bom ─< pdm_code_bom_relation.parent_id（自參考組成 BOM 樹）

食材體系（5 表）
  pdm_ingredient (主)
    ├─< pdm_ingredient_specs.ingredient
    ├─< pdm_ingredient_compat.ingredient
    └─< pdm_ingredient_nutritional_contents.ingredient_id
                                    >── pdm_nutritional_definitions.id
  pdm_ingredient.main_category / category / subcategory / source
                                  >── pdm_code_item.id（CodeItem ID 引用）
  pdm_ingredient_specs.unit / single_spec_unit >── pdm_unit_def.id
  pdm_ingredient_specs.prod_code  → 漢堡王原物料產品代碼（字串引用，外部）

食譜體系（4 表）
  pdm_recipe (主)
    ├─< pdm_single_serving_recipe.recipe_id
    │     └ >── pdm_ingredient.id（食材引用）
    │     └ >── pdm_unit_def.id（單位引用）
    ├─< pdm_recipe_nutritional_contents.recipe_id
    │     └ >── pdm_nutritional_definitions.id
    └─< pdm_product_recipe_rel.recipe_id
          └ >── 漢堡王產品 ID（外部）
  pdm_recipe.meal_type >── pdm_meal_type.id

包材體系（2 表）
  pdm_packing_materials (主)
    └─< pdm_packing_materials_dtl.packing_materials_id
          └ >── pdm_unit_def.id（unit_id、single_spec_unit）

基礎主檔（4 表）
  pdm_nutritional_definitions.unit_id >── pdm_unit_def.id
  pdm_meal_type                       （獨立）
  pdm_unit_def                        （被多個表引用）
  pdm_unit_conv.base_unit / target_unit → pdm_unit_def.unit（字串引用）

外部對接
  pdm_logistics_type                  （獨立；被 PMM/VQM、PDM/RawMaterialDemand 引用）
  AreaGroupHierarchyVO (外部)         ──→ crg_demand_forecast.region_id / store_id
                                      ──→ pmm_vendor_quote_maintenance_detail.use_store_region_id
                                      （冗餘複製，無外鍵）
```

### 3. 完整資料表規格

#### 編碼體系（4 表）

##### `pdm_code_category`（編碼類別）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| code | VARCHAR | 類別代碼（如 "A"、"01"）|
| name | VARCHAR | 類別名稱 |
| len | INT | 此類別的碼長（位數）|
| revision | BIGINT | 樂觀鎖版本號 |
| + BaseDO | | deleted, tenant_id, creator, create_time, updater, update_time |

##### `pdm_code_structure`（編碼結構）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| name | VARCHAR | 結構名稱 |
| level | SMALLINT | 層級數 |
| revision | BIGINT | 樂觀鎖 |

##### `pdm_code_structure_detail`（編碼結構明細）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| serial_no | INT | 層級序號 |
| parent_id | BIGINT FK→`pdm_code_structure` | 所屬結構 |
| category_code | VARCHAR | 對應類別代碼（字串引用 `pdm_code_category.code`）|
| revision | BIGINT | 樂觀鎖 |

##### `pdm_code_item`（編碼項目）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| category | VARCHAR | 所屬類別代碼（引用 `pdm_code_category.code`）|
| code | VARCHAR | 品項代碼 |
| parent_code | VARCHAR | 父代碼（樹形結構）|
| name | VARCHAR | 品項名稱 |

##### `pdm_code_bom`（編碼 BOM）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| name | VARCHAR | 產品名稱 |
| code | VARCHAR | 產品代碼 |
| structure | VARCHAR | 編碼結構代碼 |
| bom_category | VARCHAR | BOM 類別（枚舉）|
| bom_level | SMALLINT | BOM 層級 |
| remark | VARCHAR | 備註 |
| unit | VARCHAR | 計量單位 |

##### `pdm_code_bom_relation`（BOM 關聯）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| parent_id | BIGINT FK→`pdm_code_bom` | 父 BOM |
| child_id | BIGINT FK→`pdm_code_bom`（隱含）| 子 BOM |
| qty | DECIMAL | 用量數量 |
| deleted | INT | 軟刪除 |

#### 食材體系（5 表）

##### `pdm_ingredient`（食材主檔）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| sign_code | VARCHAR | 簽核代碼（系統生成）|
| structure | BIGINT | 編碼結構 ID |
| main_category | BIGINT FK→`pdm_code_item` | 大分類 |
| category | BIGINT FK→`pdm_code_item` | 食材類型 |
| subcategory | BIGINT FK→`pdm_code_item` | 副類型（決定 SHORT/LONG 儲存類型）|
| source | BIGINT FK→`pdm_code_item` | 料源 |
| season | VARCHAR | 季節資訊 |
| cooking_method | VARCHAR | 建議烹調方式 |
| precautions | VARCHAR | 前處理注意事項 |
| process_status | VARCHAR | 審批狀態（待處理 / 待簽核 / 已歸檔 / 已退件）|
| subject | VARCHAR | 主旨 |
| workflow_id | VARCHAR | 工作流 ID（保留欄位）|
| create_department | VARCHAR | 建立部門 |
| process_instance_id | VARCHAR | Flowable 流程實例 ID |

##### `pdm_ingredient_specs`（食材規格）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| ingredient | BIGINT FK→`pdm_ingredient` | 所屬食材 |
| name | VARCHAR | 規格名稱 |
| wastage_rate | DECIMAL | 損耗率（%）|
| ingredient_status | BIGINT FK→`pdm_code_item` | 食材狀態 |
| basic_processing | BIGINT FK→`pdm_code_item` | 基本加工方式 |
| seasoning_processing | BIGINT FK→`pdm_code_item` | 調味加工方式 |
| storage_method | BIGINT FK→`pdm_code_item` | 儲存方式 |
| serial_code1 / serial_code2 | VARCHAR | 序號碼 1 / 2 |
| prod_code | VARCHAR | 漢堡王原物料產品編號（業務 key，跨系統）|
| unit | BIGINT FK→`pdm_unit_def` | 計量單位 |
| lead_time | VARCHAR | 前置時間 |
| status | INT | 啟用狀態（0=啟用, 1=停用）|
| single_spec | DECIMAL | 單份規格量 |
| single_spec_unit | BIGINT FK→`pdm_unit_def` | 單份規格單位 |
| material_product_id | INT | 漢堡王原物料產品 ID |

##### `pdm_ingredient_compat`（食材相生相剋）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| ingredient | BIGINT FK→`pdm_ingredient` | 所屬食材 |
| category | BIGINT FK→`pdm_code_item` | 比對類型 |
| subcategory | BIGINT FK→`pdm_code_item` | 比對副類型 |
| source | BIGINT FK→`pdm_code_item` | 比對料源 |
| description | VARCHAR | 說明 |
| compat | INT | 1=相容, 0=不相容 |

##### `pdm_ingredient_nutritional_contents`（食材營養成分）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| ingredient_id | BIGINT FK→`pdm_ingredient` | 所屬食材 |
| nutritional_definition_id | BIGINT FK→`pdm_nutritional_definitions` | 營養定義項目 |
| serving_amount | DECIMAL | 每份含量 |
| unit | VARCHAR | 單位 |

##### `pdm_ingredient_subcategory_type`（副類型儲存類型，無 Controller）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| detail_id | BIGINT FK→`pdm_code_structure_detail` | 副類型結構明細 ID |
| category_code | VARCHAR | 類別代碼（冗餘）|
| storage_type | VARCHAR | `SHORT`=生鮮, `LONG`=凍品 |

#### 食譜體系（4 表）

##### `pdm_recipe`（食譜主檔）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| sign_code | VARCHAR | 簽核代碼 |
| structure | BIGINT | 編碼結構 ID |
| status | BOOLEAN | 食譜狀態 |
| main_category | BIGINT FK→`pdm_code_item` | 大分類 |
| item_category | BIGINT FK→`pdm_code_item` | 品項類別 |
| item_name | BIGINT FK→`pdm_code_item` | 品項 ID |
| item_sub_tag | VARCHAR | 品項子標籤 |
| cooking_method | VARCHAR | 烹調方式 |
| display_name | VARCHAR | 顯示名稱 |
| tag_name | VARCHAR | 標籤名稱 |
| product_code | VARCHAR | 產品代碼 |
| meal_type | VARCHAR FK→`pdm_meal_type` | 餐食類型 |
| portion_amount | VARCHAR | 單份份量 |
| amount_unit | VARCHAR | 份量單位 |
| portion_standard_cost | VARCHAR | 單份標準成本（NTD）|
| cooking_steps | VARCHAR | 烹調步驟 |
| cooking_tips | VARCHAR | 烹調技巧 |
| recipe_product_id | INT | 漢堡王產品 ID（被需求預測展開使用）|
| process_status | VARCHAR | 審批狀態 |
| process_instance_id | VARCHAR | Flowable 流程實例 ID |

##### `pdm_single_serving_recipe`（單份用量配方）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| recipe_id | BIGINT FK→`pdm_recipe` | 所屬食譜 |
| ingredient_id | BIGINT FK→`pdm_ingredient` | 食材 ID |
| prod_code | VARCHAR | 關聯食材/包材產品代碼 |
| standard_amount | DECIMAL | 標準用量 |
| unit | BIGINT FK→`pdm_unit_def` | 用量單位 |
| single_spec | DECIMAL | 單份規格 |
| single_spec_unit | BIGINT FK→`pdm_unit_def` | 單份規格單位 |
| default_supplier | VARCHAR | 預設廠商代碼 |
| latest_quote_price | DECIMAL | 最新報價（NTD/kg or L）|
| last_purchase_price | DECIMAL | 最後採購價格 |
| standard_amount_cost | DECIMAL | 標準用量成本（NTD）|

##### `pdm_recipe_nutritional_contents`（食譜營養成分）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| recipe_id | BIGINT FK→`pdm_recipe` | 所屬食譜 |
| nutritional_definition_id | BIGINT FK→`pdm_nutritional_definitions` | 營養定義項目 |
| serving_amount | DECIMAL | 每份含量 |
| unit | VARCHAR | 單位 |

##### `pdm_product_recipe_rel`（食譜 ↔ 產品關聯）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| recipe_id | BIGINT FK→`pdm_recipe` | 所屬食譜 |
| product_id | INT | 漢堡王產品 ID（外部）|
| （其他冗餘欄位）| | |

#### 包材體系（2 表）

##### `pdm_packing_materials`（包材主檔）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| sign_code | VARCHAR | 單據編號 |
| category | BIGINT FK→`pdm_code_item` | 包材類別 |
| subject | VARCHAR | 主旨 |
| process_status | VARCHAR | 流程狀態 |
| process_instance_id | VARCHAR | Flowable 流程實例 ID |

##### `pdm_packing_materials_dtl`（包材明細）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| packing_materials_id | BIGINT FK→`pdm_packing_materials` | 主表 ID |
| category | BIGINT FK→`pdm_code_item` | 包材類別 |
| name | VARCHAR | 包材名稱 |
| serial_number | VARCHAR | 流水編號（6 碼）|
| product_code | VARCHAR | 品號 |
| unit_id | BIGINT FK→`pdm_unit_def` | 計數單位 |
| single_spec | DECIMAL | 單一規格 |
| single_spec_unit | BIGINT FK→`pdm_unit_def` | 單一規格單位 |
| status | VARCHAR | 狀態 |

#### 基礎主檔（4 表）

##### `pdm_nutritional_definitions`（營養定義）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| name | VARCHAR | 中文名稱（熱量、蛋白質…）|
| eng_name | VARCHAR | 英文名稱 |
| unit_id | BIGINT FK→`pdm_unit_def` | 計量單位 |
| average_meal_recommended_intake | VARCHAR | 每餐建議攝取量 |
| default_ingredient | BOOLEAN | 是否為預設項目 |
| sort | BIGINT | 排列順序 |

##### `pdm_meal_type`（餐食類型）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| name | VARCHAR | 中文名稱 |
| eng_name | VARCHAR | 英文名稱 |
| status | VARCHAR | 狀態 |

##### `pdm_unit_def`（單位定義）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| unit | VARCHAR | 單位代碼（g, kg, ml, L, 份…）|
| unit_name | VARCHAR | 單位名稱 |
| precision_places | INT | 小數位精度 |
| status | BOOLEAN | 啟用狀態 |

##### `pdm_unit_conv`（單位換算）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| base_unit | VARCHAR | 基礎單位代碼（引用 `pdm_unit_def.unit`）|
| target_unit | VARCHAR | 目標單位代碼 |
| ratio | DECIMAL | 換算比率（`target = base × ratio`）|
| remarks | VARCHAR | 備註 |

#### 物流類型（1 表）

##### `pdm_logistics_type`（物流類型）

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | BIGINT PK | 主鍵 |
| logistics_name | VARCHAR | 物流名稱 |
| delivery_mode | VARCHAR | 配送方式（直送 / 配送）|
| cycle_type | VARCHAR | 週期類型（weekly / monthly）|
| logistics_cycle | VARCHAR | 物流週期日（逗號分隔）|
| data_type | VARCHAR | 資料提供方式 |
| default_str | VARCHAR | 預設旗標（"0"=預設, "1"=非預設）|
| remark | VARCHAR | 備註 |

#### 外部對接（無本地表）

##### `AreaGroupHierarchyVO`（漢堡王中繼回應）

| 欄位 | 來源欄位 | 說明 |
|---|---|---|
| areaId / areaName | 中繼 | 區域 |
| regionId / regionName | 中繼 | 區域群組（用於 demandForecastConfigScope.regionId）|
| storeId / storeName / storeCode | 中繼 | 門市 |

> PDM 不寫入此資料；任何模組需要持久化時自行冗餘複製。

### 4. BPM 整合規範（PDM 範圍）

| 模組 | `FormPathUniqueEnum` | path 值 | businessKey 格式 | Listener |
|---|---|---|---|---|
| 食材 | `INGREDIENTS` | `ingredients` | `ingredients:{ingredientId}` | `IngredientStatusListener` |
| 食譜 | `RECIPE` | `recipe` | `recipe:{recipeId}` | `RecipeStatusListener` |
| 包材 | `PACKAGING` | `packagingMaterials` | `packagingMaterials:{packingMaterialsId}` | `PackingMaterialsStatusListener` |

統一行為：
- 建立單據時呼叫 `MenuFlowProcessInstanceHelper.createProcessInstanceIfFlowOpen(userId, formPath, headerId)`；若選單已綁定流程則啟動 Flowable 並回填 `process_instance_id`；否則略過 BPM。
- Listener 監聽 `BpmProcessInstanceStatusEvent`，以 `businessKey` 前綴判斷是否屬於自己；APPROVE → `process_status = "已歸檔"`；REJECT/CANCEL 目前為預留行為（後續可實作「退回待處理」或「退件」）。
- 已歸檔且 `process_instance_id` 為空者不可再更新（拋對應的 `*_ARCHIVED_CANNOT_UPDATE` 錯誤碼）。

### 5. 跨模組消費表

| PDM 表 | 消費模組 | 用途 |
|---|---|---|
| `pdm_ingredient_specs.prod_code` | PMM/VQM、PMM/PurReq、WHS/Stock | 跨系統識別食材的 key |
| `pdm_ingredient_specs.material_product_id` | PDM/RawMaterialLogisticsDtl（物流單） | 漢堡王原物料對應 |
| `pdm_recipe + pdm_product_recipe_rel + pdm_single_serving_recipe` | DemandAggregation/DemandForecast | 產品 → 食譜 → 食材的展開鏈 |
| `pdm_packing_materials_dtl.product_code` | PMM/VQM `getVendorQuoteByProdCode` | 包材報價查詢 |
| `pdm_logistics_type.id` | PMM/VQM `useDeliveryType`、PDM/RawMaterialDemand `use_delivery_type` | 物流預設套用 |
| `pdm_unit_def.id` | 全 ERP 計量單位 | 單位 ID 引用 |
| `pdm_unit_conv` | PMM/VQM `calculateSingleCountMeasure` | 包裝量單位換算 |
| `pdm_meal_type.id` | PDM/Recipe | 食譜分類 |
| `pdm_nutritional_definitions.id` | PDM/Ingredient、PDM/Recipe | 營養成分引用 |
| `pdm_ingredient_subcategory_type.storage_type` | DemandAggregation/DemandForecast | LONG/SHORT 分支判斷 |
| `pdm_code_item.id` | 整個 PDM 與其他模組 | CodeItem ID 引用（最常用的 lookup 鍵）|

### 6. 命名／路由不一致（保留現況、規格記錄）

- 單位定義端點掛在 **`/pdm/udf`** 而非 `/pdm/unit-def`（與其他資源不一致）。維持現況以避免破壞前端；若日後重構，需同步更新前端與權限碼。
- 食材子表用 `/pdm/ingredient-specs`、`/pdm/ingredient-compat`、`/pdm/ingredient-nutrition`，前綴形式與主表不一致（主表單數、子表單數但帶連字符）— 維持現況。
- 部分權限碼以 `pdm:code-item:query` 等小寫連字符，與表名 `pdm_code_item` 對齊。

### 7. 不要再做的事

- **不要為「門市分群」(#22) 在 PDM 內建表** — 它是漢堡王中繼的主檔，本系統只能消費。
- **不要把 `pdm_code_bom` 與「食譜 SingleServingRecipe」視為同一概念** — 前者是品號編碼層級結構（用於命名規則），後者是實際銷售食譜的食材配方（用於需求展開）。
- **不要硬刪除任何 PDM 主檔** — 全模組依賴軟刪除（`deleted=1`）；硬刪會破壞跨模組字串引用。
- **不要繞過 BPM 直接修改 `process_status = "已歸檔"`** — 已歸檔但無 `process_instance_id` 者後續修改一律拒絕。

---

## Testing Decisions

### 好測試的判準

- 測**外部行為**而非實作細節：給定 CodeItem ID 與 mainCategory 引用，呼叫 `IngredientController.create` 並送出 → 驗證 `pdm_ingredient` 寫入、`sign_code` 生成、`process_instance_id` 視 BPM 設定回填。
- **不要**測 BeanUtils 轉換、Mapper insertBatch 內部行為、BaseDO tenant_id 注入等框架行為。
- 寫**整合測試**而非單元測試：PDM 的價值在於「主檔 + 子表」與「BPM 流轉」的聯動。

### 應測模組（建議優先序）

| 優先序 | 模組 | 場景 |
|---|---|---|
| P0 | 食材主檔 BPM 觸發 | 啟動流程、回填 `process_instance_id`；APPROVE → 「已歸檔」 |
| P0 | 食材子表級聯刪除 | 刪除食材 → 規格 / 相生相剋 / 營養成分子表同步軟刪 |
| P0 | 食譜 + 單份配方 | 建立食譜後新增多筆 single-serving；`/获得食譜-单份食谱子表信息` 正確回傳 |
| P1 | 包材主檔 + 明細 | 建立包材主檔後批量寫入明細；BPM 流轉；Excel 匯出 |
| P1 | 編碼結構→明細→Excel（含庫存類型）| `subcategory_type` join 正確；匯出檔欄位完整 |
| P2 | 單位換算 | base→target = base × ratio；PMM 端呼叫 `calculateSingleCountMeasure` 正確 |
| P2 | 營養定義刪除攔截 | 當已被 `ingredient_nutritional_contents` 引用時應拒絕（**目前 TODO**）|
| P2 | 餐食類型刪除攔截 | 當已被 `pdm_recipe.meal_type` 引用時應拒絕（**目前 TODO**）|
| P3 | 物流類型「預設」唯一性 | 同一時間僅一筆 `default_str=0`（如業務要求；目前 schema 無 enforce）|

### 既有測試參考

目前 `erp-spring` 無自動化測試。手動驗證走 Swagger UI（`http://localhost:48080/doc.html`），先用 `application-local.yaml` 連測試庫，再以 Postman 跑「建立食材 → 子表 → 送 BPM → APPROVE → 查歸檔」端到端 happy path。

---

## Out of Scope

以下項目雖在原 v1 PDM_PRD 內，但**不屬於 Excel PDM (#12-23) 範圍**，已移交其他 PRD：

| 原 v1 內容 | 程式對應 | 新歸屬 |
|---|---|---|
| 需求預測設定 | `crg_demand_forecast_config` + `crg_demand_forecast_config_scope` + Controller | [`DEMAND_AGGREGATION_PRD.md`](DEMAND_AGGREGATION_PRD.md)（Excel #24-25） |
| 需求預測作業 | `crg_demand_forecast` + `crg_demand_forecast_detail` | 同上 |
| 臨時需求 | `crg_temp_req` + `crg_temp_req_detail` | 同上（Excel #26） |
| 原物料需求行事曆 | `pdm_raw_material_demand_head` + `_date_list` + `_detail` | 待寫獨立 PRD（Excel #30） |
| 物流單 | `pdm_raw_material_logistics` + `_dtl` | 待寫獨立物流 PRD（Excel #48-52） |
| 需求預測計算公式 | `DemandForecastServiceImpl.buildIngredientDetail` | [`DEMAND_AGGREGATION_PRD.md`](DEMAND_AGGREGATION_PRD.md) |
| 漢堡王中繼 API 完整對接 | `BurgerKingStoreClient` 全部端點 | [`CONTEXT.md`](../CONTEXT.md) §外部系統整合（已存在）|

其他不在本 PRD：

- **前端 UI 規格** — 本 PRD 僅還原後端規格與 API。
- **BPM 流程模型本身** — 各單據的審批節點、簽核人選擇策略屬於 BPM 模組職責。
- **BHM 模組** — 已凍結。
- **資料庫遷移腳本** — 目前無 Flyway/Liquibase，手動 SQL 管理。

---

## Further Notes

### 已知缺口 / TODO（對應 [`UNKNOWNS.md`](../UNKNOWNS.md)）

| UNKNOWN | 問題 | 影響本 PRD 的範圍 |
|---|---|---|
| **U-3** | 食材／食譜的「營養成分子表」刪除攔截邏輯未實作（`MealTypeServiceImpl`、`NutritionalDefinitionsServiceImpl` 內有 TODO）| 影響 [`pdm_nutritional_definitions`](#pdm_nutritional_definitions營養定義)、[`pdm_meal_type`](#pdm_meal_type餐食類型) 的「批次刪除」行為 |
| **U-4** | BOM 展開規則未明 | 影響 `pdm_code_bom_relation` 的遞迴展開語意；同時也是需求預測對食材展開的前置（雖此邏輯目前走 `pdm_product_recipe_rel`，不走 `pdm_code_bom`）|
| — | `pdm_ingredient_subcategory_type` 無 Controller / Service | 需要透過 SQL 維護；未來需補建 CRUD API 才能讓業務維護 SHORT/LONG 分類 |

### 程式碼異味（建議後續整理，不在本 PRD 修改範圍）

- **路由命名不一致**：單位定義用 `/pdm/udf`、其他用全名連字符；食材主／子表前綴混用。
- **CodeBom Relation 的 child_id 欄位**程式碼中未明確標示，需檢查 DO 並補上 Schema 註解。
- **食譜 `cookingSteps` / `cookingTips`** 為 VARCHAR — 若步驟很多會被截斷；建議改為 TEXT 或結構化欄位。
- **「漢堡王原物料產品 ID」散落多處**：`pdm_ingredient_specs.material_product_id`、`pdm_recipe.recipe_product_id`、`pdm_product_recipe_rel.product_id`、`pdm_raw_material_logistics_dtl.material_product_id` — 命名不一致；建議規範統一為 `bk_product_id` 或 `material_product_id`。
- **食譜的 `portion_amount`、`portion_standard_cost`** 為 VARCHAR — 應為數值型別；目前可能存在「跨筆比較或計算時需 parse」的隱性風險。

### 與其他 PRD 的引用關係

- 上游主檔：本 PRD（PDM）→ 下游消費：[`PMM_PRD.md`](PMM_PRD.md)、[`DEMAND_AGGREGATION_PRD.md`](DEMAND_AGGREGATION_PRD.md)、WHS_PRD（待寫）
- PDM 食材／食譜的 BPM 流程定義由 BPM 模組（Flowable）擁有，本 PRD 僅描述 PDM 端的整合介面。

### 後續可擴充（不在本 PRD 範圍）

- 為 `pdm_ingredient_subcategory_type` 補建 CRUD Controller，讓業務方可以在前端維護 SHORT/LONG 分類。
- 整合 `pdm_nutritional_definitions` / `pdm_meal_type` 的刪除引用檢查（補完 U-3）。
- 對「BOM 展開」(`pdm_code_bom_relation` 遞迴)補完規格與單元測試（U-4）。
- 為單位換算建立**雙向自動互算**：目前只記錄 `base→target = base × ratio` 一個方向，反向需業務自行計算 `1/ratio`，可考慮在 Service 層加 `convert(value, fromUnit, toUnit)` 統一介面。
