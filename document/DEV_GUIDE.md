# 新功能開發步驟指南

> 這份文件說明如何在本專案的架構下新增一個功能。
> 適用對象：新加入的開發者、AI Agent。

---

## 方法一：使用程式碼生成器（建議）

INFRA 模組內建程式碼生成器，可根據資料庫表自動生成 Controller / Service / Mapper 骨架。

**步驟**：
1. 啟動服務：`http://localhost:48080`
2. 登入後前往「基礎設施 → 程式碼生成」（對應 API：`/infra/codegen`）
3. 選擇要生成的資料庫表
4. 設定模組名稱（如 `whs`）、功能名稱（如 `warehouseName`）
5. 下載生成的程式碼，放入對應的 `-biz` 模組中
6. 手動補充業務邏輯

---

## 方法二：手動新增（參考現有模組）

### 以新增「倉庫名稱管理（WarehouseName）」為例

**前置條件**：`WarehouseNameDO` 和 `WarehouseNameMapper` 已存在。

---

### Step 1：建立 VO 類

位置：`kingmaker-module-whs/kingmaker-module-whs-biz/src/main/java/com/newsoft/kingmaker/module/whs/controller/admin/warehousename/vo/`

**WarehouseNameSaveReqVO.java**（新增/更新請求）：
```java
@Schema(description = "倉庫名稱新增/更新 Request VO")
@Data
public class WarehouseNameSaveReqVO {

    @Schema(description = "ID", example = "1")
    private Long id;  // 更新時必填，新增時不填

    @Schema(description = "倉庫名稱", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank(message = "倉庫名稱不能為空")
    private String name;

    // 其他欄位參考 WarehouseNameDO...
}
```

**WarehouseNamePageReqVO.java**（分頁查詢請求）：
```java
@Schema(description = "倉庫名稱分頁查詢 Request VO")
@Data
@EqualsAndHashCode(callSuper = true)
public class WarehouseNamePageReqVO extends PageParam {

    @Schema(description = "倉庫名稱", example = "冷藏倉")
    private String name;
}
```

**WarehouseNameRespVO.java**（回應 VO）：
```java
@Schema(description = "倉庫名稱 Response VO")
@Data
public class WarehouseNameRespVO {

    @Schema(description = "ID")
    private Long id;

    @Schema(description = "倉庫名稱")
    private String name;

    @Schema(description = "建立時間")
    private LocalDateTime createTime;
}
```

---

### Step 2：建立 Service 介面和實作

**WarehouseNameService.java**：
```java
public interface WarehouseNameService {

    Long createWarehouseName(WarehouseNameSaveReqVO createReqVO);

    void updateWarehouseName(WarehouseNameSaveReqVO updateReqVO);

    void deleteWarehouseName(Long id);

    WarehouseNameDO getWarehouseName(Long id);

    PageResult<WarehouseNameDO> getWarehouseNamePage(WarehouseNamePageReqVO pageReqVO);
}
```

**WarehouseNameServiceImpl.java**：
```java
@Service
@Validated
@Slf4j
public class WarehouseNameServiceImpl implements WarehouseNameService {

    @Resource
    private WarehouseNameMapper warehouseNameMapper;

    @Override
    public Long createWarehouseName(WarehouseNameSaveReqVO createReqVO) {
        WarehouseNameDO warehouseName = BeanUtils.toBean(createReqVO, WarehouseNameDO.class);
        warehouseNameMapper.insert(warehouseName);
        return warehouseName.getId();
    }

    @Override
    public void updateWarehouseName(WarehouseNameSaveReqVO updateReqVO) {
        validateWarehouseNameExists(updateReqVO.getId());
        WarehouseNameDO updateObj = BeanUtils.toBean(updateReqVO, WarehouseNameDO.class);
        warehouseNameMapper.updateById(updateObj);
    }

    @Override
    public void deleteWarehouseName(Long id) {
        validateWarehouseNameExists(id);
        warehouseNameMapper.deleteById(id);
    }

    @Override
    public WarehouseNameDO getWarehouseName(Long id) {
        return warehouseNameMapper.selectById(id);
    }

    @Override
    public PageResult<WarehouseNameDO> getWarehouseNamePage(WarehouseNamePageReqVO pageReqVO) {
        return warehouseNameMapper.selectPage(pageReqVO);
    }

    private void validateWarehouseNameExists(Long id) {
        if (warehouseNameMapper.selectById(id) == null) {
            // 使用框架的 ServiceException，不要用 IllegalArgumentException
            throw exception(ErrorCodeConstants.WAREHOUSE_NAME_NOT_EXISTS);
        }
    }
}
```

---

### Step 3：建立 Controller

**WarehouseNameController.java**：
```java
@Tag(name = "管理後台 - 倉庫名稱管理")
@RestController
@RequestMapping("/whs/warehouse-name")
@Validated
public class WarehouseNameController {

    @Resource
    private WarehouseNameService warehouseNameService;

    @PostMapping("/create")
    @Operation(summary = "建立倉庫名稱")
    @PreAuthorize("@ss.hasPermission('whs:warehouse-name:create')")
    public CommonResult<Long> createWarehouseName(
            @Valid @RequestBody WarehouseNameSaveReqVO createReqVO) {
        return success(warehouseNameService.createWarehouseName(createReqVO));
    }

    @PutMapping("/update")
    @Operation(summary = "更新倉庫名稱")
    @PreAuthorize("@ss.hasPermission('whs:warehouse-name:update')")
    public CommonResult<Boolean> updateWarehouseName(
            @Valid @RequestBody WarehouseNameSaveReqVO updateReqVO) {
        warehouseNameService.updateWarehouseName(updateReqVO);
        return success(true);
    }

    @DeleteMapping("/delete")
    @Operation(summary = "刪除倉庫名稱")
    @Parameter(name = "id", description = "ID", required = true)
    @PreAuthorize("@ss.hasPermission('whs:warehouse-name:delete')")
    public CommonResult<Boolean> deleteWarehouseName(@RequestParam("id") Long id) {
        warehouseNameService.deleteWarehouseName(id);
        return success(true);
    }

    @GetMapping("/get")
    @Operation(summary = "取得倉庫名稱")
    @Parameter(name = "id", description = "ID", required = true, example = "1")
    @PreAuthorize("@ss.hasPermission('whs:warehouse-name:query')")
    public CommonResult<WarehouseNameRespVO> getWarehouseName(@RequestParam("id") Long id) {
        WarehouseNameDO warehouseName = warehouseNameService.getWarehouseName(id);
        return success(BeanUtils.toBean(warehouseName, WarehouseNameRespVO.class));
    }

    @GetMapping("/page")
    @Operation(summary = "取得倉庫名稱分頁列表")
    @PreAuthorize("@ss.hasPermission('whs:warehouse-name:query')")
    public CommonResult<PageResult<WarehouseNameRespVO>> getWarehouseNamePage(
            @Valid WarehouseNamePageReqVO pageReqVO) {
        PageResult<WarehouseNameDO> pageResult =
                warehouseNameService.getWarehouseNamePage(pageReqVO);
        return success(BeanUtils.toBean(pageResult, WarehouseNameRespVO.class));
    }
}
```

---

### Step 4：新增錯誤碼

在模組的 `ErrorCodeConstants` 中新增：

```java
// kingmaker-module-whs-api/.../enums/ErrorCodeConstants.java
public interface ErrorCodeConstants {
    // ...現有錯誤碼...

    ErrorCode WAREHOUSE_NAME_NOT_EXISTS = new ErrorCode(1_050_001_000, "倉庫名稱不存在");
}
```

---

### Step 5：在選單管理中新增權限

透過系統管理的「選單管理」介面新增：
- 選單名稱：倉庫名稱管理
- 路由路徑：`/whs/warehouse-name`
- 權限標識：`whs:warehouse-name:query`（查詢）、`whs:warehouse-name:create`（新增）等

---

## 如何為功能新增 BPM 審批流

參考 PMM 模組的 `PurReqServiceImpl` 實作方式：

### Step 1：在選單管理中綁定 Flowable 流程

在 SYSTEM 的選單管理，為對應路由設定 `flowPath`（Flowable 流程 Key）。

### Step 2：Service 中判斷是否發起流程

```java
@Resource
private MenuFlowProcessInstanceHelper menuFlowProcessInstanceHelper;

public Long createXxx(XxxSaveReqVO createReqVO) {
    // 1. 儲存單據
    XxxDO xxx = BeanUtils.toBean(createReqVO, XxxDO.class);
    xxxMapper.insert(xxx);

    // 2. 判斷選單是否綁定流程
    String processInstanceId = menuFlowProcessInstanceHelper
        .startProcessInstanceIfBound("your-menu-path", xxx.getId(), getLoginUserId());

    // 3. 如果有流程，更新單據的 processInstanceId
    if (processInstanceId != null) {
        xxx.setProcessInstanceId(processInstanceId);
        xxxMapper.updateById(xxx);
    }

    return xxx.getId();
}
```

### Step 3：實作狀態回調 Listener

```java
@Component
public class XxxStatusListener {

    @Resource
    private XxxMapper xxxMapper;

    @EventListener
    public void onBpmProcessInstanceStatusEvent(BpmProcessInstanceStatusEvent event) {
        // 根據 processInstanceId 找到對應單據
        XxxDO xxx = xxxMapper.selectByProcessInstanceId(event.getId());
        if (xxx == null) return;

        // 根據審批結果更新單據狀態
        if (event.getStatus() == BpmProcessInstanceStatusEnum.APPROVE) {
            xxx.setProcessStatus(ProcessStatusEnums.APPROVED.getStatus());
        } else if (event.getStatus() == BpmProcessInstanceStatusEnum.REJECT) {
            xxx.setProcessStatus(ProcessStatusEnums.REJECTED.getStatus());
        }
        xxxMapper.updateById(xxx);
    }
}
```

---

## 重要規範提醒

1. **不要用 `IllegalArgumentException`**，一律用 `throw exception(ErrorCodeConstants.XXX)`
2. **不要在 Controller 寫業務邏輯**，業務邏輯全部在 ServiceImpl
3. **分頁查詢一律繼承 `PageParam`**
4. **所有 Controller 方法都要有 `@Operation(summary = "...")`**，AI 和 Swagger 都靠這個理解端點用途
5. **`@PreAuthorize` 不要省略**，即使測試時想暫時關掉，也要留著並加上 TODO 註解
