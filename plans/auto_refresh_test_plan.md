# 🔄 自动刷新/自动续杯机制完整测试计划

## 📋 项目概述

**项目名称**: DesignArena-2Api v8.0 Industrial Pro  
**测试目标**: 完整落地测试自动刷新机制和自动续杯机制  
**测试范围**: TokenManager、浏览器刷新、端到端续杯流程

---

## 🏗️ 系统架构分析

### 核心组件

```mermaid
graph TB
    subgraph "Token管理层"
        TM[TokenManager<br/>单例模式]
        TM --> |过期检测| EX[is_expired]
        TM --> |刷新判断| RF[needs_refresh]
        TM --> |智能预测| PR[Predictive<br/>Algorithm]
        TM --> |持久化| FS[File Storage]
    end
    
    subgraph "浏览器管理层"
        BM[PlaywrightManager]
        BM --> |登录流程| LG[launch_login]
        BM --> |静默刷新| LR[launch_refresh]
        BM --> |流量嗅探| SN[Sniffer]
    end
    
    subgraph "自动续杯流程"
        AC[Auto Refresh<br/>Check]
        AC --> |触发条件| TM
        AC --> |执行刷新| BM
        BM --> |捕获Token| SN
        SN --> |更新Token| TM
    end
    
    TM --> |提供认证| API[API请求]
    BM --> |同步镜像| CH[Chrome Profile]
```

### 自动刷新机制流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant API as API服务
    participant TM as TokenManager
    participant BM as BrowserManager
    participant Chrome as Chrome浏览器
    
    Note over TM,BM: 初始化阶段
    TM->>TM: 加载本地Token
    TM->>TM: 计算过期时间
    
    Note over API,TM: 请求阶段
    User->>API: 发送API请求
    API->>TM: 获取认证头
    TM->>TM: 检查is_expired()
    
    alt Token已过期
        TM->>TM: 检查needs_refresh()
        TM->>BM: 触发后台刷新
        BM->>Chrome: 启动无头浏览器
        Chrome->>Chrome: 访问designarena.ai
        Chrome->>BM: 嗅探新Token
        BM->>TM: 更新Token
        TM->>API: 返回新认证头
    else Token有效
        TM->>API: 返回现有认证头
    end
    
    API->>User: 返回响应
```

---

## 🧪 测试用例设计

### 测试层级

```mermaid
graph LR
    subgraph "单元测试"
        UT1[TokenManager<br/>基础功能]
        UT2[过期检测<br/>逻辑]
        UT3[刷新判断<br/>算法]
        UT4[文件持久化]
    end
    
    subgraph "集成测试"
        IT1[浏览器<br/>启动测试]
        IT2[流量嗅探<br/>测试]
        IT3[Token捕获<br/>测试]
    end
    
    subgraph "端到端测试"
        E2E1[完整续杯<br/>流程]
        E2E2[多轮刷新<br/>测试]
        E2E3[异常恢复<br/>测试]
    end
    
    UT1 --> IT1
    UT2 --> IT2
    UT3 --> IT3
    IT1 --> E2E1
    IT2 --> E2E2
    IT3 --> E2E3
```

---

## 📝 详细测试用例

### 1. TokenManager单元测试

#### 1.1 基础功能测试

| 测试ID | 测试名称 | 测试目标 | 前置条件 | 测试步骤 | 预期结果 |
|--------|---------|---------|---------|---------|---------|
| UT-001 | 单例模式验证 | 验证TokenManager是单例 | 无 | 1. 创建两个TokenManager实例<br>2. 比较两个实例 | 两个实例是同一个对象 |
| UT-002 | Token更新 | 验证Token更新功能 | 无 | 1. 调用update_token()<br>2. 检查current_token | Token已更新 |
| UT-003 | Cookie更新 | 验证Cookie更新功能 | 无 | 1. 调用update_token()带cookie<br>2. 检查current_cookie | Cookie已更新 |
| UT-004 | 认证头生成 | 验证get_auth_header() | Token已设置 | 1. 调用get_auth_header()<br>2. 检查返回的headers | 包含Authorization和Cookie |

#### 1.2 过期检测测试

| 测试ID | 测试名称 | 测试目标 | 前置条件 | 测试步骤 | 预期结果 |
|--------|---------|---------|---------|---------|---------|
| UT-010 | 未过期检测 | Token还有30分钟过期 | Token_expires_at = now + 30min | 1. 调用is_expired() | 返回False |
| UT-011 | 即将过期检测 | Token还有5分钟过期 | Token_expires_at = now + 5min | 1. 调用is_expired() | 返回True (提前10分钟) |
| UT-012 | 已过期检测 | Token已过期 | Token_expires_at = now - 5min | 1. 调用is_expired() | 返回True |
| UT-013 | 无过期时间 | 没有设置过期时间 | token_expires_at = None | 1. 调用is_expired() | 返回False |

#### 1.3 智能刷新判断测试

| 测试ID | 测试名称 | 测试目标 | 前置条件 | 测试步骤 | 预期结果 |
|--------|---------|---------|---------|---------|---------|
| UT-020 | 首次刷新 | 从未刷新过 | last_refresh_time = None | 1. 调用needs_refresh() | 返回True |
| UT-021 | 安全刷新点 | 基于平均寿命计算 | avg_token_life = 60min<br>last_refresh_time = now - 36min | 1. 调用needs_refresh() | 返回True (60*0.6=36min) |
| UT-022 | 无需刷新 | 刚刷新不久 | last_refresh_time = now - 10min | 1. 调用needs_refresh() | 返回False |
| UT-023 | 动态调整 | 验证加权衰减算法 | 多次update_token() | 1. 检查avg_token_life | 平均寿命已更新 |

#### 1.4 文件持久化测试

| 测试ID | 测试名称 | 测试目标 | 前置条件 | 测试步骤 | 预期结果 |
|--------|---------|---------|---------|---------|---------|
| UT-030 | 保存Token | 验证Token保存 | Token已设置 | 1. 调用save_to_files()<br>2. 检查文件内容 | 文件包含Token |
| UT-031 | 加载Token | 验证Token加载 | Token文件存在 | 1. 创建新TokenManager<br>2. 检查current_token | Token已加载 |
| UT-032 | 保存统计 | 验证统计信息保存 | 有统计信息 | 1. 调用save_to_files()<br>2. 检查cache文件 | 文件包含统计 |
| UT-033 | 加载历史 | 验证历史记录加载 | 历史文件存在 | 1. 创建新TokenManager<br>2. 检查expiry_history | 历史已加载 |

---

### 2. 浏览器集成测试

#### 2.1 浏览器启动测试

| 测试ID | 测试名称 | 测试目标 | 前置条件 | 测试步骤 | 预期结果 |
|--------|---------|---------|---------|---------|---------|
| IT-001 | Chrome查找 | 验证Chrome路径查找 | Chrome已安装 | 1. 调用find_chrome_executable() | 返回有效路径 |
| IT-002 | 镜像同步 | 验证profile镜像同步 | Chrome profile存在 | 1. 调用setup_mirror_profile() | 镜像目录创建成功 |
| IT-003 | 无头启动 | 验证无头浏览器启动 | Playwright可用 | 1. 启动launch_refresh() | 浏览器启动成功 |

#### 2.2 流量嗅探测试

| 测试ID | 测试名称 | 测试目标 | 前置条件 | 测试步骤 | 预期结果 |
|--------|---------|---------|---------|---------|---------|
| IT-010 | Token正则匹配 | 验证Token正则表达式 | 无 | 1. 测试TOKEN_PATTERN正则<br>2. 匹配各种Token格式 | 正确匹配JWT格式 |
| IT-011 | 请求头嗅探 | 验证从请求头捕获Token | 有网络请求 | 1. 模拟带Token的请求<br>2. 检查嗅探结果 | Token被捕获 |
| IT-012 | 响应体嗅探 | 验证从响应体捕获Token | 有API响应 | 1. 模拟带Token的响应<br>2. 检查嗅探结果 | Token被捕获 |

---

### 3. 端到端测试

#### 3.1 完整续杯流程测试

| 测试ID | 测试名称 | 测试目标 | 前置条件 | 测试步骤 | 预期结果 |
|--------|---------|---------|---------|---------|---------|
| E2E-001 | 首次登录续杯 | 验证首次登录流程 | 无本地Token | 1. 启动launch_login()<br>2. 等待Token捕获<br>3. 验证Token保存 | Token成功捕获并保存 |
| E2E-002 | 自动刷新续杯 | 验证自动刷新流程 | Token即将过期 | 1. 触发check_and_auto_refresh()<br>2. 等待刷新完成<br>3. 验证新Token | Token成功刷新 |
| E2E-003 | 静默后台刷新 | 验证无头刷新流程 | Token需要刷新 | 1. 启动launch_refresh()<br>2. 等待刷新完成<br>3. 验证Token更新 | Token成功刷新 |

#### 3.2 多轮刷新测试

| 测试ID | 测试名称 | 测试目标 | 前置条件 | 测试步骤 | 预期结果 |
|--------|---------|---------|---------|---------|---------|
| E2E-010 | 连续刷新 | 验证连续多次刷新 | Token可刷新 | 1. 执行3次连续刷新<br>2. 每次验证Token更新 | 所有刷新成功 |
| E2E-011 | 历史统计 | 验证历史记录累积 | 多次刷新 | 1. 执行5次刷新<br>2. 检查expiry_history | 历史记录正确累积 |
| E2E-012 | 平均寿命计算 | 验证加权平均算法 | 多次不同寿命 | 1. 模拟不同寿命Token<br>2. 检查avg_token_life | 平均值计算正确 |

#### 3.3 异常恢复测试

| 测试ID | 测试名称 | 测试目标 | 前置条件 | 测试步骤 | 预期结果 |
|--------|---------|---------|---------|---------|---------|
| E2E-020 | 网络异常恢复 | 验证网络异常处理 | 网络不可用 | 1. 模拟网络断开<br>2. 尝试刷新<br>3. 恢复网络<br>4. 重新刷新 | 异常后成功恢复 |
| E2E-021 | Token无效恢复 | 验证无效Token处理 | Token已失效 | 1. 使用无效Token<br>2. 触发错误诊断<br>3. 自动刷新 | 成功刷新新Token |
| E2E-022 | 文件损坏恢复 | 验证文件损坏处理 | Token文件损坏 | 1. 损坏Token文件<br>2. 重新加载<br>3. 触发刷新 | 成功恢复Token |

---

## 🎯 测试执行计划

### 阶段1: 单元测试 (无需网络)

```mermaid
gantt
    title 单元测试执行计划
    dateFormat  HH:mm
    section TokenManager测试
    单例模式验证       :ut001, 00:00, 5min
    Token更新测试      :ut002, after ut001, 5min
    过期检测测试       :ut010, after ut002, 10min
    刷新判断测试       :ut020, after ut010, 10min
    文件持久化测试     :ut030, after ut020, 10min
```

### 阶段2: 集成测试 (需要环境)

```mermaid
gantt
    title 集成测试执行计划
    dateFormat  HH:mm
    section 浏览器测试
    Chrome路径查找    :it001, 00:00, 5min
    镜像同步测试      :it002, after it001, 10min
    无头浏览器启动    :it003, after it002, 10min
    section 嗅探测试
    Token正则测试    :it010, after it003, 5min
    请求头嗅探测试    :it011, after it010, 10min
```

### 阶段3: 端到端测试 (完整流程)

```mermaid
gantt
    title 端到端测试执行计划
    dateFormat  HH:mm
    section 续杯流程
    首次登录续杯      :e2e001, 00:00, 15min
    自动刷新续杯      :e2e002, after e2e001, 15min
    静默后台刷新      :e2e003, after e2e002, 15min
    section 多轮测试
    连续刷新测试      :e2e010, after e2e003, 20min
    历史统计验证      :e2e011, after e2e010, 10min
    section 异常恢复
    网络异常恢复      :e2e020, after e2e011, 15min
    Token无效恢复    :e2e021, after e2e020, 15min
```

---

## 📊 测试数据准备

### 模拟Token数据

```python
# 有效Token (JWT格式)
VALID_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

# 即将过期Token (5分钟后)
EXPIRING_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE1MTYyNDI2MjJ9.4Adcj3UFYzPUVaVF43FmMab6R5QVgZ3f0zZuG8FQdXw"

# 已过期Token
EXPIRED_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE1MTYyMzkwMjJ9.invalid_signature"

# 模拟Cookie
MOCK_COOKIE = "session_id=abc123; user_token=xyz789; csrf_token=def456"
```

### 测试时间场景

```python
from datetime import datetime, timedelta

# 场景1: Token还有30分钟过期 (安全)
SCENARIO_SAFE = {
    "expires_at": datetime.now() + timedelta(minutes=30),
    "last_refresh": datetime.now() - timedelta(minutes=10),
    "expected_expired": False,
    "expected_needs_refresh": False
}

# 场景2: Token还有5分钟过期 (需要刷新)
SCENARIO_EXPIRING = {
    "expires_at": datetime.now() + timedelta(minutes=5),
    "last_refresh": datetime.now() - timedelta(minutes=50),
    "expected_expired": True,
    "expected_needs_refresh": True
}

# 场景3: Token已过期 (必须刷新)
SCENARIO_EXPIRED = {
    "expires_at": datetime.now() - timedelta(minutes=5),
    "last_refresh": datetime.now() - timedelta(minutes=60),
    "expected_expired": True,
    "expected_needs_refresh": True
}

# 场景4: 从未刷新过 (需要刷新)
SCENARIO_NEVER_REFRESHED = {
    "expires_at": datetime.now() + timedelta(minutes=60),
    "last_refresh": None,
    "expected_expired": False,
    "expected_needs_refresh": True
}
```

---

## 🔍 测试验证点

### 关键验证指标

```mermaid
graph TD
    subgraph "功能验证"
        FV1[Token更新正确性]
        FV2[过期检测准确性]
        FV3[刷新判断准确性]
        FV4[文件持久化完整性]
    end
    
    subgraph "性能验证"
        PV1[刷新响应时间]
        PV2[内存使用情况]
        PV3[文件IO效率]
    end
    
    subgraph "可靠性验证"
        RV1[异常处理能力]
        RV2[恢复机制有效性]
        RV3[并发安全性]
    end
    
    FV1 --> PASS[测试通过]
    FV2 --> PASS
    FV3 --> PASS
    FV4 --> PASS
    PV1 --> PASS
    PV2 --> PASS
    PV3 --> PASS
    RV1 --> PASS
    RV2 --> PASS
    RV3 --> PASS
```

### 验证标准

| 验证项 | 验证方法 | 通过标准 |
|--------|---------|---------|
| Token更新 | 检查current_token值 | Token值与输入一致 |
| 过期检测 | 调用is_expired() | 返回值与预期一致 |
| 刷新判断 | 调用needs_refresh() | 返回值与预期一致 |
| 文件保存 | 检查文件内容 | 文件包含正确的Token |
| 文件加载 | 创建新实例检查 | Token从文件正确加载 |
| 浏览器启动 | 检查进程状态 | 浏览器成功启动 |
| Token嗅探 | 检查捕获结果 | Token被正确捕获 |
| 自动刷新 | 检查刷新后Token | Token已更新为新值 |

---

## 📈 测试报告模板

### 测试执行摘要

```
测试执行时间: YYYY-MM-DD HH:MM:SS
测试环境: Windows 10, Python 3.10+, Playwright Chromium
测试执行人: [测试人员]

测试结果统计:
- 单元测试: XX/XX 通过
- 集成测试: XX/XX 通过
- 端到端测试: XX/XX 通过
- 总体通过率: XX%

关键发现:
1. [发现1]
2. [发现2]
3. [发现3]

建议:
1. [建议1]
2. [建议2]
3. [建议3]
```

### 详细测试结果

| 测试ID | 测试名称 | 状态 | 执行时间 | 备注 |
|--------|---------|------|---------|------|
| UT-001 | 单例模式验证 | ✅通过 | 0.05s | - |
| UT-002 | Token更新 | ✅通过 | 0.03s | - |
| ... | ... | ... | ... | ... |

---

## 🚀 下一步行动

1. **执行单元测试** - 验证TokenManager核心逻辑
2. **执行集成测试** - 验证浏览器交互功能
3. **执行端到端测试** - 验证完整续杯流程
4. **生成测试报告** - 汇总测试结果和发现
5. **优化建议** - 基于测试结果提出改进建议

---

## 📚 参考资料

- [TokenManager源码](../core/token_manager.py)
- [BrowserManager源码](../core/browser.py)
- [现有测试文件](../tests/)
- [手动刷新测试](../test_refresh_manual.py)

---

**文档版本**: v1.0  
**创建时间**: 2026-03-29  
**最后更新**: 2026-03-29
