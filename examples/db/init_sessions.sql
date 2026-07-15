-- ============================================================
-- 会话存储表
-- ============================================================

-- 会话阶段存储（guide / product 各一条）
CREATE TABLE IF NOT EXISTS sessions (
    session_id  VARCHAR(64)   NOT NULL COMMENT '会话唯一标识',
    stage       VARCHAR(16)   NOT NULL DEFAULT 'guide' COMMENT '阶段: guide / product',
    user_id     VARCHAR(64)   NOT NULL DEFAULT '' COMMENT '用户 ID',
    messages    JSON          NOT NULL COMMENT '完整对话记录 [{role,phase,msg_type,content,metadata}]',
    created_at  DOUBLE        NOT NULL COMMENT '首次保存时间戳',
    updated_at  DOUBLE        NOT NULL COMMENT '最后更新时间戳',
    PRIMARY KEY (session_id, stage)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='会话阶段存储表';

-- 最终意图表（guide → product 交接）
CREATE TABLE IF NOT EXISTS session_intents (
    session_id  VARCHAR(64)   PRIMARY KEY COMMENT '关联 session_id',
    intent      JSON          NOT NULL COMMENT '导购最终意图 {category, intent_delta, ...}',
    created_at  DOUBLE        NOT NULL COMMENT '创建时间戳',
    updated_at  DOUBLE        NOT NULL COMMENT '最后更新时间戳',
    INDEX idx_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='会话最终意图表';
