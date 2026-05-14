# PRD：PDM 商品資料 + 需求預測模組（逆向規格分析）

> 本文件透過逆向分析 `erp-spring` 程式碼，還原 PDM 模組的完整業務規格、資料表設計、ER Model 與功能清單。

---

## Problem Statement

漢堡王台灣缺乏完整的 PDM 模組書面規格。目前程式碼已實作大部分功能，但：
- 無正式業務規格文件，新進人員或 AI Agent 必須從程式碼逆推
- 部分功能（需求預測歸檔後觸發原物料需求、安全庫存計算標準）尚有 TODO，無規格可循
- ER Model 與資料表關聯未有統一文件
- 需求預測計算公式散落在 `DemandForecastServiceImpl`，無法被業務人員驗證

---

## Solution

產出本 PRD，作為 PDM 模組的**權威規格文件**，涵蓋：
1. 完整 ER Model（10 個子域、27 張資料表）
2. 每張資料表的欄位清單與說明
3. 所有業務流程的步驟規格
4. 需求預測計算公式還原
5. BPM 審批流綁定規範
6. 外部系統整合點（漢堡王中繼 API）
7. 未解決的規格問題（UNKNOWNS）

---

## User Stories

### 編碼管理

1. 作為**商品管理員**，我想維護**編碼類別（CodeCategory）**，以便定義品號編碼的分類與碼長
2. 作為**商品管理員**，我想維護**編碼結構（CodeStructure）**，以便建立品號的層級規則（Level 1/2/3）
3. 作為**商品管理員**，我想在編碼結構下新增**編碼結構明細（CodeStructureDetail）**，以便指定每層對應的類別與排序
4. 作為**商品管理員**，我想維護**編碼品項（CodeItem）**，以便建立各類別下的具體選項（主類、副類、料源等）
5. 作為**商品管理員**，我想維護**BOM 結構（CodeBom）**，定義產品的物料清單層級與數量
6. 作為**商品管理員**，我想設定**BOM 關聯（CodeBomRelation）**，定義父子 BOM 間的組成數量

### 食材管理

7. 作為**研發人員**，我想建立**食材主檔（Ingredient）**，填寫大分類、食材類型、副類型、料源、烹調方式、注意事項
8. 作為**研發人員**，我想為一筆食材新增多筆**規格（IngredientSpecs）**，每筆規格含名稱、損耗率、單位、前置時間、產品編號（prodCode）
9. 作為**研發人員**，我想設定食材的**相生相剋（IngredientCompat）**，標記哪些食材類型組合相容或不相容
10. 作為**研發人員**，我想記錄食材的**營養成分（IngredientNutritionalContents）**，對應至標準營養定義（NutritionalDefinitions）
11. 作為**研發人員**，我想送出食材主檔，觸發 **BPM 審批流**，讓主管審核後才能歸檔
12. 作為**審核主管**，我想在**待辦清單（todo-page）**中看到待審食材，逐一審核或退件
13. 作為**商品管理員**，我想批次查詢與匯出食材資料，以便核對供應商規格

### 食譜管理

14. 作為**研發人員**，我想建立**食譜主檔（PdmRecipe）**，填寫餐點類型、烹調方式、標準份量與成本
15. 作為**研發人員**，我想在食譜下設定**單份配方（PdmSingleServingRecipe）**，指定每份所需食材、標準用量、最新報價
16. 作為**研發人員**，我想記錄食譜的**營養成分（RecipeNutritionalContents）**，對應至標準營養定義
17. 作為**研發人員**，我想建立**食譜與漢堡王產品的對應關係（PdmProductRecipeRel）**，讓系統在銷售資料中識別對應食材需求
18. 作為**研發人員**，我想送出食譜，觸發 BPM 審批流
19. 作為**審核主管**，我想在待辦清單中看到待審食譜，審核後食譜歸檔

### 包材管理

20. 作為**採購人員**，我想建立**包材主檔（PackingMaterials）**，填寫分類與主旨
21. 作為**採購人員**，我想在包材主檔下新增多筆**包材明細（PackingMaterialsDtl）**，填寫名稱、序號、產品編號、單位規格
22. 作為**採購人員**，我想送出包材維護單，觸發 BPM 審批流

### 營養定義管理

23. 作為**管理員**，我想維護**營養定義（NutritionalDefinitions）**，定義熱量、蛋白質等標準營養項目的名稱、單位與建議攝取量
24. 作為**管理員**，我想設定**餐食類型（MealType）**，如早餐、午餐、套餐等，讓食譜分類使用

### 單位管理

25. 作為**管理員**，我想維護**單位定義（PdmUnitDef）**，定義 kg、g、份等單位與精度
26. 作為**管理員**，我想建立**單位換算（PdmUnitConv）**，設定基礎單位到目標單位的換算比率

### 物流類型管理

27. 作為**物流管理員**，我想建立**物流類型（LogisticsType）**，定義直送或配送、週期（每週/每月）、物流週期日與資料提供方式
28. 作為**物流管理員**，我想設定某一物流類型為**預設**，讓需求行事曆自動套用

### 需求預測設定

29. 作為**採購主管**，我想建立**需求預測設定（DemandForecastConfig）**，定義預測模式（區域-季）、排程表達式（Cron）、需求週數、銷售天數與預測增量百分比
30. 作為**採購主管**，我想設定每個預測設定的**適用範圍（DemandForecastConfigScope）**，指定哪些區域或門市要套用此設定
31. 作為**採購主管**，我想在啟用設定前**預檢衝突（precheck）**，系統告知哪些門市已被其他設定覆蓋
32. 作為**採購主管**，我想手動**立即執行**某個預測設定，無需等排程觸發
33. 作為**採購主管**，我想停用某個設定，系統停止對應門市的排程預測

### 需求預測作業

34. 作為**門市採購人員**，我想選擇**區域/群組與門市**（透過漢堡王中繼 API 查詢），建立需求預測單
35. 作為**門市採購人員**，我想設定**預測週（weekStartDate / weekEndDate）**與**銷售分析時段（salesStartDate / salesEndDate）**
36. 作為**門市採購人員**，我想設定**預測增量百分比**（如 1.05 = 105%），讓系統在歷史基準上提高預測值
37. 作為**門市採購人員**，我想呼叫**產品食譜分析（product-recipe-analysis）**，系統自動：
    a. 從漢堡王中繼 API 拉取該時段的完成訂單銷售統計
    b. 比對本系統食譜，展開成食材需求明細
    c. 計算每萬元平日/假日平均用量與預測用量
    d. 對於**長效食材**（LONG），比對安全庫存，若低於安全庫存才顯示需求量
38. 作為**門市採購人員**，我想在前端調整平日/假日銷售數字後，呼叫**重新計算（calculate-projected-sales）**，系統即時更新預測值
39. 作為**門市採購人員**，我想儲存需求預測單（含明細），並送出 BPM 審批流
40. 作為**審核主管**，我想在待辦清單中審核需求預測單，核准後系統將狀態改為「已歸檔」
41. 作為**系統**，需求預測核准後，自動觸發**原物料需求行事曆**的建立（TODO - 尚未實作）
42. 作為**採購人員**，我想分頁查詢需求預測單，按區域、門市、日期區間、審批狀態篩選

### 臨時需求

43. 作為**門市人員**，我想建立**臨時需求單（TempReq）**，在正式預測週期外申請額外食材
44. 作為**門市人員**，我想在臨時需求單下填寫**明細（TempReqDetail）**，指定產品、申請數量與最終核定數量
45. 作為**審核主管**，我想審核臨時需求單，核准後系統更新臨時需求最終數量

### 原物料需求行事曆

46. 作為**採購人員**，我想查看**原物料需求行事曆（RawMaterialDemandHead）**，以門市與食材分類為維度，看到各日期的需求量
47. 作為**採購人員**，我想查詢特定月份的需求明細，以報表形式看到每個日期、每個食材的需求量與預計交貨日
48. 作為**採購人員**，我想按**交貨日期**分組查詢需求，以便規劃每次到貨的採購清單
49. 作為**物流系統**，我想**產生 CSV 匯出（generateCsv）**，對接 MSS 物流系統的每日出貨計畫

### 物流單

50. 作為**物流管理員**，我想建立**物流單（RawMaterialLogistics）**，記錄每次配送的出貨日與廠商
51. 作為**物流管理員**，我想在物流單下填寫**明細（RawMaterialLogisticsDtl）**，記錄每個品項的實際到貨量與門市代碼
52. 作為**採購主管**，我想匯出物流單，以便核對廠商出貨紀錄

---

## Implementation Decisions

### 模組子域劃分

| 子域 | 核心資料表 | 說明 |
|------|-----------|------|
| 編碼管理 | pdm_code_category, pdm_code_structure, pdm_code_structure_detail, pdm_code_item, pdm_code_bom, pdm_code_bom_relation | 品號編碼規則與 BOM 結構定義 |
| 食材管理 | pdm_ingredient, pdm_ingredient_specs, pdm_ingredient_compat, pdm_ingredient_nutritional_contents, pdm_ingredient_subcategory_type | 食材主檔與規格，含 BPM 審批流 |
| 食譜管理 | pdm_recipe, pdm_single_serving_recipe, pdm_recipe_nutritional_contents, pdm_product_recipe_rel | 食譜與單份配方，關聯漢堡王產品 |
| 包材管理 | pdm_packing_materials, pdm_packing_materials_dtl | 包材維護，含 BPM 審批流 |
| 營養定義 | pdm_nutritional_definitions, pdm_meal_type | 基礎資料：營養項目與餐食類型 |
| 單位管理 | pdm_unit_def, pdm_unit_conv | 單位定義與換算 |
| 物流管理 | pdm_logistics_type, pdm_raw_material_logistics, pdm_raw_material_logistics_dtl | 物流類型設定與物流單 |
| 需求預測設定 | crg_demand_forecast_config, crg_demand_forecast_config_scope | 排程設定與適用範圍 |
| 需求預測作業 | crg_demand_forecast, crg_demand_forecast_detail | 需求預測單頭單身 |
| 原物料需求 | pdm_raw_material_demand_head, pdm_raw_material_demand_detail, pdm_raw_material_demand_date_list | 行事曆式的原物料需求 |
| 臨時需求 | crg_temp_req, crg_temp_req_detail | 週期外的臨時需求申請 |

---

### ER Model（文字描述）

```
編碼管理:
  pdm_code_category (1) ──< pdm_code_structure_detail (category_code FK)
  pdm_code_structure (1) ──< pdm_code_structure_detail (parent_id FK)
  pdm_code_structure_detail (1) ──── pdm_ingredient_subcategory_type (detail_id FK)
  pdm_code_bom (1) ──< pdm_code_bom_relation (parent_id FK)
  pdm_code_item (多) ── code 被多個子域以字串方式引用

食材管理:
  pdm_ingredient (1) ──< pdm_ingredient_specs (ingredient FK)
  pdm_ingredient (1) ──< pdm_ingredient_compat (ingredient FK)
  pdm_ingredient (1) ──< pdm_ingredient_nutritional_contents (ingredient_id FK)
  pdm_ingredient_nutritional_contents >── pdm_nutritional_definitions (nutritional_definition_id FK)
  pdm_ingredient_specs >── pdm_unit_def (unit FK, single_spec_unit FK)

食譜管理:
  pdm_recipe (1) ──< pdm_single_serving_recipe (recipe_id FK)
  pdm_recipe (1) ──< pdm_recipe_nutritional_contents (recipe_id FK)
  pdm_recipe (1) ──< pdm_product_recipe_rel (recipe_id FK)
  pdm_single_serving_recipe >── pdm_ingredient (ingredient_id FK)
  pdm_single_serving_recipe >── pdm_unit_def (unit FK, single_spec_unit FK)
  pdm_recipe_nutritional_contents >── pdm_nutritional_definitions (nutritional_definition_id FK)

需求預測:
  crg_demand_forecast_config (1) ──< crg_demand_forecast_config_scope (config_id FK)
  crg_demand_forecast (1) ──< crg_demand_forecast_detail (parent_id FK)
  crg_demand_forecast_detail >── pdm_ingredient (ingredient_id FK)  [邏輯外鍵]
  crg_demand_forecast_detail >── pdm_product_recipe_rel (product_id 路徑)  [邏輯關聯]

原物料需求:
  pdm_raw_material_demand_head (1) ──< pdm_raw_material_demand_date_list (head_id FK)
  pdm_raw_material_demand_head (1) ──< pdm_raw_material_demand_detail (head_id FK)
  pdm_raw_material_demand_detail >── pdm_raw_material_demand_date_list (demand_date_id FK)
  pdm_raw_material_demand_detail >── pdm_logistics_type (use_delivery_type FK)
  pdm_raw_material_demand_detail 關聯 crg_demand_forecast (demand_relation_doc = signCode)

物流單:
  pdm_raw_material_logistics (1) ──< pdm_raw_material_logistics_dtl (parent_id FK)

臨時需求:
  crg_temp_req (1) ──< crg_temp_req_detail (parent_id FK)
```

---

### 資料表詳細規格

#### 1. `pdm_code_category`（編碼類別）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| code | VARCHAR | 類別代碼（如 "A"、"01"） |
| name | VARCHAR | 類別名稱 |
| len | INT | 此類別的碼長（位數） |
| revision | BIGINT | 樂觀鎖版本號 |
| + BaseDO 欄位 | | deleted, tenant_id, creator, create_time, updater, update_time |

#### 2. `pdm_code_structure`（編碼結構）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| name | VARCHAR | 結構名稱 |
| level | SMALLINT | 層級數（如 3 層結構） |
| revision | BIGINT | 樂觀鎖 |

#### 3. `pdm_code_structure_detail`（編碼結構明細）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| serial_no | INT | 序號 |
| parent_id | BIGINT FK→pdm_code_structure | 所屬結構 |
| category_code | VARCHAR FK→pdm_code_category.code | 對應類別代碼 |
| revision | BIGINT | 樂觀鎖 |

#### 4. `pdm_code_item`（編碼品項）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| category | VARCHAR FK→pdm_code_category.code | 所屬類別 |
| code | VARCHAR | 品項代碼 |
| parent_code | VARCHAR | 父代碼（樹形結構） |
| name | VARCHAR | 品項名稱 |

#### 5. `pdm_code_bom`（BOM 結構）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| name | VARCHAR | 產品名稱 |
| code | VARCHAR | 產品代碼 |
| structure | VARCHAR | 編碼結構代碼 |
| bom_category | VARCHAR | BOM 類別（枚舉）|
| bom_level | SMALLINT | BOM 層級 |
| remark | VARCHAR | 備註 |
| unit | VARCHAR | 計量單位 |

#### 6. `pdm_code_bom_relation`（BOM 關聯）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| parent_id | BIGINT FK→pdm_code_bom | 父 BOM |
| [child_id 隱含] | BIGINT FK→pdm_code_bom | 子 BOM（需確認） |
| qty | DECIMAL | 用量數量 |
| deleted | INT | 軟刪除（0=有效, 1=刪除）|

#### 7. `pdm_ingredient`（食材主檔）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| sign_code | VARCHAR | 簽核代碼（由系統生成） |
| structure | BIGINT | 編碼結構 ID |
| main_category | BIGINT FK→CodeItem | 大分類 ID |
| category | BIGINT FK→CodeItem | 食材類型 ID |
| subcategory | BIGINT FK→CodeItem | 副類型 ID |
| source | BIGINT FK→CodeItem | 料源 ID |
| season | VARCHAR | 季節資訊 |
| cooking_method | VARCHAR | 建議烹調方式 |
| precautions | VARCHAR | 前處理注意事項 |
| process_status | VARCHAR | 審批狀態（待處理/審批中/已歸檔）|
| subject | VARCHAR | 主旨 |
| workflow_id | VARCHAR | 工作流 ID |
| create_department | VARCHAR | 建立部門 |
| process_instance_id | VARCHAR | Flowable 流程實例 ID |
| + BaseDO 欄位 | | |

#### 8. `pdm_ingredient_specs`（食材規格）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| ingredient | BIGINT FK→pdm_ingredient | 所屬食材 |
| name | VARCHAR | 規格名稱 |
| wastage_rate | DECIMAL | 損耗率（%） |
| ingredient_status | BIGINT FK→CodeItem | 食材狀態 |
| basic_processing | BIGINT FK→CodeItem | 基本加工方式 |
| seasoning_processing | BIGINT FK→CodeItem | 調味加工方式 |
| storage_method | BIGINT FK→CodeItem | 儲存方式 |
| serial_code1 | VARCHAR | 序號碼 1 |
| serial_code2 | VARCHAR | 序號碼 2 |
| prod_code | VARCHAR | 產品編號（對應漢堡王原物料）|
| unit | BIGINT FK→pdm_unit_def | 計量單位 |
| lead_time | VARCHAR | 前置時間 |
| status | INT | 狀態（0=啟用, 1=停用）|
| single_spec | DECIMAL | 單份規格量 |
| single_spec_unit | BIGINT FK→pdm_unit_def | 單份規格單位 |
| material_product_id | INT | 漢堡王原物料產品 ID |

#### 9. `pdm_ingredient_compat`（食材相生相剋）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| ingredient | BIGINT FK→pdm_ingredient | 所屬食材 |
| category | BIGINT FK→CodeItem | 比對類型 |
| subcategory | BIGINT FK→CodeItem | 比對副類型 |
| source | BIGINT FK→CodeItem | 比對料源 |
| description | VARCHAR | 說明 |
| compat | INT | 1=相容, 0=不相容 |

#### 10. `pdm_ingredient_nutritional_contents`（食材營養成分）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| ingredient_id | BIGINT FK→pdm_ingredient | 所屬食材 |
| nutritional_definition_id | BIGINT FK→pdm_nutritional_definitions | 營養定義項目 |
| serving_amount | DECIMAL | 每份含量 |
| unit | VARCHAR | 單位 |

#### 11. `pdm_ingredient_subcategory_type`（副類型儲存類型）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| detail_id | BIGINT FK→pdm_code_structure_detail | 副類型結構明細 ID |
| category_code | VARCHAR | 類別代碼（冗餘用於除錯）|
| storage_type | VARCHAR | `SHORT`=生鮮, `LONG`=凍品 |

#### 12. `pdm_recipe`（食譜主檔）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| structure | BIGINT | 編碼結構 ID |
| status | BOOLEAN | 食譜狀態 |
| main_category | BIGINT FK→CodeItem | 大分類 |
| item_category | BIGINT FK→CodeItem | 品項類別 |
| item_name | BIGINT FK→CodeItem | 品項 ID |
| cooking_method | VARCHAR | 烹調方式 |
| display_name | VARCHAR | 顯示名稱 |
| tag_name | VARCHAR | 標籤名稱 |
| product_code | VARCHAR | 產品代碼 |
| meal_type | VARCHAR FK→pdm_meal_type | 餐食類型 |
| portion_amount | VARCHAR | 單份份量 |
| amount_unit | VARCHAR | 份量單位 |
| portion_standard_cost | VARCHAR | 單份標準成本（NTD）|
| item_sub_tag | VARCHAR | 品項子標籤 |
| cooking_steps | VARCHAR | 烹調步驟 |
| cooking_tips | VARCHAR | 烹調技巧 |
| process_status | VARCHAR | 審批狀態 |
| sign_code | VARCHAR | 簽核代碼 |
| recipe_product_id | INT | 漢堡王產品 ID |
| process_instance_id | VARCHAR | Flowable 流程實例 ID |

#### 13. `pdm_single_serving_recipe`（單份配方）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| recipe_id | BIGINT FK→pdm_recipe | 所屬食譜 |
| ingredient_id | BIGINT FK→pdm_ingredient | 食材 ID |
| standard_amount | DECIMAL | 標準用量 |
| unit | BIGINT FK→pdm_unit_def | 用量單位 |
| single_spec | DECIMAL | 單份規格 |
| single_spec_unit | BIGINT FK→pdm_unit_def | 單份規格單位 |
| default_supplier | VARCHAR | 預設廠商代碼 |
| latest_quote_price | DECIMAL | 最新報價（NTD/kg or L）|
| last_purchase_price | DECIMAL | 最後採購價格 |
| standard_amount_cost | DECIMAL | 標準用量成本（NTD）|
| prod_code | VARCHAR | 關聯食材/包材產品代碼 |

#### 14. `pdm_nutritional_definitions`（營養定義）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| name | VARCHAR | 中文名稱（熱量、蛋白質...）|
| eng_name | VARCHAR | 英文名稱 |
| unit_id | BIGINT FK→pdm_unit_def | 計量單位 |
| average_meal_recommended_intake | VARCHAR | 每餐建議攝取量 |
| default_ingredient | BOOLEAN | 是否為預設項目 |
| sort | BIGINT | 排列順序 |

#### 15. `pdm_meal_type`（餐食類型）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| name | VARCHAR | 中文名稱 |
| eng_name | VARCHAR | 英文名稱 |
| status | VARCHAR | 狀態 |

#### 16. `pdm_unit_def`（單位定義）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| unit | VARCHAR | 單位代碼（g, kg, 份...）|
| unit_name | VARCHAR | 單位名稱 |
| precision_places | INT | 小數位精度 |
| status | BOOLEAN | 啟用狀態 |

#### 17. `pdm_unit_conv`（單位換算）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| base_unit | VARCHAR | 基礎單位代碼 |
| target_unit | VARCHAR | 目標單位代碼 |
| remarks | VARCHAR | 備註 |
| ratio | DECIMAL | 換算比率（base → target = × ratio）|

#### 18. `pdm_logistics_type`（物流類型）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| logistics_name | VARCHAR | 物流名稱 |
| delivery_mode | VARCHAR | 配送方式（直送/配送）|
| cycle_type | VARCHAR | 週期類型（weekly/monthly）|
| logistics_cycle | VARCHAR | 物流週期日（逗號分隔，如 "1,3,5"）|
| data_type | VARCHAR | 資料提供方式 |
| default_str | VARCHAR | 預設旗標（0=預設, 1=非預設）|
| remark | VARCHAR | 備註 |

#### 19. `crg_demand_forecast_config`（需求預測設定）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| name | VARCHAR | 設定名稱（如「全区域标準週預測」）|
| enabled | INT | 啟用旗標（1=啟用, 0=停用）|
| conflict_flag | INT | 衝突旗標（1=有衝突）|
| forecast_mode | VARCHAR | 預測模式（如「区域-季」）|
| cron_expression | VARCHAR | Quartz Cron 表達式 |
| demand_weeks | INT | 需求週數（如 4）|
| sales_days | INT | 銷售資料天數（如 28）|
| data_length_days | INT | 資料長度（如 28）|
| forecast_increment_percent | DECIMAL | 預測增量（1.00=100%, 1.05=105%）|
| last_success_time | TIMESTAMP | 最後成功執行時間 |

#### 20. `crg_demand_forecast_config_scope`（預測設定範圍）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| config_id | BIGINT FK→crg_demand_forecast_config | 設定 ID |
| region_id | INT | 區域 ID（必填）|
| store_id | INT NULLABLE | 門市 ID（null=區域全部門市）|

#### 21. `crg_demand_forecast`（需求預測單頭）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| document_date | DATE | 單據日期 |
| document_code | VARCHAR | 單號 |
| sign_code | VARCHAR | 簽核代碼 |
| forecast_mode | VARCHAR | 預測模式 |
| store_region | VARCHAR | 門市區域名稱 |
| demand_store | VARCHAR | 需求門市名稱 |
| week_start_date | DATE | 預測週開始日 |
| week_end_date | DATE | 預測週結束日 |
| forecast_increment_percent | DECIMAL | 預測增量% |
| sales_start_date | DATE | 銷售資料起始日 |
| sales_end_date | DATE | 銷售資料結束日 |
| process_status | VARCHAR | 審批狀態 |
| subject | VARCHAR | 主旨 |
| region_id | INT | 區域 ID（外部系統）|
| store_id | INT | 門市 ID（外部系統）|
| process_instance_id | VARCHAR | Flowable 流程實例 ID |

#### 22. `crg_demand_forecast_detail`（需求預測單身）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| parent_id | BIGINT FK→crg_demand_forecast | 所屬單頭 |
| region | VARCHAR | 區域名稱 |
| store_name | VARCHAR | 門市名稱 |
| product_id | INT | 漢堡王產品 ID |
| product_name | VARCHAR | 產品名稱 |
| weekday_sales | INT | 平日銷售額（萬元）|
| weekend_sales | INT | 假日銷售額（萬元）|
| ingredient_id | BIGINT FK→pdm_ingredient | 食材 ID |
| ingredient_name | VARCHAR | 食材名稱 |
| prod_code | VARCHAR | 產品代碼 |
| standard_amount | DECIMAL | 標準用量 |
| amount_unit | VARCHAR | 用量單位 |
| standard_quantity | DECIMAL | 標準數量 |
| quantity_unit | VARCHAR | 數量單位 |
| weekday_demand_amount | DECIMAL | 平日需求量 |
| weekend_demand_amount | DECIMAL | 假日需求量 |
| weekday_demand_count | DECIMAL | 平日需求次數 |
| weekend_demand_count | DECIMAL | 假日需求次數 |
| forecast_demand | DECIMAL | 預測需求量 |
| weekday_order_amount | DECIMAL | 平日訂單金額（元）|
| holiday_order_amount | DECIMAL | 假日訂單金額（元）|
| weekday_average_sales_per10k | DECIMAL(8,2) | 平日每萬元平均用量 |
| holiday_average_sales_per10k | DECIMAL(8,2) | 假日每萬元平均用量 |
| projected_weekday_average_sales_per10k | DECIMAL(8,2) | 預測平日每萬元平均 |
| projected_holiday_average_sales_per10k | DECIMAL(8,2) | 預測假日每萬元平均 |
| weekday_average_sales | DECIMAL(2,2) | 平日平均銷售 |
| holiday_average_sales | DECIMAL(2,2) | 假日平均銷售 |
| weekday_count | INT | 平日天數 |
| holiday_count | INT | 假日天數 |
| region_id | INT | 區域 ID |
| store_id | INT | 門市 ID |

#### 23. `pdm_raw_material_demand_head`（原物料需求單頭）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| region_id | INT | 區域 ID |
| store_region | VARCHAR | 區域名稱 |
| store_id | INT | 門市 ID |
| demand_store | VARCHAR | 門市名稱 |
| category | BIGINT FK→CodeItem | 食材分類 |
| subcategory | BIGINT FK→CodeItem | 食材副分類 |
| start_date | TIMESTAMP | 行事曆起始日 |
| end_date | TIMESTAMP | 行事曆結束日 |

#### 24. `pdm_raw_material_demand_date_list`（需求日期清單）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| head_id | BIGINT FK→pdm_raw_material_demand_head | 所屬單頭 |
| demand_date | TIMESTAMP | 需求日期 |
| store_id | INT | 門市 ID |
| demand_store | VARCHAR | 門市名稱 |
| demand_relation_doc | VARCHAR | 關聯需求預測單（signCode）|
| temp_relation_doc | VARCHAR | 關聯臨時需求單（signCode）|
| expect_amount | DECIMAL | 預計量（萬元單位）|

#### 25. `pdm_raw_material_demand_detail`（原物料需求明細）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| head_id | BIGINT FK→pdm_raw_material_demand_head | 所屬單頭 |
| demand_date_id | BIGINT FK→pdm_raw_material_demand_date_list | 需求日期 |
| prod_code | VARCHAR | 食材產品代碼 |
| demand_amount | DECIMAL | 需求數量 |
| mfr_id | VARCHAR | 供應商 ID |
| expect_delivery_date | TIMESTAMP | 預計交貨日 |
| use_delivery_type | BIGINT FK→pdm_logistics_type | 使用物流類型 |
| actual_arrival_date | TIMESTAMP | 實際到貨日 |
| actual_arrival_amount | DECIMAL | 實際到貨量 |
| store_id | INT | 門市 ID |
| demand_store | VARCHAR | 門市名稱 |
| demand_relation_doc | VARCHAR | 關聯需求預測單 |
| temp_relation_doc | VARCHAR | 關聯臨時需求單 |
| region_id | INT | 區域 ID |
| store_region | VARCHAR | 區域名稱 |
| stock_sign_code | VARCHAR | 庫存入庫單代碼 |

#### 26. `pdm_raw_material_logistics`（物流單）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| sign_code | VARCHAR | 物流單代碼 |
| delivery_mode | VARCHAR | 配送方式 |
| delivery_mfr_id | VARCHAR | 配送廠商 ID |
| shipping_date | TIMESTAMP | 出貨日期 |

#### 27. `pdm_raw_material_logistics_dtl`（物流單明細）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| parent_id | BIGINT FK→pdm_raw_material_logistics | 所屬物流單 |
| delivery_mode | VARCHAR | 配送方式 |
| prod_code | VARCHAR | 產品代碼 |
| material_product_id | BIGINT | 漢堡王原物料產品 ID |
| mfr_id | VARCHAR | 廠商 ID |
| actual_arrival_amount | DECIMAL | 實際到貨量 |
| material_type | VARCHAR | 物料類型 |
| store_code | VARCHAR | 門市代碼 |
| store_id | INT | 門市 ID |
| demand_relation_doc | VARCHAR | 關聯需求預測單 |
| temp_relation_doc | VARCHAR | 關聯臨時需求單 |
| region_id | INT | 區域 ID |
| shipping_date | TIMESTAMP | 出貨日期 |

---

### 需求預測計算公式（逆向還原）

以下公式從 `DemandForecastServiceImpl.buildIngredientDetail()` 逆向還原：

**前提變數**
- `weekdaySales`：前端輸入的平日銷售額（萬元，整數）
- `weekendSales`：前端輸入的假日銷售額（萬元，整數）
- `weekdayMultiplier`：從漢堡王中繼 API 取得的平日銷售比例（小數）
- `holidayMultiplier`：從漢堡王中繼 API 取得的假日銷售比例（小數）
- `standardQuantity`：食材每份標準用量（來自 pdm_single_serving_recipe）
- `forecastIncrementPercent`：預測增量倍數（如 1.05）
- `singlePackCount`：每箱個數（來自廠商報價）

**計算步驟（生鮮/SHORT 食材，或凍品低於安全庫存）**

```
1. 訂單金額（元）
   weekdayOrderAmount = weekdayMultiplier × 10,000     （四捨五入至整數）
   holidayOrderAmount = holidayMultiplier × 10,000      （四捨五入至整數）

2. 每萬元平均用量
   weekdayAverageSalesPer10k = weekdayMultiplier × 10,000 × standardQuantity
   holidayAverageSalesPer10k = holidayMultiplier × 10,000 × standardQuantity

3. 預測萬元平均用量
   projectedWeekdayAverageSalesPer10k = weekdayAverageSalesPer10k × forecastIncrementPercent
   projectedHolidayAverageSalesPer10k = holidayAverageSalesPer10k × forecastIncrementPercent
   （各保留 2 位小數）

4. 換算箱數（需廠商報價中的 singlePackCount）
   weekdayBoxConversion = projectedWeekdayAverageSalesPer10k ÷ singlePackCount
   holidayBoxConversion = projectedHolidayAverageSalesPer10k ÷ singlePackCount
```

**每萬元平均銷售計算（calculateAverageSalesPer10k）**
```
avgSales = sales ÷ dayCount
avgSalesPer10k = avgSales × 10,000 ÷ orderAmount
精度：8 位小數 → 輸出 2 位小數
```

**凍品（LONG）邏輯**
- 若庫存 >= 安全庫存：跳過計算，前端顯示「判斷庫存」
- 若庫存 < 安全庫存：執行上述完整計算，並標記 `isSafetyStockWarning = true`

---

### BPM 審批流整合規範

適用模組：食材維護（Ingredient）、食譜維護（Recipe）、包材維護（PackingMaterials）、需求預測（DemandForecast）

**標準流程：**
1. 建立單據 → 呼叫 `menuFlowProcessInstanceHelper.createProcessInstanceIfFlowOpen(userId, formPath, recordId)`
2. 若選單已綁定 Flowable 流程 → 自動建立流程實例，設定 `processStatus = "待處理"`
3. 若未綁定 → 直接歸檔或略過
4. 流程事件監聽器接收 `BpmProcessInstanceStatusEvent`
5. 核准（APPROVE）→ 更新 `processStatus = "已歸檔"`；執行後續業務邏輯
6. 退件（REJECT）→ 更新 `processStatus = "已退件"`

**FormPath 對應表：**
| 模組 | FormPathUniqueEnum | 路徑值 |
|------|-------------------|-------|
| 食材維護 | INGREDIENTS | "ingredients" |
| 食譜維護 | RECIPE | "recipe" |
| 包材維護 | PACKAGING | "packagingMaterials" |
| 需求預測 | DEMAND | "reqCalculation" |
| 臨時需求 | TEMP_REQ | "tempReq" |

---

### 外部系統整合（漢堡王中繼 API）

Base URL：`http://61.218.209.215:80/api`
FeignClient：`BurgerKingStoreClient`（自動管理 Token，有效期 55 分鐘）

| 方法 | 路徑 | 用途 |
|------|------|------|
| getGroupWithStoresInner | `/api/burgerking/admin/store/group-with-stores/inner` | 取得群組與門市清單（內部用）|
| getCompletedOrdersFilter | `/api/burgerking/admin/order/completed/filter` | 取得完成訂單統計（按群組/時段/門市）|
| getAllAreasWithStores | `/api/burgerking/admin/area-group/all-areas-with-stores` | 取得完整區域 → 門市層級 |

---

### API 端點清單（PDM 模組）

| 控制器 | 方法 | 路徑 | 說明 |
|--------|------|------|------|
| CodeBomController | GET | /pdm/code-bom/page | BOM 分頁查詢 |
| CodeBomController | POST | /pdm/code-bom/create | 建立 BOM |
| CodeStructureController | GET | /pdm/code-structure/page | 編碼結構分頁 |
| IngredientController | POST | /pdm/ingredient/create | 建立食材 |
| IngredientController | GET | /pdm/ingredient/todo-page | 待審食材清單 |
| IngredientSpecsController | GET | /pdm/ingredient-specs/getList | 查詢食材規格 |
| PdmRecipeController | POST | /pdm/recipe/create | 建立食譜 |
| PdmRecipeController | GET | /pdm/recipe/todo-page | 待審食譜清單 |
| DemandForecastController | GET | /pdm/demand-forecast/page | 需求預測分頁 |
| DemandForecastDetailController | GET | /pdm/demand-forecast/detail/product-recipe-analysis | 產品食譜分析（計算核心）|
| DemandForecastDetailController | POST | /pdm/demand-forecast/detail/calculate-projected-sales | 重新計算預測 |
| DemandForecastDetailController | POST | /pdm/demand-forecast/detail/create-with-details | 建立需求預測（含明細）|
| DemandForecastConfigController | POST | /pdm/demand-forecast-config/save | 儲存預測設定 |
| DemandForecastConfigController | POST | /pdm/demand-forecast-config/run-now | 手動觸發排程 |
| RawMaterialDemandHeadController | GET | /pdm/raw-material-demand-head/query-details-by-month | 月份需求查詢 |
| RawMaterialDemandHeadController | POST | /pdm/raw-material-demand-head/generateCsv | 產生 MSS CSV |
| LogisticsTypeController | GET | /pdm/logistics-type/page | 物流類型分頁 |

---

## Testing Decisions

**好的測試定義：** 只驗證外部行為（API 回應、狀態變化），不測試私有方法或內部實作。

**目前測試方式：** 無自動化測試，依賴 Swagger UI 手動驗證（`http://localhost:48080/doc.html`）

**建議優先測試模組（若要加入自動化測試）：**

1. **需求預測計算公式**（`buildIngredientDetail`、`calculateProjectedSales`）
   - 輸入：銷售統計 + 食譜資料 + 增量 %
   - 期望輸出：各預測欄位值符合公式
   - 理由：這是核心業務邏輯，最容易因修改而出錯

2. **食材/食譜 BPM 流程觸發**
   - 驗證：建立食材後，若選單有綁定流程，processInstanceId 不為空
   - 驗證：審批核准後，processStatus 變為「已歸檔」

3. **需求預測設定衝突偵測**（precheck）
   - 驗證：同一門市被兩個 config scope 覆蓋時，precheck 回傳衝突清單

---

## Out of Scope

1. **BHM 模組**（漢堡王基礎資料）：凍結，不在本 PRD 範圍
2. **BizContract**（合約管理）：全部程式碼在 `/* */` 中，用途不明
3. **前端 UI 實作細節**：本 PRD 僅規範後端 API 合約
4. **資料庫 Migration 腳本**：目前無 Flyway/Liquibase，手動管理
5. **庫存異常處理（WHS）**：屬於 WHS 模組範圍

---

## Further Notes

### 未解決的規格問題（UNKNOWNS — 對應 UNKNOWNS.md）

| UNKNOWN | 問題 | 影響 |
|---------|------|------|
| U-1 | 需求預測核准後如何產生 RawMaterialDemand？自動還是手動觸發？ | `DemandForecastStatusListener` 中有 TODO，邏輯未實作 |
| U-2 | 供應商篩選條件：DemandForecastDetail 如何匹配廠商？按 prodCode？按 storeId？ | 影響原物料需求明細的 mfr_id 來源 |
| U-4 | BOM 展開計算規則：CodeBom 如何展開為食材用量？有遞迴嗎？ | 影響需求預測展開食材的方式 |
| U-5 | 安全庫存計算標準：是每日平均 × N 天？還是總銷售量的 X%？ | 影響 `selectFirstSafetyStockByIngredientIds` 的查詢邏輯 |

### 資料一致性說明

- 所有資料表均使用**軟刪除**（deleted=1）而非實體刪除
- 多租戶隔離透過 `tenant_id` 欄位實現（MyBatis Plus 自動注入）
- 樂觀鎖透過 `revision` 欄位實現，防止並發衝突
- 需求預測與原物料需求之間的關聯是透過 `sign_code`（字串）而非 ID，屬於**跨域鬆耦合設計**

### 命名規範觀察

- 「短效」食材（生鮮）= `storage_type = "SHORT"`
- 「長效」食材（凍品）= `storage_type = "LONG"`
- 「萬元」= 10,000 元，是系統中銷售額的計算單位
- `prodCode` = 漢堡王系統的原物料產品代碼，是跨系統整合的核心 key
