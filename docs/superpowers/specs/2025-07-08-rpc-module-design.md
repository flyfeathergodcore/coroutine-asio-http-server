# RPC 模块设计规范

**日期：** 2025-07-08  
**作者：** Brainstorming Session  
**状态：** 已批准

---

## 1. 概述

RPC 模块是 HTTP 服务器与后端微服务（ai-chat、rag、ppt）通信的核心组件。采用全局单例模式，集成服务发现、负载均衡、故障重试、连接池管理。

### 业务需求
- 支持三个后端 gRPC 服务：AI 会话（ChatStream）、RAG 检索、PPT 自动制作
- 分布式架构：HTTP 服务器作为网关，后端服务独立部署
- 高可用：服务发现 + 自动故障转移 + 智能重试

---

## 2. 整体架构

```
┌─ RpcModule (全局单例) ──────────────────────────┐
│                                                  │
│  ┌─ ServiceDiscovery ────────────────────────┐ │
│  │ • 连接注册中心 (Consul)                   │ │
│  │ • 监听服务变更 (watch/订阅)               │ │
│  │ • 心跳检测 (定期 ping)                    │ │
│  │ • 维护活跃实例列表                        │ │
│  └─ InstanceCache: {service: [inst1, inst2]}─┘ │
│                         ↓                       │
│  ┌─ LoadBalancer ────────────────────────────┐ │
│  │ • 最少连接算法 (选择连接数最少的实例)     │ │
│  │ • 实例健康状态查询                        │ │
│  │ • 故障实例隔离 (标记为不可用)             │ │
│  └────────────────────────────────────────────┘ │
│                         ↓                       │
│  ┌─ ConnectionPool ───────────────────────────┐ │
│  │ • gRPC 连接缓存 {inst_addr: [conn1, conn2]}│ │
│  │ • 连接复用和生命周期管理                  │ │
│  └────────────────────────────────────────────┘ │
│                         ↓                       │
│  ┌─ RetryPolicy ──────────────────────────────┐ │
│  │ • 状态码解析 (500/300/其他)                │ │
│  │ • 差异化重试决策                          │ │
│  │ • 等待和指数退避                          │ │
│  └────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

**调用流程：**
1. 业务层（ChatHandler/RagHandler）调用 `RpcModule::Call()`
2. RpcModule 查询 LoadBalancer 获取最优实例
3. LoadBalancer 从 InstanceCache 读取活跃实例，返回连接数最少的
4. RpcModule 从 ConnectionPool 获取或创建连接到该实例
5. 发起 gRPC 调用
6. 若失败，RetryPolicy 根据状态码决策（重试/切换实例/失败）
7. 若重试，回到步骤 2

---

## 3. 核心组件设计

### 3.1 ServiceDiscovery（服务发现）

**职责：** 连接注册中心，监听服务变更，维护活跃实例列表

```cpp
class ServiceDiscovery {
public:
    // 初始化与注册中心连接
    bool Connect(const std::string& consul_addr);

    // 监听服务变更（后台线程）
    void WatchService(const std::string& service_name);

    // 查询活跃实例列表
    std::vector<ServiceInstance> GetInstances(const std::string& service_name);

private:
    // 心跳检测 (定期检查实例健康)
    void HeartbeatCheck();
};

struct ServiceInstance {
    std::string service_name;      // "ai-chat", "rag", "ppt"
    std::string address;            // "127.0.0.1:50051"
    int weight = 1;                 // 权重（预留）
    bool healthy = true;            // 健康标记
    int64_t last_heartbeat = 0;    // 最后心跳时间
};
```

**实现要点：**
- 后台线程异步监听注册中心变更（Consul watch）
- 心跳机制定期更新实例状态（默认 5 秒一次）
- GetInstances() 返回当前活跃实例（过滤掉不健康的）
- 与注册中心失联时使用本地缓存

### 3.2 LoadBalancer（负载均衡）

**职责：** 根据最少连接算法选择最优实例，管理故障隔离

```cpp
class LoadBalancer {
public:
    // 根据最少连接选择实例
    std::optional<ServiceInstance> SelectInstance(
        const std::string& service_name);

    // 记录实例连接数变化
    void RecordConnectionOpen(const std::string& addr);
    void RecordConnectionClose(const std::string& addr);

    // 标记实例故障（暂时隔离）
    void MarkUnhealthy(const std::string& addr, int timeout_sec = 30);

private:
    std::map<std::string, int> connection_count_;       // addr -> 连接数
    std::map<std::string, int64_t> unhealthy_until_;    // 故障隔离时间
};
```

**算法：**
- 选择 `connection_count_` 最低的实例
- 故障实例暂时隔离（默认 30 秒后重试）
- 所有实例都故障时返回 std::nullopt，让上层处理

### 3.3 ConnectionPool（连接池）

**职责：** 缓存和复用 gRPC 连接，管理生命周期

```cpp
class ConnectionPool {
public:
    // 获取到指定实例的连接
    std::shared_ptr<grpc::ClientContext> AcquireConnection(
        const std::string& addr);

    // 释放连接（回收到池中）
    void ReleaseConnection(const std::string& addr,
                          std::shared_ptr<grpc::ClientContext> conn);

private:
    std::map<std::string, std::deque<std::shared_ptr<grpc::ClientContext>>> pools_;
    std::map<std::string, int> max_pool_size_;  // 每个实例最多连接数
};
```

**实现要点：**
- 连接按实例地址分组缓存
- AcquireConnection 优先从池中取，池空时创建新连接
- ReleaseConnection 将连接放回池中复用
- 空闲连接定期清理（配置参数）

### 3.4 RetryPolicy（重试策略）

**职责：** 根据响应状态码制定重试决策

```cpp
class RetryPolicy {
public:
    enum class RetryAction {
        SUCCESS,           // 成功，不重试
        RETRY_SAME,        // 重试同实例（带延迟）
        RETRY_OTHER,       // 切换实例重试
        FAIL               // 放弃
    };

    RetryAction DecideRetry(int status_code, int retry_count);

private:
    int max_retries_ = 3;
};
```

**重试决策表：**

| 状态码 | 含义 | 动作 | 重试次数 |
|--------|------|------|---------|
| 500 | 实例宕机 | RETRY_OTHER | 立即切换实例 |
| 300 | 实例高负荷 | RETRY_SAME | 等待后重试，最多 3 次 |
| 其他 | 业务错误 | FAIL | 不重试 |

**退避策略：**
- 同实例重试：指数退避 (100ms, 200ms, 400ms, ...)
- 切换实例重试：立即执行

---

## 4. 数据流

### 4.1 初始化流程

```
启动 main.cpp
  ↓
RpcModule::Initialize()
  ├─ ServiceDiscovery::Connect(consul_addr)
  ├─ ServiceDiscovery::WatchService("ai-chat")
  ├─ ServiceDiscovery::WatchService("rag")
  ├─ ServiceDiscovery::WatchService("ppt")
  └─ 启动后台心跳线程
```

### 4.2 请求调用流程（以 ChatHandler 为例）

```
ChatHandler::HandleStream(ctx, sink)
  ↓
RpcModule::CallService("ai-chat", request)
  ├─ LoadBalancer::SelectInstance("ai-chat")
  │   └─ 从 ServiceDiscovery 查询活跃实例
  │   └─ 选择 connection_count_ 最少的
  │   └─ 返回 ServiceInstance
  ├─ ConnectionPool::AcquireConnection(instance.address)
  │   └─ 从池中取或创建新连接
  ├─ 发起 gRPC 调用
  └─ 等待响应
      ↓
  响应返回
    ├─ 状态 200 → 成功，ConnectionPool::ReleaseConnection(连接)
    ├─ 状态 500 → RetryPolicy::DecideRetry() → RETRY_OTHER
    │   └─ LoadBalancer::MarkUnhealthy(instance.address, 30s)
    │   └─ 回到 SelectInstance 重新选择
    │   └─ 最多重试 3 次
    └─ 状态 300 → RetryPolicy::DecideRetry() → RETRY_SAME
        └─ 等待 (指数退避: 100ms, 200ms, 400ms)
        └─ 重试同实例，最多 3 次
```

### 4.3 心跳更新流程

```
后台心跳线程 (每 5 秒)
  ↓
ServiceDiscovery::HeartbeatCheck()
  ├─ 查询注册中心所有服务实例
  ├─ 对比本地 InstanceCache
  ├─ 新增实例 → 添加到缓存
  ├─ 下线实例 → 标记为不健康，30 秒后移除
  └─ 更新 last_heartbeat 时间戳
```

---

## 5. 配置

### config.yaml

```yaml
rpc:
  registry:
    type: "consul"
    address: "127.0.0.1:8500"
    datacenter: "dc1"

  services:
    - name: "ai-chat"
      timeout_sec: 30
    - name: "rag"
      timeout_sec: 30
    - name: "ppt"
      timeout_sec: 60

  load_balance:
    strategy: "least_connections"
    unhealthy_timeout_sec: 30
    max_retries: 3

  connection_pool:
    max_size_per_instance: 10
    idle_timeout_sec: 300

  heartbeat:
    interval_sec: 5
```

---

## 6. 监控与可观测性

### 6.1 RPC 指标集成到 MetricsCollector

```cpp
struct MetricsSnapshot {
    // 原有 HTTP 指标
    uint64_t request_count = 0;
    uint64_t error_count = 0;

    // 新增 RPC 指标
    struct RpcMetrics {
        // 服务级别
        std::map<std::string, uint64_t> rpc_requests;      // 各服务请求数
        std::map<std::string, uint64_t> rpc_errors;        // 各服务错误数
        std::map<std::string, uint64_t> rpc_retries;       // 各服务重试次数

        // 实例级别
        std::map<std::string, int> instance_count;         // 各服务活跃实例数
        std::map<std::string, int> healthy_instances;      // 健康实例数
        std::map<std::string, int> active_connections;     // 各实例活跃连接数

        // 性能
        std::map<std::string, uint64_t> rpc_latency_us;    // 各服务平均延迟
    } rpc;
};
```

### 6.2 Dashboard 展示（/metrics/stream）

```json
{
  "type": "metrics_snapshot",
  "http": {
    "requests": 1000,
    "errors": 5,
    "bytes_sent": 102400,
    "latency_p99": 45000
  },
  "rpc": {
    "services": {
      "ai-chat": {
        "requests": 500,
        "errors": 2,
        "retries": 15,
        "instances": { "healthy": 2, "total": 2 },
        "latency_avg": 50000
      },
      "rag": {
        "requests": 300,
        "errors": 1,
        "retries": 8,
        "instances": { "healthy": 3, "total": 3 },
        "latency_avg": 80000
      },
      "ppt": {
        "requests": 200,
        "errors": 0,
        "retries": 5,
        "instances": { "healthy": 1, "total": 1 },
        "latency_avg": 120000
      }
    }
  }
}
```

---

## 7. 错误处理与降级

### 7.1 故障场景处理

| 场景 | 处理方案 |
|------|--------|
| 注册中心连接失败 | 使用本地缓存的实例列表，降级模式运行 |
| 所有实例不可用 | 返回错误，业务层自行决策（失败、队列重试、降级方案） |
| gRPC 连接超时 | 根据状态码重试（500 切换实例，300 等待重试） |
| 连接池耗尽 | 创建新连接或等待连接归还（可配置超时） |
| 心跳更新失败 | 使用缓存的实例，继续运行，30 秒后重试心跳 |

### 7.2 业务层错误处理

```cpp
auto reply = co_await rpc_module_->CallAsync("ai-chat", request);
if (!reply.ok()) {
    if (reply.error_code() == ErrorCode::SERVICE_UNAVAILABLE) {
        sink.SendError("所有 ai-chat 实例不可用，请稍后重试");
    } else if (reply.error_code() == ErrorCode::TIMEOUT) {
        sink.SendError("请求超时，请重试");
    } else {
        sink.SendError(reply.error_message());
    }
}
```

---

## 8. 业务层使用接口

```cpp
// 在 main.cpp 中初始化
auto rpc_module = std::make_shared<RpcModule>();
rpc_module->Initialize(config.rpc);

// 在业务 Handler 中使用
class ChatHandler : public RequestHandler {
    asio::awaitable<void> HandleStream(const Context& ctx, StreamSink& sink) {
        auto reply = co_await rpc_module_->CallAsync(
            "ai-chat",
            ChatRequest{...},
            std::chrono::seconds(30)  // 超时 30 秒
        );
        // 处理 reply...
    }
};
```

---

## 9. 部署

### 9.1 后端服务注册

后端服务启动时自动注册到 Consul：

```bash
./ai-chat-service --name ai-chat --port 50051 --consul 127.0.0.1:8500
```

自动调用 Consul API：
```
POST /v1/agent/service/register
{
  "ID": "ai-chat-1",
  "Name": "ai-chat",
  "Address": "127.0.0.1",
  "Port": 50051,
  "Check": {
    "HTTP": "http://127.0.0.1:50051/health",
    "Interval": "5s"
  }
}
```

### 9.2 Docker Compose

```yaml
version: '3'
services:
  consul:
    image: consul:1.15
    ports: [8500:8500]
    command: agent -server -ui -bootstrap-expect=1 -client=0.0.0.0

  ai-chat:
    build: ./services/ai-chat
    ports: [50051:50051]
    environment:
      CONSUL_ADDR: consul:8500
    depends_on: [consul]

  rag:
    build: ./services/rag
    ports: [50052:50052]
    environment:
      CONSUL_ADDR: consul:8500
    depends_on: [consul]

  ppt:
    build: ./services/ppt
    ports: [50053:50053]
    environment:
      CONSUL_ADDR: consul:8500
    depends_on: [consul]

  http-server:
    build: ./
    ports: [443:443]
    environment:
      CONSUL_ADDR: consul:8500
    depends_on: [consul, ai-chat, rag, ppt]
```

---

## 10. 实现阶段

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| **Phase 1** | ServiceDiscovery + Consul 集成 + 心跳机制 | ⭐⭐⭐ |
| **Phase 2** | LoadBalancer（最少连接）+ ConnectionPool | ⭐⭐⭐ |
| **Phase 3** | RetryPolicy（状态码驱动重试） | ⭐⭐⭐ |
| **Phase 4** | 集成到 MetricsCollector，暴露 Dashboard | ⭐⭐ |
| **Phase 5** | 故障模拟、压测、文档 | ⭐ |

---

## 11. 测试策略

| 层级 | 测试 | 方法 |
|------|------|------|
| **单元** | ServiceDiscovery、LoadBalancer、RetryPolicy 逻辑 | 模拟 Consul 响应，验证算法 |
| **集成** | ConnectionPool + LoadBalancer 配合 | 模拟多实例，验证连接复用 |
| **功能** | 完整的请求流程 + 故障转移 | Docker Compose 启动真实服务 |
| **压测** | 并发请求、故障恢复 | wrk/ab 测试，注入故障验证重试 |

---

## 12. 后续优化方向

1. **动态配置**：支持运行时修改负载均衡策略、重试参数
2. **链路追踪**：集成 OpenTelemetry，追踪请求在各服务间的流转
3. **高级算法**：支持加权轮询、一致性哈希等其他负载均衡策略
4. **断路器**：快速故障转移，防止级联故障
5. **本地缓存**：对 RAG 结果进行本地缓存，减少后端调用

