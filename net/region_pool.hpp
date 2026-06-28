#pragma once
#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

// ── RegionPool ──
//
// Worker-level large memory pool.  Pre-allocates a 256 MB virtual
// region via mmap.  Sessions acquire/release variable-size sub-regions.
// Acquire is first-fit through a freelist, fallback to bump.
//
// Thread-compatible (not safe): one RegionPool per worker thread.
//
class RegionPool {
public:
    static constexpr size_t kPoolSize  = 256UL * 1024 * 1024; // 256 MB
    static constexpr size_t kMinRegion = 4096;

    RegionPool();
    ~RegionPool();

    RegionPool(const RegionPool&) = delete;
    RegionPool& operator=(const RegionPool&) = delete;

    /// Acquire a region of at least @a min_size bytes.
    /// Returns {offset_in_pool, actual_capacity}.
    std::pair<size_t, size_t> Acquire(size_t min_size);

    /// Return a region to the pool.
    void Release(size_t offset, size_t size);

    char* Base() const { return base_; }

private:
    char* base_;
    size_t bump_offset_ = 0;

    struct FreeSlot {
        size_t offset;
        size_t size;
    };
    std::vector<FreeSlot> free_;

    /// Coalesce adjacent free slots (called after each Release).
    void Coalesce();
};
