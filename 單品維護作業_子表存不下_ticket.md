# 【後端 Ticket】單品維護作業 — 明細頁子表資料完全沒被儲存

- **模組**：ERP / PDM / Recipe（單品維護作業）
- **嚴重度**：Blocker（功能無法使用）
- **回報日**：2026-05-28
- **回報人**：前端（dylan_lo）
- **相關前端**：`resources/js/Pages/ERP/PDM/User/Recipe/RecipeDetail.vue`
- **相關後端**：
    - `app/Http/Controllers/ERP/PDM/RecipeController.php`
    - `app/Services/ERP/PDM/RecipeService.php`
    - `app/Repositories/ERP/PDM/RecipeRepository.php`
- **背景文件**：`docs/_handoff/單品維護作業_後端待辦.md` §1

---

## 問題現象

使用者在「單品維護作業」明細頁填寫「**單份用量配方**」與「**營養成分含量**」兩張子表後按「暫存」或「遞交」，回到列表頁再進入該單據時兩張子表都是空的。

實測：
1. 新增單品 → 填主表 → 填單份用量配方 → 填營養成分 → 暫存 → 回編輯 → **兩張子表都消失**。
2. 已存在單品 → 編輯 → 補上營養成分含量 → 暫存 → 回編輯 → **營養成分仍空白**（單份用量配方則正常保留）。

---

## 根因

前端 `buildSavePayload()` 已正確將兩張子表打包送出（`singleServingRecipes`、`recipeNutritionalContents`），可從 Network 面板 payload 確認。問題出在後端：

### Bug A — `RecipeService::create()` 完全沒處理任一子表
`app/Services/ERP/PDM/RecipeService.php` `create()`（約 L109–143）只 insert 主檔 `Recipe`，前端送來的 `singleServingRecipes` / `recipeNutritionalContents` 直接被丟掉。

### Bug B — `RecipeService::update()` 沒處理營養成分子表
`app/Services/ERP/PDM/RecipeService.php` `update()`（約 L145–188）只處理 `singleServingRecipes`：

```php
if (isset($data['singleServingRecipes'])) {
    $this->repo->deleteSingleServingByRecipeId($id);
    $this->repo->createSingleServingBatch($id, $data['singleServingRecipes'], $userId, $now);
}
// ← 缺 recipeNutritionalContents 區段
```

### Bug C — Repository 缺營養成分對應方法
`app/Repositories/ERP/PDM/RecipeRepository.php` 僅有 `deleteSingleServingByRecipeId()` 與 `createSingleServingBatch()`，沒有 nutrition 版本。

---

## 期望修法

### 1. `RecipeRepository` 補兩支方法

```php
public function deleteNutritionByRecipeId(int $recipeId): void
{
    RecipeNutritionContents::where('recipe_id', $recipeId)->delete();
}

public function createNutritionBatch(int $recipeId, array $list, string $userId, int $now): void
{
    $nextId = (int) (RecipeNutritionContents::max('id') ?? 0) + 1;
    foreach ($list as $item) {
        $row = new RecipeNutritionContents([
            'recipe_id'                 => $recipeId,
            'nutritional_definition_id' => isset($item['nutritionalDefinitionId']) ? (int) $item['nutritionalDefinitionId'] : null,
            'serving_amount'            => isset($item['servingAmount']) ? (float) $item['servingAmount'] : null,
            'unit'                      => $item['unit'] ?? null,
            'creator'                   => $userId,
            'create_time'               => $now,
            'updater'                   => $userId,
            'update_time'               => $now,
        ]);
        $row->id = $nextId++;
        $row->save();
    }
}
```

### 2. `RecipeService::update()` 在 single-serving 區段下方加上

```php
if (isset($data['recipeNutritionalContents'])) {
    $this->repo->deleteNutritionByRecipeId($id);
    $this->repo->createNutritionBatch($id, $data['recipeNutritionalContents'], $userId, $now);
}
```

### 3. `RecipeService::create()` 在主檔 insert 後同步寫兩張子表

```php
if (!empty($data['singleServingRecipes'])) {
    $this->repo->createSingleServingBatch($model->id, $data['singleServingRecipes'], $userId, $now);
}
if (!empty($data['recipeNutritionalContents'])) {
    $this->repo->createNutritionBatch($model->id, $data['recipeNutritionalContents'], $userId, $now);
}
```

---

## 前端送出 payload 範例（給後端對欄位用）

```json
{
  "structure": 2,
  "status": true,
  "mainCategory": 1,
  "itemCategory": 5,
  "itemName": 12,
  "cookingMethod": 3,
  "displayName": "範例單品",
  "productCode": "0105123",
  "singleServingRecipes": [
    {
      "ingredientId": 7,
      "standardAmount": 100,
      "unit": "1",
      "singleSpec": 50,
      "singleSpecUnit": "1",
      "defaultSupplier": null,
      "latestQuotePrice": null,
      "lastPurchasePrice": null,
      "standardAmountCost": 0,
      "prodCode": "..."
    }
  ],
  "recipeNutritionalContents": [
    {
      "nutritionalDefinitionId": 2,
      "servingAmount": 5.6,
      "unit": "g"
    }
  ]
}
```

---

## 驗收條件

- [ ] 新增單品時填寫單份用量配方，暫存後回編輯，資料完整保留。
- [ ] 新增單品時填寫營養成分含量，暫存後回編輯，資料完整保留。
- [ ] 編輯已存在單品時新增 / 修改 / 刪除營養成分含量列，暫存後回編輯，資料正確同步（含「刪除舊列」行為，與單份用量配方一致）。
- [ ] 遞交（`processStatus = '已歸檔'`）流程下子表同樣正確持久化。
- [ ] `RecipeRepository::delete()` 既有的子表級聯刪除維持不變。
