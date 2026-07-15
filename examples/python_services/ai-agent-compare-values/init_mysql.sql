-- 用户历史会话主表
CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR(32) NOT NULL COMMENT '会话唯一标识ID',
    stage ENUM('guide','product') NOT NULL DEFAULT 'guide' COMMENT '当前执行Agent阶段：guide/product',
    status_code SMALLINT NOT NULL DEFAULT 0 COMMENT '会话状态码',
    content JSON NOT NULL DEFAULT (JSON_ARRAY()) COMMENT '完整对话消息列表 [{role:"",message:""}]',
    create_at DATETIME(3) NOT NULL COMMENT '记录创建时间，精确到毫秒',
    count TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '会话访问次数',
    update_at DATETIME(3) NOT NULL COMMENT '最后更新时间，精确到毫秒',
    PRIMARY KEY (session_id, status_code, stage)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='用户历史会话主表';

-- 用户会话意向明细表
CREATE TABLE IF NOT EXISTS session_intent (
    session_id VARCHAR(32) NOT NULL COMMENT '会话标识ID，关联sessions表',
    stage ENUM('guide','product') NOT NULL DEFAULT 'guide' COMMENT '当前执行Agent阶段：guide/product',
    status_code SMALLINT NOT NULL DEFAULT 0 COMMENT '会话状态码',
    category JSON NOT NULL DEFAULT JSON_ARRAY() COMMENT '用户意向产品集合 ["产品1","产品2"]',
    solve_category JSON NOT NULL DEFAULT JSON_ARRAY() COMMENT '已完成咨询产品集合',
    now_category VARCHAR(20) NOT NULL DEFAULT '' COMMENT '当前正在咨询产品',
    count_categorys TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '意向产品总数',
    create_at DATETIME(3) NOT NULL COMMENT '记录创建时间，精确到毫秒',
    update_at DATETIME(3) NOT NULL COMMENT '最后更新时间，精确到毫秒',
    INDEX idx_session_id (session_id),
    -- 逻辑关联 session_id，不做物理外键（sessions 主键是联合主键）
    INDEX idx_sid_stage_status (session_id, stage, status_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='用户会话产品意向明细表';

-- 用户画像汇总表
CREATE TABLE IF NOT EXISTS user_summary (
    user_id VARCHAR(32) NOT NULL COMMENT '用户唯一ID',
    summary JSON DEFAULT JSON_OBJECT() COMMENT '用户画像汇总信息',
    create_at DATETIME(3) NOT NULL COMMENT '画像创建时间，精确到毫秒',
    update_at DATETIME(3) NOT NULL COMMENT '画像最后更新时间，精确到毫秒',
    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='用户画像汇总表';

-- 商品基础信息主表
CREATE TABLE IF NOT EXISTS products (
    product_id INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '商品自增主键',
    jd_sku VARCHAR(32) NOT NULL COMMENT '京东SKU编码',
    product_name VARCHAR(255) NOT NULL DEFAULT '' COMMENT '商品名称',
    current_price INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '当前最低价格(单位：分)',
    min_platform VARCHAR(32) NOT NULL COMMENT '最低价所属平台',
    url VARCHAR(1024) NOT NULL DEFAULT '' COMMENT '商品链接',
    image_url VARCHAR(1024) NOT NULL DEFAULT '' COMMENT '商品主图链接',
    parameters JSON DEFAULT NULL COMMENT '商品参数，如 {"CPU":"i7","RAM":"16GB"}',
    create_at DATETIME(3) NOT NULL COMMENT '商品录入时间，精确到毫秒',
    update_at DATETIME(3) NOT NULL COMMENT '商品信息更新时间',
    PRIMARY KEY (product_id),
    UNIQUE KEY uk_jd_sku (jd_sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='商品基础信息主表';

-- 商品历史价格记录表（比价、价格走势）
CREATE TABLE IF NOT EXISTS product_price_history (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '历史记录自增主键',
    jd_sku VARCHAR(32) NOT NULL COMMENT '关联商品SKU',
    price INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '本次抓取价格(单位：分)',
    platform VARCHAR(32) NOT NULL COMMENT '价格所属平台',
    capture_time DATETIME(3) NOT NULL COMMENT '价格抓取时间，精确到毫秒',
    PRIMARY KEY (id),
    -- 联合索引：快速查询单商品历史价格，按时间倒序
    INDEX idx_sku_time (jd_sku, capture_time DESC),
    -- 外键：商品删除自动清理历史价格
    CONSTRAINT fk_sku_ref_product
    FOREIGN KEY (jd_sku) REFERENCES products(jd_sku)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='商品历史价格记录表（用于价格走势、历史比价）';