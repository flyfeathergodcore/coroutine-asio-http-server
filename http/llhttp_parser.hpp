#pragma once
#include "http/context.hpp"
#include "http/llhttp.h"
#include "net/session_region.hpp"
#include <cstddef>
#include <string_view>

// llhttp-based HTTP/1.1 parser.
//
// All parsed data is stored as offset-based RegionOff references into
// the SessionRegion.  This survives region migration (vector-like growth
// of the backing buffer) because offsets are relative to the region base.
//
class LlhttpParser : public Context {
public:
    LlhttpParser();
    ~LlhttpParser() override;

    ParseResult Feed(const char* data, size_t len) override;

    std::string_view Method()  const override { return method_; }
    std::string_view Path()    const override;
    std::string_view Version() const override { return version_; }
    std::string_view Header(const std::string_view key) const override;
    std::string_view Body()   const override;

private:
    llhttp_t parser_;
    llhttp_settings_t settings_;
    bool message_complete_ = false;

    // ── Parsed results (static or offset-based) ──

    std::string_view method_;   // points to static storage ("GET", "POST"...)
    std::string_view version_;  // points to static storage ("HTTP/1.1"...)
    RegionOff path_;
    RegionOff body_;

    // ── Flat header array (offset-based, survives migration) ──

    static constexpr size_t kMaxHeaders = 64;
    struct HeaderEntry {
        RegionOff name;
        RegionOff value;
    };
    HeaderEntry headers_[kMaxHeaders];
    int header_count_ = 0;

    // ── Accumulation buffers (stack only, flushed to pool on completion) ──

    char url_buf_[2048];
    size_t url_len_ = 0;

    char cur_field_[256];
    size_t cur_field_len_ = 0;
    char cur_value_[4096];
    size_t cur_value_len_ = 0;

    // Body: pre-allocated from pool when Content-Length is known
    RegionOff body_prealloc_;
    size_t body_written_ = 0;

    // ── Callbacks ──

    static int OnUrl(llhttp_t* p, const char* at, size_t len);
    static int OnHeaderField(llhttp_t* p, const char* at, size_t len);
    static int OnHeaderValue(llhttp_t* p, const char* at, size_t len);
    static int OnHeadersComplete(llhttp_t* p);
    static int OnBody(llhttp_t* p, const char* at, size_t len);
    static int OnMessageComplete(llhttp_t* p);

    /// Flush accumulated header field+value into the flat array.
    void FlushHeader();
};
