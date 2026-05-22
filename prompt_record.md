
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