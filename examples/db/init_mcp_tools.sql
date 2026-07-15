-- MCP 工具注册表
CREATE TABLE IF NOT EXISTS mcp_tools (
    name         VARCHAR(64)  PRIMARY KEY COMMENT '工具唯一名',
    group_name   VARCHAR(32)  NOT NULL DEFAULT 'default' COMMENT '权限组: memory / product',
    description  TEXT         NOT NULL COMMENT '工具描述',
    params_json  JSON         DEFAULT NULL COMMENT '参数定义 {参数名: 类型+描述}',
    module_path  VARCHAR(256) NOT NULL COMMENT 'Python 模块路径 mcp_servers.skills.xxx',
    handler_name VARCHAR(64)  NOT NULL DEFAULT 'handle' COMMENT '入口函数名',
    enabled      BOOLEAN      DEFAULT TRUE COMMENT '是否启用',
    created_at   DOUBLE       NOT NULL,
    updated_at   DOUBLE       NOT NULL,
    INDEX idx_group (group_name),
    INDEX idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='MCP 工具注册表';

-- 用户偏好摘要工具（独立于 memory_nodes）
INSERT IGNORE INTO mcp_tools (name, group_name, description, params_json, module_path, handler_name, enabled, created_at, updated_at) VALUES
('save_user_summary', 'memory', '保存用户的消费特征摘要（覆盖写入 user_summary 表）',
 '{"user_id": "用户ID", "summary": "一句话消费特征描述"}',
 'mcp_servers.skills.save_user_summary', 'handle', TRUE, UNIX_TIMESTAMP(), UNIX_TIMESTAMP()),
('load_user_summary', 'memory', '加载用户的消费特征摘要（从 user_summary 表按 user_id 读取）',
 '{"user_id": "用户ID"}',
 'mcp_servers.skills.load_user_summary', 'handle', TRUE, UNIX_TIMESTAMP(), UNIX_TIMESTAMP());
