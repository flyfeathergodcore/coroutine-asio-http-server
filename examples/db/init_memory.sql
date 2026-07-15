-- ============================================================
-- 记忆模块 MySQL 表结构
-- ============================================================

CREATE TABLE IF NOT EXISTS memory_nodes (
    id          VARCHAR(64)  PRIMARY KEY COMMENT '记忆唯一标识',
    type        VARCHAR(32)  NOT NULL COMMENT 'preference|knowledge|experience|temp',
    source      VARCHAR(16)  NOT NULL COMMENT 'user|agent|tool',
    content     TEXT         NOT NULL COMMENT '记忆正文',
    importance  DOUBLE       NOT NULL DEFAULT 0.5 COMMENT '重要性 0.0~1.0',
    created_at  DOUBLE       NOT NULL COMMENT 'unix 时间戳',
    updated_at  DOUBLE       NOT NULL COMMENT '最后更新时间戳',
    access_count INT         NOT NULL DEFAULT 0 COMMENT '被召回次数',
    source_session VARCHAR(128) NOT NULL DEFAULT '' COMMENT '来源会话 ID',
    entity_type VARCHAR(32)  DEFAULT NULL COMMENT '图实体类型',
    entity_id   VARCHAR(128) DEFAULT NULL COMMENT '图实体标识',

    -- 标签用 JSON 数组存
    tags        JSON         DEFAULT NULL,

    INDEX idx_type (type),
    INDEX idx_source_session (source_session),
    INDEX idx_importance (importance),
    INDEX idx_updated_at (updated_at),
    INDEX idx_entity_type (entity_type),
    FULLTEXT INDEX idx_content (content) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='长期记忆主表';
