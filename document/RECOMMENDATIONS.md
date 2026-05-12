# 穩定性改善建議（RECOMMENDATIONS）

> 針對目前程式碼中發現的問題，提出改善建議。
> 依優先度排序。實施前請先確認不影響現有功能。

---

## 高優先（直接影響系統穩定性）

### R-1：導入 Flyway 做資料庫版本控制

**問題**：目前使用手動 `.sql` 檔管理 schema，多人開發時很容易發生「A 開發者加了欄位，B 開發者不知道要執行哪個 SQL」的同步問題。

**建議**：導入 Flyway，所有 schema 變更寫成版本化的 migration 腳本。

**實作步驟**：
1. 在 `kingmaker-dependencies/pom.xml` 加入 Flyway 依賴
2. 在 `application.yaml` 啟用 Flyway
3. 將現有 `sql/kingmaker.sql` 拆分為 `V1__init_schema.sql`
4. 後續每次 schema 變更建立新的 `V{n}__{description}.sql`

```xml
<!-- 加入 dependency -->
<dependency>
    <groupId>org.flywaydb</groupId>
    <artifactId>flyway-core</artifactId>
</dependency>
<dependency>
    <groupId>org.flywaydb</groupId>
    <artifactId>flyway-database-postgresql</artifactId>
</dependency>
```

```yaml
# application.yaml
spring:
  flyway:
    enabled: true
    locations: classpath:db/migration
    baseline-on-migrate: true
```

---

### R-2：統一錯誤處理方式

**問題**：部分 Service 使用 Java 原生例外（`IllegalArgumentException`、`RuntimeException`），導致前端收到不一致的錯誤格式。

**發現位置**：`WHS/WarehouseServiceImpl.java`（多處）

**建議**：全面使用框架的 `ServiceExceptionUtil`。

```java
// 錯誤做法（現有問題程式碼）
throw new IllegalArgumentException("区域参数不能为空");
throw new RuntimeException("廠商記錄不存在");

// 正確做法
import static com.newsoft.kingmaker.framework.common.exception.util.ServiceExceptionUtil.exception;
throw exception(ErrorCodeConstants.WAREHOUSE_AREA_REQUIRED);
```

**統一做法的好處**：
- 前端收到統一格式的錯誤回應（`CommonResult.error(code, msg)`）
- AI Agent 可以正確解析錯誤訊息
- 錯誤碼可集中管理和翻譯

---

### R-3：加入 docker-compose.yml（開發環境一致性）

**問題**：每個開發者需自行安裝和設定 PostgreSQL + Redis，環境不一致容易產生「只有我的機器跑不起來」的問題。

**建議**：在 repo 根目錄加入 `docker-compose.yml`。

```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: bk
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./sql/kingmaker.sql:/docker-entrypoint-initdb.d/01-init.sql

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

啟動指令：`docker-compose up -d`

---

## 中優先（影響開發效率和程式碼品質）

### R-4：補充 Swagger @Operation 說明

**問題**：部分端點缺少完整的 `@Operation(summary = "...")` 說明，導致：
- AI Agent 無法理解端點用途，容易誤用
- 前端開發者需看程式碼才能理解 API 行為

**建議**：所有 Controller 方法都補上中文說明。

```java
// 加上 summary 和必要的 description
@GetMapping("/page")
@Operation(
    summary = "取得請購單分頁列表",
    description = "支援依門市、食材、狀態過濾，需有 pmm:pur-req:query 權限"
)
public CommonResult<PageResult<PurReqRespVO>> getPurReqPage(...) { ... }
```

---

### R-5：核心流程補充整合測試

**問題**：目前完全沒有自動化測試，業務邏輯改動後只能靠手動 Swagger 驗證，風險高。

**建議**：優先為最複雜的 PMM 採購流程補充整合測試。

**最小可行方案**（只測最關鍵路徑）：

```java
// 測試：請購單 → 歸檔 → 生成報價單（幂等性）
@SpringBootTest
@Transactional
class PurReqServiceIntegrationTest {

    @Test
    void archivePurReq_shouldCreateExactlyOneQuote() {
        // 1. 建立請購單
        // 2. 歸檔
        // 3. 驗證只生成一張報價單
        // 4. 再次歸檔（幂等性）
        // 5. 驗證報價單數量仍為 1
    }
}
```

---

### R-6：新增功能使用程式碼生成器

**問題**：目前新功能是手寫全套 CRUD，耗時且容易遺漏。

**建議**：優先使用 INFRA 模組內建的程式碼生成器（`/infra/codegen`）產生骨架，再手動補充業務邏輯。

詳細步驟見 `DEV_GUIDE.md`。

---

## 低優先（技術債清理，不影響業務）

### R-7：補齊 DictTypeConstants 枚舉

**問題**：PDM 多個 VO 的 `@DictFormat` 有 TODO，指出字典類型常量應在 `DictTypeConstants` 中定義。

**位置**：`CodeBomRespVO.java`、`MealTypeRespVO.java`、`PdmRecipeRespVO.java`

### R-8：統一 VO 轉換方式

**問題**：部分模組用 MapStruct Convert 類，部分模組直接用 `BeanUtils.toBean()`，不一致。

**建議**：對於簡單 CRUD，`BeanUtils.toBean()` 足夠；對於複雜欄位映射（如欄位改名、計算欄位），使用 MapStruct。

### R-9：補充 API 版本標識

**問題**：目前所有 API 沒有版本號（如 `/v1/`），未來 breaking change 時無法漸進式升級。

**建議**：現階段未上線，暫不強制。但建議在 URL 規範中記錄此決策（避免上線後的技術債更大）。
