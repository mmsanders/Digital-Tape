//! Canonical JSON (contract §6): UTF-8, keys sorted lexicographically by UTF-8 bytes, no
//! insignificant whitespace, final LF. Strings escape only `"`, `\` and U+0000–U+001F
//! (as `\u00XX`, lowercase hex); every other scalar is emitted as raw UTF-8.

use crate::common::{put, Res};
use std::collections::BTreeMap;

pub enum J {
    Null,
    Bool(bool),
    Int(u64),
    Str(String),
    Arr(Vec<J>),
    Obj(BTreeMap<String, J>),
}

impl J {
    pub fn obj<const N: usize>(pairs: [(&str, J); N]) -> J {
        J::Obj(pairs.into_iter().map(|(k, v)| (k.to_string(), v)).collect())
    }
    pub fn s(v: impl Into<String>) -> J {
        J::Str(v.into())
    }
    pub fn opt_s(v: Option<&str>) -> J {
        v.map(J::s).unwrap_or(J::Null)
    }
    /// Fixed six-decimal string, round-half-even on the exact binary value, -0 → 0.
    pub fn dec(v: f64) -> J {
        J::Str(dec6(v))
    }
    pub fn opt_dec(v: Option<f64>) -> J {
        v.map(J::dec).unwrap_or(J::Null)
    }

    fn write(&self, o: &mut String) -> Res<()> {
        match self {
            J::Null => put(o, "null")?,
            J::Bool(b) => put(o, if *b { "true" } else { "false" })?,
            J::Int(i) => put(o, &i.to_string())?,
            J::Str(s) => {
                put(o, "\"")?;
                for c in s.chars() {
                    match c {
                        '"' => put(o, "\\\"")?,
                        '\\' => put(o, "\\\\")?,
                        c if (c as u32) < 0x20 => put(o, &format!("\\u{:04x}", c as u32))?,
                        c => put(o, c.encode_utf8(&mut [0; 4]))?,
                    }
                }
                put(o, "\"")?;
            }
            J::Arr(a) => {
                put(o, "[")?;
                for (i, v) in a.iter().enumerate() {
                    if i > 0 {
                        put(o, ",")?;
                    }
                    v.write(o)?;
                }
                put(o, "]")?;
            }
            J::Obj(m) => {
                // BTreeMap<String> orders by UTF-8 bytes.
                put(o, "{")?;
                for (i, (k, v)) in m.iter().enumerate() {
                    if i > 0 {
                        put(o, ",")?;
                    }
                    J::Str(k.clone()).write(o)?;
                    put(o, ":")?;
                    v.write(o)?;
                }
                put(o, "}")?;
            }
        }
        Ok(())
    }

    pub fn canonical(&self) -> Res<String> {
        let mut s = String::new();
        self.write(&mut s)?;
        put(&mut s, "\n")?;
        Ok(s)
    }
}

/// Rust's fixed-precision float formatting is exact-decimal with ties-to-even.
pub fn dec6(v: f64) -> String {
    let s = format!("{v:.6}");
    if s == "-0.000000" { "0.000000".into() } else { s }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn six_decimals() {
        assert_eq!(dec6(-0.0), "0.000000");
        assert_eq!(dec6(-0.0000001), "0.000000");
        assert_eq!(dec6(1.5), "1.500000");
        // 0.0000005 is not exactly representable; exact value decides.
        assert_eq!(dec6(0.0000005), format!("{:.6}", 0.0000005f64));
        // exact tie: 2^-7 = 0.0078125 → half-even at 6 decimals → 0.007812
        assert_eq!(dec6(0.0078125), "0.007812");
        assert_eq!(dec6(0.0234375), "0.023438"); // 3/128 tie rounds to even 8
    }
    #[test]
    fn ordering_and_escape() {
        let j = J::obj([("b", J::Int(1)), ("a", J::s("x\"\n")), ("A", J::Null)]);
        assert_eq!(j.canonical().unwrap(), "{\"A\":null,\"a\":\"x\\\"\\u000a\",\"b\":1}\n");
    }
}
