#include "net/session_pool.hpp"

// 尝试获取空闲 Session（empty shell，需 Reset 注入新 stream+parser）
std::shared_ptr<Session<asio::ssl::stream<asio::ip::tcp::socket>>>
SessionPool::TryAcquireSession()
{
    if (!idle_.empty()) {
        auto s = std::move(idle_.back());
        idle_.pop_back();
        return s;
    }
    return nullptr;
}

void SessionPool::ReleaseSession(
    std::shared_ptr<Session<asio::ssl::stream<asio::ip::tcp::socket>>> session)
{
    idle_.push_back(std::move(session));
}

size_t SessionPool::IdleCount() const
{
    return idle_.size();
}
