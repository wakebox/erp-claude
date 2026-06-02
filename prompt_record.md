
# 庫存管理 API 整理

根據 前端/stock/ ，整理出所有api，可以參考後端，產生html file,要有OA是否有實作的選項，盡量將所有資料，配合節錄文章，code，流程圖，model 圖，表格，商業邏輯說明，顯示出來或加強解釋


# 連外 API

整理後端和外部串間的api,產生html file,要有OA是否有實作的選項，盡量將所有資料，配合節錄文章，code，流程圖，model 圖，表格，商業邏輯說明，顯示出來或加強解釋

---- 回應不是要的 ---- 

# 漢堡王中繼 API（上游資料來源）
分析
### 漢堡王中繼 API（上游資料來源）


位置：kingmaker-module-pdm-biz
FeignClient 類：BurgerKingStoreClient
基礎 URL：http://61.218.209.215:80/api
認證方式：JWT Token（有效期 55 分鐘，自動更新）
| API 路徑 | 方法 | 用途 | OA 是否實作 |
|---|---|---|---|
|---|---|---|
| `/api/burgerking/admin/order/completed/filter` | GET | 已完成訂單統計 |
| `/api/burgerking/admin/order/daily/product-sales` | GET | 日維度商品銷量 |
| `/api/burgerking/admin/area-group/all-areas-with-stores` | GET | 區域組及門店（層級結構） |

整理api,要有OA是否有實作的選項，盡量將所有資料，配合節錄文章，code，流程圖，model 圖，表格，商業邏輯說明，顯示出來或加強解釋


# 觸發中繼 API 的流程


# 執行重構動作

@stock-api-docs.html ,重構 erp bk , 倉庫基本設定 

@stock-api-docs.md   重構 ERP BK , 倉儲查詢作業 ，完成後修正 OA實做內容

@stock-api-docs.md   重構 ERP BK , 入庫作業管理 ，完成後修正 OA實做內容

---

重構 erp bk ,  /data/erp-claude/html/stock-api-docs.md 出庫作業管理 (Stock Out)

---


重構 erp bk , http:10.65.163.46/stock/out api


-----

檢查  OA 程式碼 針對 ERP 模組下 - controller 是否有遵守 MVC 原則，controller 絕不處理資料庫，商業邏輯，修正不符合地方

----- 5/25 

重構 erp bk , api/erp/whs/check-plan/page?pageNo=1&pageSize=20&processStatus=%E5%BE%85%E8%99%95%E7%90%86

--- 5/28

/tdd 測試 api/erp/pdm/packing-materials/update ，單據編號不會移除


食材 api/erp/pdm/ingredient/update

單品  api/erp/pdm/recipe/update 

/tdd 單品維護作業 測試 api/erp/pdm/recipe/update  ，單據編號不會移除

重構 erp bk , 修改 api/erp/pdm/packing-materials/create  ，會回應 id


/tdd 測試 /api/erp/pdm/packing-materials/update   已經有主旨，不可清空



/tdd 單品維護作業 測試 api/erp/pdm/recipe/update  ，營養成份含量 資料確實寫入


這個promt造成ai誤判，測試erp,加上   ---- " 不是ERP , java , "  才正常
/tdd  不是ERP , java , 是測試 oa api - api/erp/whs/stock/currentPage ，查詢時過濾 warehouse 可以發生作用