//! Resource exhaustion (contract §5: exit 1, nothing published).
//!
//! Every allocation sized by the input goes through `common::alloc` and its siblings,
//! which fail as an ordinary IO_MEMORY `Fail` (exit 1). What stable Rust cannot make fallible (small
//! strings, decoder state, the error path itself) is covered here: the process
//! allocator wraps the system allocator, and a request of at most `SMALL` bytes that
//! the system refuses is served from a fixed `RESERVE` while the exhaustion is latched.
//! The run then fails at its next `common::checkpoint()`, and always at the one just
//! before publication, through the same error propagation and cleanup as any other
//! failure. Nothing here decides an output byte.
//!
//! Residual, stated rather than hidden: a refused request larger than `SMALL`, or one
//! that a spent reserve cannot hold, still ends as std defines (abort). Neither is
//! reachable from an input-sized allocation, which all go through `common`.

use std::alloc::{GlobalAlloc, Layout};
use std::cell::UnsafeCell;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

pub const RESERVE: usize = 1 << 20;
pub const SMALL: usize = 64 << 10;

#[repr(C, align(4096))]
struct Arena(UnsafeCell<[u8; RESERVE]>);

/// The process allocator: `A` (the system allocator, or the test build's capped one)
/// with the reserve behind it.
pub struct Reserve<A> {
    inner: A,
    arena: Arena,
    used: AtomicUsize,
    exhausted: AtomicBool,
}

// Disjoint arena ranges are handed out by the atomic bump below and never reused.
unsafe impl<A: Sync> Sync for Reserve<A> {}

#[cfg(not(feature = "observe"))]
#[global_allocator]
pub static HEAP: Reserve<std::alloc::System> = Reserve::new(std::alloc::System);
#[cfg(feature = "observe")]
#[global_allocator]
pub static HEAP: Reserve<crate::observe::CapAlloc> = Reserve::new(crate::observe::CapAlloc);

/// Whether the system has refused an allocation during this run.
pub fn exhausted() -> bool {
    HEAP.exhausted.load(Ordering::SeqCst)
}

impl<A> Reserve<A> {
    pub const fn new(inner: A) -> Self {
        Reserve {
            inner,
            arena: Arena(UnsafeCell::new([0; RESERVE])),
            used: AtomicUsize::new(0),
            exhausted: AtomicBool::new(false),
        }
    }

    fn base(&self) -> usize {
        self.arena.0.get() as usize
    }

    fn in_arena(&self, p: *mut u8) -> bool {
        let a = p as usize;
        a >= self.base() && a < self.base() + RESERVE
    }

    /// A refused request: latch the exhaustion, then serve it from the reserve if it
    /// is small and fits. Null otherwise.
    fn from_reserve(&self, l: Layout) -> *mut u8 {
        self.exhausted.store(true, Ordering::SeqCst);
        if l.size() > SMALL {
            return std::ptr::null_mut();
        }
        let base = self.base();
        let mut cur = self.used.load(Ordering::SeqCst);
        loop {
            let start = (base + cur).next_multiple_of(l.align()) - base;
            let end = match start.checked_add(l.size()) {
                Some(e) if e <= RESERVE => e,
                _ => return std::ptr::null_mut(),
            };
            match self.used.compare_exchange_weak(cur, end, Ordering::SeqCst, Ordering::SeqCst) {
                Ok(_) => return (base + start) as *mut u8,
                Err(c) => cur = c,
            }
        }
    }
}

unsafe impl<A: GlobalAlloc> GlobalAlloc for Reserve<A> {
    unsafe fn alloc(&self, l: Layout) -> *mut u8 {
        let p = unsafe { self.inner.alloc(l) };
        if p.is_null() { self.from_reserve(l) } else { p }
    }

    unsafe fn alloc_zeroed(&self, l: Layout) -> *mut u8 {
        let p = unsafe { self.inner.alloc_zeroed(l) };
        if !p.is_null() {
            return p;
        }
        let q = self.from_reserve(l);
        if !q.is_null() {
            unsafe { std::ptr::write_bytes(q, 0, l.size()) };
        }
        q
    }

    unsafe fn dealloc(&self, p: *mut u8, l: Layout) {
        if !self.in_arena(p) {
            unsafe { self.inner.dealloc(p, l) }
        }
    }

    unsafe fn realloc(&self, p: *mut u8, l: Layout, n: usize) -> *mut u8 {
        let nl = unsafe { Layout::from_size_align_unchecked(n, l.align()) };
        if self.in_arena(p) {
            let q = unsafe { self.alloc(nl) };
            if !q.is_null() {
                unsafe { std::ptr::copy_nonoverlapping(p, q, l.size().min(n)) };
            }
            return q;
        }
        let q = unsafe { self.inner.realloc(p, l, n) };
        if !q.is_null() {
            return q;
        }
        let q = self.from_reserve(nl);
        if !q.is_null() {
            unsafe {
                std::ptr::copy_nonoverlapping(p, q, l.size().min(n));
                self.inner.dealloc(p, l);
            }
        }
        q
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// An inner allocator that refuses everything, so every request meets the reserve.
    struct Refuse;
    unsafe impl GlobalAlloc for Refuse {
        unsafe fn alloc(&self, _l: Layout) -> *mut u8 {
            std::ptr::null_mut()
        }
        unsafe fn dealloc(&self, _p: *mut u8, _l: Layout) {}
    }

    static A: Reserve<Refuse> = Reserve::new(Refuse);

    #[test]
    fn reserve_serves_small_refuses_large_and_latches() {
        let a = &A;
        assert!(!a.exhausted.load(Ordering::SeqCst));
        unsafe {
            let p = a.alloc(Layout::from_size_align(100, 8).unwrap());
            assert!(!p.is_null() && a.in_arena(p) && p as usize % 8 == 0);
            assert!(a.exhausted.load(Ordering::SeqCst) && !exhausted());
            assert!(a.alloc(Layout::from_size_align(SMALL + 1, 8).unwrap()).is_null());
            let z = a.alloc_zeroed(Layout::from_size_align(64, 64).unwrap());
            assert!(!z.is_null() && z as usize % 64 == 0 && std::slice::from_raw_parts(z, 64).iter().all(|&b| b == 0));
            *p = 7;
            let q = a.realloc(p, Layout::from_size_align(100, 8).unwrap(), 200);
            assert!(!q.is_null() && *q == 7);
            a.dealloc(q, Layout::from_size_align(200, 8).unwrap());
        }
    }
}
