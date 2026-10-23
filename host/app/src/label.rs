//! APP-1 §2 label: UTF-8, 1–32 bytes, as `tapectl provision --label` requires. Input that
//! would exceed 32 bytes is not accepted (the previous label stands); nothing is ever
//! truncated, and the box is never pre-filled.

pub const MAX_BYTES: usize = 32;

/// Whether `proposed` may replace the current label text in the box.
pub fn accept(proposed: &str) -> bool {
    proposed.len() <= MAX_BYTES && !proposed.contains('\0')
}

/// Whether the label is usable for Make cartridge.
pub fn complete(label: &str) -> bool {
    !label.is_empty() && accept(label)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn byte_limit_not_char_limit() {
        assert!(accept(&"a".repeat(32)));
        assert!(!accept(&"a".repeat(33)));
        assert!(accept(&"é".repeat(16))); // 32 bytes
        assert!(!accept(&"é".repeat(17))); // 34 bytes: refused, never truncated
        assert!(!complete(""));
        assert!(!accept("a\0b"));
    }
}
