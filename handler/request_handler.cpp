#include "handler/request_handler.hpp"
#include "net/response.hpp"
#include "net/session_region.hpp"
#include <unistd.h>

StaticFileHandler::StaticFileHandler(const FileCache* cache)
    : cache_(cache) {}

Response StaticFileHandler::Handle(const Context& ctx)
{
    auto* pool = ctx.Pool();

    if (ctx.Method() != "GET") {
        return Response::Error(501, *pool);
    }

    std::string norm_path = NormalizePath(ctx.Path());
    if (norm_path.empty()) {
        return Response::Error(403, *pool);
    }

    auto* file = cache_->Get(norm_path);
    if (!file) {
        return Response::Error(404, *pool);
    }

    // In-memory content available → gather-write (faster for SSL)
    if (!file->content.empty()) {
        Response resp(200, *pool);
        resp.Header("Content-Type", file->mime);
        resp.Header("Content-Length", file->content.size());
        // Inject any headers from middleware (CORS etc.)
        for (int i = 0; i < ctx.ResponseHeaderCount(); i++)
            resp.Header(ctx.ResponseHeaderKey(i), ctx.ResponseHeaderVal(i));
        resp.EndHeaders();
        resp.Body(file->content);
        return resp;
    }

    // Large file: use sendfile path
    if (file->fd >= 0) {
        Response resp(200, *pool);
        resp.Header("Content-Type", file->mime);
        resp.Header("Content-Length", file->file_size);
        for (int i = 0; i < ctx.ResponseHeaderCount(); i++)
            resp.Header(ctx.ResponseHeaderKey(i), ctx.ResponseHeaderVal(i));
        resp.EndHeaders();
        resp.BodyFile(file->fd, file->file_size);
        return resp;
    }

    return Response::Error(404, *pool);
}

std::string StaticFileHandler::NormalizePath(std::string_view raw) const
{
    std::string p(raw);
    if (p.empty() || p[0] != '/') return {};
    if (p.find("..") != std::string::npos) return {};
    if (p.find("//") != std::string::npos) return {};

    if (p.back() == '/') p += "index.html";
    else if (p.size() == 1) p += "index.html";

    return p;
}
