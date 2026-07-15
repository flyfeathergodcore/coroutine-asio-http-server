-- ============================================================
-- 产品数据表 — 商品搜索 + 历史价格 + 评价
-- ============================================================

-- 产品主表
CREATE TABLE IF NOT EXISTS products (
    id              VARCHAR(64)   PRIMARY KEY COMMENT '产品唯一标识',
    name            VARCHAR(512)  NOT NULL COMMENT '产品名称',
    platform        VARCHAR(32)   NOT NULL COMMENT '平台: jd/taobao/pdd/1688/xianyu/meituan',
    category        VARCHAR(128)  DEFAULT NULL COMMENT '品类',
    brand           VARCHAR(128)  DEFAULT NULL COMMENT '品牌',
    model           VARCHAR(256)  DEFAULT NULL COMMENT '型号',
    current_price   DECIMAL(12,2) DEFAULT NULL COMMENT '当前售价',
    original_price  DECIMAL(12,2) DEFAULT NULL COMMENT '原价/划线价',
    currency        VARCHAR(8)    DEFAULT 'CNY' COMMENT '货币',

    -- 商品参数 (JSON: CPU/RAM/SSD/屏幕/显卡/重量...)
    parameters      JSON          DEFAULT NULL,

    -- 销量和评价
    sales_volume    INT           DEFAULT 0 COMMENT '销量',
    rating          DECIMAL(3,2)  DEFAULT NULL COMMENT '评分 1.00~5.00',
    review_count    INT           DEFAULT 0 COMMENT '评价数',
    positive_rate   DECIMAL(5,4)  DEFAULT NULL COMMENT '好评率 0.0000~1.0000',
    reviews_summary TEXT          DEFAULT NULL COMMENT '评价摘要(AI生成)',

    -- 链接
    url             VARCHAR(1024) DEFAULT NULL COMMENT '商品链接',
    image_url       VARCHAR(1024) DEFAULT NULL COMMENT '主图链接',

    -- 状态
    in_stock        BOOLEAN       DEFAULT TRUE COMMENT '是否有货',
    first_seen      DOUBLE        NOT NULL COMMENT '首次发现时间(unix)',
    last_updated    DOUBLE        NOT NULL COMMENT '最后更新时间',

    -- 索引
    INDEX idx_platform (platform),
    INDEX idx_category (category),
    INDEX idx_brand (brand),
    INDEX idx_price (current_price),
    INDEX idx_rating (rating),
    INDEX idx_sales (sales_volume),
    FULLTEXT INDEX idx_name (name) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='商品信息主表';


-- 历史价格表
CREATE TABLE IF NOT EXISTS product_prices (
    id              BIGINT        AUTO_INCREMENT PRIMARY KEY,
    product_id      VARCHAR(64)   NOT NULL COMMENT '关联 products.id',
    price           DECIMAL(12,2) NOT NULL COMMENT '价格',
    original_price  DECIMAL(12,2) DEFAULT NULL COMMENT '当时原价',
    platform        VARCHAR(32)   DEFAULT NULL,
    in_stock        BOOLEAN       DEFAULT TRUE,
    recorded_at     DOUBLE        NOT NULL COMMENT '记录时间(unix)',

    INDEX idx_product (product_id),
    INDEX idx_recorded (recorded_at),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='商品历史价格';


-- 用户评价快照表
CREATE TABLE IF NOT EXISTS product_reviews_snapshot (
    id              BIGINT        AUTO_INCREMENT PRIMARY KEY,
    product_id      VARCHAR(64)   NOT NULL COMMENT '关联 products.id',
    rating          DECIMAL(3,2)  DEFAULT NULL,
    positive_rate   DECIMAL(5,4)  DEFAULT NULL,
    review_count    INT           DEFAULT 0,
    keywords        JSON          DEFAULT NULL COMMENT '高频评价词',
    summary         TEXT          DEFAULT NULL COMMENT 'AI 评价摘要',
    snapshot_at     DOUBLE        NOT NULL COMMENT '快照时间',

    INDEX idx_product (product_id),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='商品评价快照';
