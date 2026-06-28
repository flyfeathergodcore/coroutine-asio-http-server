#include "http/llhttp_parser.hpp"
#include "net/session_region.hpp"
#include <cctype>
#include <cstring>

static LlhttpParser* Self(llhttp_t* p) {
    return static_cast<LlhttpParser*>(p->data);
}

static void Lowercase(char* s, size_t n) {
    for (size_t i = 0; i < n; i++)
        s[i] = static_cast<char>(std::tolower(static_cast<unsigned char>(s[i])));
}

// ── Accessors (convert RegionOff → string_view) ──

std::string_view LlhttpParser::Path() const {
    auto* r = Pool();
    return r ? r->ToView(path_) : std::string_view{};
}

std::string_view LlhttpParser::Body() const {
    auto* r = Pool();
    return r ? r->ToView(body_) : std::string_view{};
}

std::string_view LlhttpParser::Header(const std::string_view key) const {
    auto* r = Pool();
    if (!r) return {};
    for (int i = 0; i < header_count_; i++) {
        if (r->ToView(headers_[i].name) == key)
            return r->ToView(headers_[i].value);
    }
    return {};
}

// ── Callbacks ──

int LlhttpParser::OnUrl(llhttp_t* p, const char* at, size_t len) {
    auto* self = Self(p);
    size_t copy = std::min(len, sizeof(self->url_buf_) - self->url_len_);
    std::memcpy(self->url_buf_ + self->url_len_, at, copy);
    self->url_len_ += copy;
    return 0;
}

int LlhttpParser::OnHeaderField(llhttp_t* p, const char* at, size_t len) {
    auto* self = Self(p);

    // Transition from value → new field: flush the completed pair
    if (self->cur_value_len_ > 0)
        self->FlushHeader();

    size_t copy = std::min(len, sizeof(self->cur_field_) - self->cur_field_len_);
    std::memcpy(self->cur_field_ + self->cur_field_len_, at, copy);
    self->cur_field_len_ += copy;
    return 0;
}

int LlhttpParser::OnHeaderValue(llhttp_t* p, const char* at, size_t len) {
    auto* self = Self(p);
    size_t copy = std::min(len, sizeof(self->cur_value_) - self->cur_value_len_);
    std::memcpy(self->cur_value_ + self->cur_value_len_, at, copy);
    self->cur_value_len_ += copy;
    return 0;
}

int LlhttpParser::OnHeadersComplete(llhttp_t* p) {
    auto* self = Self(p);

    // Flush last header pair
    self->FlushHeader();

    // Method — static string, zero allocation
    switch (llhttp_get_method(p)) {
        case HTTP_GET:     self->method_ = "GET"; break;
        case HTTP_POST:    self->method_ = "POST"; break;
        case HTTP_PUT:     self->method_ = "PUT"; break;
        case HTTP_DELETE:  self->method_ = "DELETE"; break;
        case HTTP_HEAD:    self->method_ = "HEAD"; break;
        case HTTP_OPTIONS: self->method_ = "OPTIONS"; break;
        default:           self->method_ = "UNKNOWN"; break;
    }

    // Version — static string for the common cases
    int maj = llhttp_get_http_major(p);
    int min = llhttp_get_http_minor(p);
    if (maj == 1 && min == 1)
        self->version_ = "HTTP/1.1";
    else if (maj == 1 && min == 0)
        self->version_ = "HTTP/1.0";
    else
        self->version_ = "HTTP/1.1";

    // Pre-allocate body from pool if Content-Length is known
    auto cl = p->content_length;
    auto* pool = self->Pool();
    if (cl > 0 && pool) {
        void* buf = pool->Alloc(static_cast<size_t>(cl));
        if (buf) {
            auto off = static_cast<uint32_t>(static_cast<char*>(buf) - pool->Data());
            self->body_prealloc_ = {off, static_cast<uint32_t>(cl)};
            self->body_written_ = 0;
        }
    }

    return 0;
}

int LlhttpParser::OnBody(llhttp_t* p, const char* at, size_t len) {
    auto* self = Self(p);

    if (self->body_prealloc_.IsValid()) {
        auto* r = self->Pool();
        if (r) {
            auto remain = self->body_prealloc_.len - self->body_written_;
            auto copy = std::min(len, static_cast<size_t>(remain));
            if (copy > 0) {
                // body_prealloc_.off is relative to the region's Data().
                // But after migration, Data() may have changed.
                // body_prealloc_.off is still valid (memcpy preserved it).
                std::memcpy(r->Data() + self->body_prealloc_.off + self->body_written_,
                           at, copy);
                self->body_written_ += copy;
            }
        }
    }

    return 0;
}

int LlhttpParser::OnMessageComplete(llhttp_t* p) {
    Self(p)->message_complete_ = true;
    return 0;
}

void LlhttpParser::FlushHeader() {
    if (cur_field_len_ == 0 || cur_value_len_ == 0) {
        cur_field_len_ = 0;
        cur_value_len_ = 0;
        return;
    }

    auto* pool = Pool();
    if (!pool || header_count_ >= static_cast<int>(kMaxHeaders)) {
        cur_field_len_ = 0;
        cur_value_len_ = 0;
        return;
    }

    Lowercase(cur_field_, cur_field_len_);
    headers_[header_count_].name  = pool->DupOff({cur_field_, cur_field_len_});
    headers_[header_count_].value = pool->DupOff({cur_value_, cur_value_len_});
    header_count_++;

    cur_field_len_ = 0;
    cur_value_len_ = 0;
}

// ── Public API ──

LlhttpParser::LlhttpParser() {
    llhttp_settings_init(&settings_);
    settings_.on_url              = OnUrl;
    settings_.on_header_field     = OnHeaderField;
    settings_.on_header_value     = OnHeaderValue;
    settings_.on_headers_complete = OnHeadersComplete;
    settings_.on_body             = OnBody;
    settings_.on_message_complete = OnMessageComplete;

    llhttp_init(&parser_, HTTP_REQUEST, &settings_);
    parser_.data = this;
}

LlhttpParser::~LlhttpParser() = default;

ParseResult LlhttpParser::Feed(const char* data, size_t len) {
    llhttp_reset(&parser_);

    // Reset per-request state
    message_complete_ = false;
    header_count_  = 0;
    url_len_       = 0;
    cur_field_len_ = 0;
    cur_value_len_ = 0;
    body_prealloc_ = {};
    body_written_  = 0;
    path_ = {};
    body_ = {};
    ClearResponseHeaders();
    // method_, version_ are set in OnHeadersComplete.

    llhttp_errno_t err = llhttp_execute(&parser_, data, len);
    if (err != HPE_OK && err != HPE_PAUSED)
        return ParseResult::Error;

    // Dup accumulated URL into pool (after all callbacks — no more migration).
    if (url_len_ > 0 && Pool())
        path_ = Pool()->DupOff({url_buf_, url_len_});

    // Body RegionOff — pre-allocated, now just set the view.
    if (body_prealloc_.IsValid() && body_written_ == body_prealloc_.len)
        body_ = body_prealloc_;

    if (!message_complete_)
        return ParseResult::Incomplete;

    return ParseResult::Complete;
}
