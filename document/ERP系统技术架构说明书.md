# 汉堡王ERP 系统技术架构说明书

> 项目：汉堡王ERP（
> 版本：V1

---

## 一、技术背景

### 1.1 前端框架

| 技术层    | 组件                        | 版本         |
| --------- | --------------------------- | ------------ |
| 核心框架  | Vue                         | 3.5.17       |
| 路由      | Vue Router                  | 4.5.1        |
| 状态管理  | Pinia                       | 3.0.3        |
| UI 组件库 | Ant Design Vue              | 4.2.6        |
| 构建工具  | Vite                        | 7.1.2        |
| 语言      | TypeScript                  | 5.8.3        |
| CSS 方案  | Tailwind CSS                | 3.4.17       |
| 工具库    | VueUse                      | 13.4.0       |
| 网络请求  | @vben/request（基于 axios） | axios 1.10.0 |
| 国际化    | vue-i18n                    | 11.1.7       |

工程形态：**pnpm Monorepo**（apps/packages/internal），基础模板：`vue-vben-admin`（@vben/burger-king）

### 1.2 后端框架

| 技术层 | 组件 | 版本 |
|--------|------|------|
| 核心框架 | Spring Boot | 3.4.1 |
| Java 版本 | JDK | 17 |
| 基础脚手架 | 芋道框架 | 2.4.2 |
| ORM | MyBatis Plus | 3.5.9 |
| 工作流引擎 | Flowable | 7.0.1 |
| 远程调用 | Spring Cloud OpenFeign | 2024.0.1 |

应用名：`kingmaker-server`，服务端口：**48080**

### 1.3 数据库

| 类型 | 说明 |
|------|------|
| 主数据库 | **PostgreSQL**（端口 5432） |
| 连接池 | Druid 1.2.24 |

### 1.4缓存

| 组件 | 说明 |
|------|------|
| Redis | Redisson 3.41.0，DB 0，TTL 默认 1 小时 |

### 1.5 其他中间件与工具

| 类别 | 组件 |
|------|------|
| API 文档 | SpringDoc 2.7.0 + Knife4j 4.6.0 |
| 定时任务 | Quartz |
| 工具库 | Hutool 5.8.35 |
| 安全认证 | Spring Security  + JWT |

---

## 二、外部数据源与外部调用

### 2.1 系统上游(调用中继)

ERP 通过 **FeignClient** 调用汉堡王外部 API，拉取门店和销售数据作为需求预测的数据来源。

```
外部接口地址：http://61.218.209.215:80/api
FeignClient 类：BurgerKingStoreClient
认证方式：JWT Token（自动刷新，有效期 55 分钟）
```

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/burgerking/admin/order/completed/filter` | GET | 已完成订单统计 |
| `/api/burgerking/admin/order/daily/product-sales` | GET | 日维度商品销量 |
| `/api/burgerking/admin/area-group/all-areas-with-stores` | GET | 区域组及门店（层级结构） |

**ERP 与外部系统关系：**

```
BurgerKing 门店系统
       ↓ FeignClient 拉取销售数据
   需求预测服务
       ↓ 计算需求
   原料需求明细
       ↓ 
   进行请采验操作
```

**Token 管理机制**：`BurgerKingTokenManager` 自动维护 Token 缓存，到期前自动使用 Base64 HTTP Basic Auth 重新登录获取新 Token，调用方无需关心认证细节。

---

## 三、系统模块架构

### 3.1 模块总览

ERP 整体采用 **Maven 多模块**结构，分为框架层和业务层两大部分。

| 分类           | 模块名称                                   | 说明                        |
| -------------- | ------------------------------------------ | --------------------------- |
| 依赖管理       | `kingmaker-dependencies`                   | 全局依赖版本 BOM 管理       |
| 框架层         | `kingmaker-framework / kingmaker-common`   | 公共工具、常量、枚举        |
| 框架层 Starter | `kingmaker-framework / starter-web`        | Web 层（Jackson、过滤器等） |
| 框架层 Starter | `kingmaker-framework / starter-security`   | 认证鉴权                    |
| 框架层 Starter | `kingmaker-framework / starter-redis`      | Redis                       |
| 框架层 Starter | `kingmaker-framework / starter-mybatis`    | ORM 及多数据源              |
| 框架层 Starter | `kingmaker-framework / starter-biz-tenant` | 多租户                      |
| 框架层 Starter | `kingmaker-framework / starter-*`          | 其余 Starter（共 11 个）    |
| 业务模块       | `kingmaker-module-system`                  | 系统管理模块（SYSTEM）      |
| 业务模块       | `kingmaker-module-infra`                   | 基础设施模块（INFRA）       |
| 业务模块       | `kingmaker-module-bpm`                     | 审核流程模块（BPM）         |
| 业务模块       | `kingmaker-module-pdm`                     | PDM+需求集合模块（PDM）     |
| 业务模块       | `kingmaker-module-whs`                     | 库存管理模块（WHS）         |
| 业务模块       | `kingmaker-module-pmm`                     | 采购管理模块（PMM）         |
| 启动模块       | `kingmaker-server`                         | 主应用启动模块              |

每个业务模块内部均分为 `-api` 和 `-biz` 两层：
- `-api`：对外暴露的接口定义（DTO、枚举、API 接口），供其他模块依赖
- `-biz`：业务实现（Controller、Service、Mapper、数据库操作）

---

### 3.2 各模块功能说明

#### SYSTEM — 系统管理模块

负责整个平台的基础用户权限体系，是所有模块的公共依赖底座。

**主要功能：**
- 用户管理：账号、密码、头像
- 角色管理：角色权限绑定、菜单权限
- 部门管理：树形结构
- 菜单管理：含流程配置`flowPath`
- 数据字典管理
- 内置店长功能配置

---

#### INFRA — 基础设施模块

提供开发运维层面的通用能力，不承载业务逻辑。

**主要功能：**
- 文件管理：本地/S3/OSS 多存储策略
- 数据源配置管理：动态添加数据库连接
- 代码生成器：根据数据表自动生成 CRUD 代码
- 定时任务管理
- API 访问日志：请求记录、回放
- 系统配置：键值参数维护

---

#### BPM — 业务流程管理模块

基于 Flowable 构建，是全系统审批签核的统一入口。

**主要功能：**
- 流程模型设计：可视化设计器
- 流程定义部署/版本管理
- 流程实例发起、查询、取消
- 用户任务审批：通过/拒绝等
- 审批人候选策略：15+ 种策略：指定用户、角色、部门负责人、发起人自选等
- 待办/已办任务查询
- 审批意见、附件
- 流程状态事件回调（`BpmProcessInstanceStatusEvent`）

**流程状态流转：**

```
发起 → 待签核（各节点名称） → 已批准 → 已归档
                           ↘ 已拒绝（驳回）
```

---

#### PDM — PDM+需求集合模块

ERP 的**核心业务模块之一**，物料编码维护、管理食材、配方、需求预测、物流行事历、原物料行事历等

**主要功能：**

- 编码管理：物料编码维护管理
- 食材、包材管理：食材、包材档案、分类、规格、单位换算
- BOM配方管理：BOM 配方树、配方与食材的关联
- 需求预测：拉取 中继销售数据 → 计算需求 → 发起审批流 → 归档
- 原料需求明细：根据预测结果展开 BOM，计算原料需求量
- 物流行事历：物流管理行事历接口

---

#### WHS — 库存管理模块

负责仓库库存的日常运营管理，多个业务场景集成 BPM 审批流。

**主要功能：**

- 库存基本设定：实时库存查询、库存调整
- 仓储查询：记录出入库记录，以及数量溯源
- 入库作业：记录入库记录，包括调拨入库，盘点软硬件等类型
- 出库作业：记录出库记录，包括调拨出库，盘点软硬件等类型
- 盘点计划制定：制定盘点计划，发起审批
- 盘点计划执行：根据盘点计划制定的周期进行盘点
- 不良品管理：盘点不良品做转仓操作
- 每日盘点：每日盘点数据，远程获取中继当天销售数据进行盘点
- 库存异常处理：异常库存上报，流程审批
- 调拨单管理：跨仓库或跨门店调拨，BPM 审批

---

#### PMM — 采购管理模块

负责采购业务全流程管理。

**主要功能：**

- 厂商资料：用于厂商资料的维护
- 厂商报价：厂商对食材报价的管理维护
- 请购单管理：主要针对库存不足的商品进行请购申请
- 报价单管理：根据对比不同厂商的报价，选择最实惠的报价
- 采购单管理：根据选择的报价，按照厂商进行区分不同的採购单
- 结转验收作业：根据采购的数量以及当前派送的数据，进行部分的结转验收，可能需要多次
- 验收确认作业：主要对验收的进行一个确认，之后根据验收确认作业进行入库的操作





