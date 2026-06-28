#include "net/region_pool.hpp"
#include <algorithm>
#include <cstring>
#include <iostream>
#include <sys/mman.h>
#include <unistd.h>

RegionPool::RegionPool() {
    void* p = mmap(nullptr, kPoolSize, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) {
        std::cerr << "[region_pool] mmap(" << (kPoolSize / 1024 / 1024)
                  << " MB) failed: " << strerror(errno) << std::endl;
        p = nullptr;
    }
    base_ = static_cast<char*>(p);
    // fprintf(stderr, "[region_pool] mmap %zu MB at %p\n",
    //         kPoolSize / 1024 / 1024, p);
}

RegionPool::~RegionPool() {
    if (base_) {
        munmap(base_, kPoolSize);
    }
}

std::pair<size_t, size_t> RegionPool::Acquire(size_t min_size) {
    // Round up to kMinRegion alignment for freelist simplicity.
    size_t need = ((min_size + kMinRegion - 1) / kMinRegion) * kMinRegion;
    if (need < kMinRegion) need = kMinRegion;

    // First-fit through freelist.
    for (auto it = free_.begin(); it != free_.end(); ++it) {
        if (it->size >= need) {
            auto result = std::make_pair(it->offset, it->size);
            free_.erase(it);
            return result;
        }
    }

    // Bump allocate.
    size_t offset = bump_offset_;
    bump_offset_ += need;
    if (bump_offset_ > kPoolSize) {
        std::cerr << "[region_pool] OOM: need " << need
                  << ", bump " << bump_offset_ << " > " << kPoolSize << std::endl;
        return {0, 0};  // error
    }
    return {offset, need};
}

void RegionPool::Release(size_t offset, size_t size) {
    if (size == 0) return;
    free_.push_back({offset, size});
    Coalesce();
}

void RegionPool::Coalesce() {
    if (free_.size() < 2) return;

    // Sort by offset.
    std::sort(free_.begin(), free_.end(),
              [](const FreeSlot& a, const FreeSlot& b) {
                  return a.offset < b.offset;
              });

    // Merge adjacent.
    size_t wi = 0;
    for (size_t ri = 1; ri < free_.size(); ++ri) {
        auto& prev = free_[wi];
        auto& curr = free_[ri];
        if (prev.offset + prev.size == curr.offset) {
            prev.size += curr.size;
        } else {
            ++wi;
            if (wi != ri) free_[wi] = curr;
        }
    }
    free_.resize(wi + 1);
}
