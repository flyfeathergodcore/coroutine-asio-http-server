FROM python:3.13-slim

# 覆盖宿主机代理设置，避免 apt/pip 走代理
ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG http_proxy=
ARG https_proxy=
ARG NO_PROXY=*
ARG no_proxy=*

WORKDIR /app

# 系统依赖（Playwright 需要 libwebkit2gtk 等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
RUN HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy="" NO_PROXY="*" no_proxy="*" \
    pip install --no-cache-dir \
    pymysql neo4j qdrant-client redis pyyaml httpx mcp \
    grpcio grpcio-tools playwright playwright-stealth \
    -q -i https://pypi.org/simple/

# 安装 Playwright Chromium 浏览器
RUN python -m playwright install chromium 2>&1

# 安装 Chromium 运行时系统依赖
RUN python -m playwright install-deps chromium 2>&1

# 编译 Python gRPC 桩代码
COPY proto/shopping.proto /app/proto/shopping.proto
RUN python -m grpc_tools.protoc \
    -I/app/proto \
    --python_out=/app \
    --grpc_python_out=/app \
    /app/proto/shopping.proto

# 创建 Cookie 目录
RUN mkdir -p /app/cookie

# 复制源码
COPY python_services/ai-agent-compare-values/ /app/

# 暴露端口
EXPOSE 8080 50054

# 默认 JD Cookie 路径环境变量
ENV JD_COOKIE_PATH=/app/cookie/jd_cookie.json

# 启动入口（HTTP + gRPC 双服务）
CMD ["python", "-u", "run.py"]
