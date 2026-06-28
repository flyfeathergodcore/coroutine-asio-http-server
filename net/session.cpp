#include "net/session.hpp"
#include "net/region_pool.hpp"
#include <iostream>
#include <sys/sendfile.h>
#include <unistd.h>

using asio::ip::tcp;

template<typename Stream>
Session<Stream>::Session(Stream stream,
                         RequestHandler& handler,
                         MiddlewareChain& middleware,
                         RegionPool* region_pool)
    : stream_(std::move(stream))
    , handler_(handler)
    , middleware_(middleware)
{
    if (region_pool)
        region_.Init(region_pool);
}

template<typename Stream>
asio::awaitable<void> Session<Stream>::Start()
{
    auto self = this->shared_from_this();
    std::array<char, 4096> buf;
    try {
    for (;;)
    {
        region_.Reset();  // bump pointer back to 0 (keep region, don't release)

        // Inject region into parser BEFORE Feed (parser stores data in region).
        parser_.SetPool(&region_);

        auto [ec, n] = co_await stream_.async_read_some(
            asio::buffer(buf), asio::as_tuple(asio::use_awaitable));
        if (ec) break;

        {   // Raw byte phase: middleware can short-circuit here
            auto mw = middleware_.ProcessRaw(buf.data(), static_cast<size_t>(n));
            if (!mw.IsNone()) { co_await Send(std::move(mw)); break; }
        }

        auto ret = parser_.Feed(buf.data(), static_cast<size_t>(n));
        if (ret == ParseResult::Incomplete) continue;
        if (ret == ParseResult::Error) { co_await Send(Response::Error(400, region_)); break; }

        // Onion chain → handler (handler uses ctx.Pool() to access region)
        auto resp = middleware_.Execute(parser_, handler_);
        co_await Send(std::move(resp));

        // Keep-alive check
        auto conn = parser_.Header("connection");
        if (conn == "close") break;
    }
    } catch (std::exception& e) {
        std::cerr << "[session] " << e.what() << std::endl;
    }
}

template<typename Stream>
asio::awaitable<void> Session<Stream>::Send(Response response)
{
    if (response.IsFile())
    {
        co_await async_write(stream_,
            asio::buffer(response.HeaderWire()),
            asio::use_awaitable);

        auto fd = response.Fd();
        ::lseek(fd, 0, SEEK_SET);
        auto remaining = response.FileSize();

        if constexpr (std::is_same_v<Stream, tcp::socket>)
        {
            off_t offset = 0;
            while (remaining > 0) {
                ssize_t n = ::sendfile(stream_.native_handle(), fd,
                                       &offset, remaining);
                if (n <= 0) {
                    if (errno == EAGAIN) continue;
                    break;
                }
                remaining -= static_cast<size_t>(n);
            }
        }
        else
        {
            std::array<char, 65536> readbuf;
            while (remaining > 0) {
                auto to_read = std::min(remaining, readbuf.size());
                ssize_t n = ::read(fd, readbuf.data(), to_read);
                if (n <= 0) break;
                co_await async_write(stream_,
                    asio::buffer(readbuf.data(), static_cast<size_t>(n)),
                    asio::use_awaitable);
                remaining -= static_cast<size_t>(n);
            }
        }
    }
    else
    {
        auto body = response.BodyWire();
        if (!body.empty())
        {
            // Single gather-write: headers + body in one SSL record
            std::array<asio::const_buffer, 2> bufs = {{
                asio::buffer(response.HeaderWire()),
                asio::buffer(body)
            }};
            co_await async_write(stream_, bufs, asio::use_awaitable);
        }
        else
        {
            co_await async_write(stream_,
                asio::buffer(response.HeaderWire()),
                asio::use_awaitable);
        }
    }
}

template class Session<tcp::socket>;
template class Session<asio::ssl::stream<tcp::socket>>;
