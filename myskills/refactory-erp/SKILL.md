---
name: refactory-erp
description: Login to the Burger King ERP backend and call any API endpoint. Handles JWT auth flow (login → get token → call API). Use when user says "refactory bk erp", "重構 bk erp" .
---

# refactory BK ERP — 呼叫 API 並產生 OA 對應程式碼

本 skill 涵蓋兩個系統：

## 設定變數

```bash
OA_PATH=/data/newprooa       # OA 原始碼目錄
ERP_BACKEND_PATH=/data/burgerking/erp-spring    # ERP Spring Boot 後端
ERP_FRONTEND_PATH=/data/burgerking/erp-kingmaker # ERP Vue 前端
ERP_HOST=10.65.163.46               # ERP 後端主機 IP
```

## OA Source code path
$OA_PATH
## ERP backend code path
$ERP_BACKEND_PATH
## ERP frontend code path
$ERP_FRONTEND_PATH

---

## 系統對照表

| 項目 | ERP（來源） | OA（目標） |
|------|------------|-----------|
| Base URL | `http://$ERP_HOST/admin-api` | `http://localhost`（需帶 `Host: pc.wilson`） |
| API 前綴 | `/system/auth/...` | `/api/erp/system/auth/...` |
| 登入端點 | `POST /system/auth/login` | `POST /api/erp/system/auth/login` |
| 認證 header | `Authorization: Bearer <token>` + `tenant-id: 1` | `Authorization: Bearer <token>` |
| 程式碼位置 | — | `$OA_PATH` |
| 路由設定 | — | `routes/module/erp.php` |
| Controller | — | `app/Http/Controllers/ERP/` |

---

## 執行流程

### Phase 1 — 呼叫 ERP API 取得資料結構

#### Step 1-1 ERP 登入

```bash
ERP_TOKEN=$(curl -s -X POST http://$ERP_HOST/admin-api/system/auth/login \
  -H 'Content-Type: application/json' \
  -H 'tenant-id: 1' \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['accessToken'])")

echo "ERP Token: ${ERP_TOKEN:0:40}..."
```

> 若 TOKEN 為空，確認：ERP 服務是否啟動、`tenant-id: 1` 是否存在、帳密是否正確（admin / admin123）

#### Step 1-2 呼叫 ERP 目標 API

```bash
# GET 範例
curl -s "http://$ERP_HOST/admin-api$TARGET_API" \
  -H "Authorization: Bearer $ERP_TOKEN" \
  -H 'tenant-id: 1' \
  | python3 -m json.tool

# POST 範例（帶 body）
curl -s -X POST "http://$ERP_HOST/admin-api$TARGET_API" \
  -H "Authorization: Bearer $ERP_TOKEN" \
  -H 'tenant-id: 1' \
  -H 'Content-Type: application/json' \
  -d "$REQUEST_BODY" \
  | python3 -m json.tool
```

---

### Phase 2 — 在 OA 系統登入測試

#### Step 2-1 取得 OA Token（方法一：直接用 tinker，不需密碼）

```bash
cd $OA_PATH
OA_TOKEN=$(php artisan tinker --execute="
\$user = \App\Models\SC\User::where('account', 'admin')->first();
echo auth()->guard('api')->login(\$user);
" 2>/dev/null | grep -v Deprecated | tail -1)

echo "OA Token: ${OA_TOKEN:0:40}..."
```

#### Step 2-1 取得 OA Token（方法二：用帳密登入）

```bash
OA_TOKEN=$(curl -s -X POST http://localhost/api/erp/system/auth/login \
  -H 'Host: pc.wilson' \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<password>"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['accessToken'])")
```

> OA admin 密碼未知時，優先使用方法一（tinker）。

#### Step 2-2 呼叫 OA API 測試

```bash
curl -s "http://localhost/api/erp$TARGET_API" \
  -H 'Host: pc.wilson' \
  -H "Authorization: Bearer $OA_TOKEN" \
  | python3 -m json.tool
```

---

### Phase 3 — 在 OA 實作對應 API（產生程式碼）

若 OA 尚無此 API，依下列順序實作：

#### Step 3-1 確認是否需要新資料表

先檢查 OA 是否有對應資料：

```bash
cd $OA_PATH
php artisan tinker --execute="
echo \DB::table('你的表格名')->count();
" 2>/dev/null | grep -v Deprecated
```

若需要新表格：
- 先從 ERP API 取全量資料，存入 `database/seeders/data/erp_system_xxx.json`
- 建立 migration：`php artisan make:migration create_erp_system_xxx_table`
- **Seed 資料直接寫入 migration**（不建立獨立 Seeder 類別）

**重要規則：**
- 新 ERP 相容表格命名前綴用 `erp_system_`
- Seed JSON 放 `database/seeders/data/` 資料夾
- 欄位設計參考 ERP 資料庫結構
- Migration `up()` 結尾直接讀 JSON 插入資料，`down()` 只需 `dropIfExists`

**Migration 內含 Seed 資料模板：**
```php
use Illuminate\Support\Facades\DB;
// ...
public function up(): void
{
    Schema::create('erp_system_xxx', function (Blueprint $table) {
        // 欄位定義...
    });

    $rawData = json_decode(
        file_get_contents(database_path('seeders/data/erp_system_xxx.json')),
        true
    );

    $rows = array_map(fn($item) => [
        'col_a' => $item['camelA'],
        'col_b' => $item['camelB'] ?? null,
    ], $rawData);

    // 資料量大時分批 insert
    foreach (array_chunk($rows, 200) as $chunk) {
        DB::table('erp_system_xxx')->insert($chunk);
    }
}
```

#### Step 3-2 執行 Migration（Seed 資料已內嵌）

```bash
cd $OA_PATH
php artisan migrate 2>/dev/null | grep -v Deprecated

# 驗證資料已寫入
php artisan tinker --execute="
echo \DB::table('erp_system_xxx')->count();
" 2>/dev/null | grep -v Deprecated
```

#### Step 3-3 新增 Controller 方法

新建 `app/Http/Controllers/ERP/XxxController.php`：

> ⚠️ 基礎類別必須用 `App\Http\Controllers\Base\Controller`，不是 `App\Http\Controllers\Controller`

**Response 格式規範（ERP 相容）：**
```php
// 成功 — 物件/陣列
return response()->json(['code' => 0, 'data' => $data]);

// 成功 — 純量（數字、字串）
return response()->json(['code' => 0, 'data' => $count, 'msg' => '']);

// 成功 — 分頁列表
return response()->json(['code' => 0, 'data' => ['list' => $items, 'total' => $total]]);

// 失敗
return response()->json(['code' => $httpCode, 'msg' => $msg, 'data' => null], $httpCode);
```

**常用 DB 查詢模式：**
```php
// 取使用者角色
$roles = DB::table('erp_system_user_roles as ur')
    ->join('erp_system_roles as r', 'r.id', '=', 'ur.role_id')
    ->where('ur.user_id', auth()->id())
    ->pluck('r.code')
    ->toArray();

// 未讀通知數
$count = DB::table('sc_user_notifications')
    ->where('sc_user_id', auth()->id())
    ->whereNull('read_at')
    ->count();

// 使用者簡易列表（含主部門）
$data = User::with('departments')->get()->map(function (User $user) {
    $dept = $user->departments->first();
    return [
        'id'       => $user->id,
        'nickname' => $user->chinese_name,
        'deptId'   => $dept?->id,
        'deptName' => $dept?->name,
    ];
})->values();

// 分頁查詢
$pageNo   = max(1, (int) $request->query('pageNo', 1));
$pageSize = max(1, min(100, (int) $request->query('pageSize', 10)));
$total    = $query->count();
$items    = $query->orderByDesc('id')
    ->offset(($pageNo - 1) * $pageSize)
    ->limit($pageSize)
    ->get();

// 組 menu 樹狀（注意：用 plain array 加 reference，不能用 Collection + keyBy）
$menusArr = [];
foreach ($rawMenus as $m) {
    $menusArr[$m->id] = [..., 'children' => []];
}
$tree = [];
foreach ($menusArr as $id => &$menu) {
    $pid = $menu['parentId'];
    if ($pid == 0 || !isset($menusArr[$pid])) {
        $tree[] = &$menu;
    } else {
        $menusArr[$pid]['children'][] = &$menu;
    }
}
unset($menu);
```

> ⚠️ Laravel Collection 不支援 PHP reference 修改，組樹狀必須先轉為 plain array。

#### Step 3-4 新增路由

編輯 `routes/module/erp.php`：

```php
Route::prefix('system/auth')->group(function () {
    Route::post('/login', [AuthController::class, 'login']);

    Route::middleware('auth:api')->group(function () {
        Route::get('/get-permission-info', [AuthController::class, 'getPermissionInfo']);
        // 新增其他需要認證的 ERP API
    });
});
```

驗證路由：
```bash
cd $OA_PATH
php artisan route:list --path=erp 2>/dev/null | grep -v Deprecated
```

#### Step 3-5 端對端測試

```bash
cd $OA_PATH
OA_TOKEN=$(php artisan tinker --execute="
\$user = \App\Models\SC\User::where('account', 'admin')->first();
echo auth()->guard('api')->login(\$user);
" 2>/dev/null | grep -v Deprecated | tail -1)

curl -s "http://localhost/api/erp$TARGET_API" \
  -H 'Host: pc.wilson' \
  -H "Authorization: Bearer $OA_TOKEN" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('code:', d.get('code'))
# 輸出主要欄位摘要
data = d.get('data', {})
for k, v in data.items():
    if isinstance(v, list): print(f'{k}: {len(v)} items')
    else: print(f'{k}:', v)
"
```

---

## 常見問題

| 症狀 | 可能原因 | 處置 |
|------|----------|------|
| ERP TOKEN 為空 | 後端未啟動 / BASE_URL 錯誤 | 確認 Spring Boot 是否運行 |
| OA TOKEN 為空（帳密登入） | admin 密碼未知 | 改用 tinker 方法（Step 2-1 方法一） |
| `code: 401` OA | token 過期 | 重新執行 tinker 取 token |
| `Could not resolve host: pc.wilson` | DNS 未設定 | 改用 `http://localhost` + `-H 'Host: pc.wilson'` |
| Seeder `user_roles` 空 | sc_roles 欄位名錯誤 | 確認欄位是 `name` 而非 `role_name` |
| 組樹狀 `Indirect modification` | Collection 不支援 reference | 先 `->toArray()` 或改用 plain array loop |
| `code: 404` 路由找不到 | 路由未加或 middleware 包錯 | 確認 erp.php prefix 與 middleware 設定 |

---

## 注意事項

1. **Host header**：OA 在 Apache virtualhost `pc.wilson`，本地測試必須帶 `-H 'Host: pc.wilson'`
2. **ERP tenant-id**：每個 ERP API 請求都必須帶 `tenant-id: 1`
3. **Seed 資料內嵌 migration**：Seed 資料直接寫在 migration `up()` 末尾，不建立獨立 Seeder 類別；JSON 原始檔仍保留在 `database/seeders/data/` 供重複使用
4. **Controller 基礎類別**：一律用 `App\Http\Controllers\Base\Controller`
5. **Permissions 來源**：ERP 的 permissions 陣列來自 role 的 `permissions` JSON 欄位（非 menu.permission），需從 `erp_system_roles.permissions` 取得
6. **OA 角色對應**：OA `sc_roles.name = 'admin'` → ERP `super_admin`；`normal` → `common`
7. **OA 使用者部門**：`User::with('departments')` — BelongsToMany via `sc_department_members`，`departments->first()` 為主部門
8. **OA 通知未讀**：`sc_user_notifications` — `sc_user_id` + `read_at IS NULL`
