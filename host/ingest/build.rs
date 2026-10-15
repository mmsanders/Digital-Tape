//! Embed the identity of every library that decides output bytes: the Cargo.lock checksum
//! of a crates.io package, or a SHA-256 over the vendored (patched) crate tree.

use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};

const VENDORED: [&str; 4] = ["symphonia-bundle-mp3", "symphonia-codec-aac", "symphonia-common", "symphonia-core"];
const REGISTRY: [&str; 5] = ["libm", "md-5", "sha2", "symphonia-metadata", "unicode-normalization"];

fn files(dir: &Path, root: &Path, out: &mut Vec<PathBuf>) {
    for e in fs::read_dir(dir).unwrap() {
        let p = e.unwrap().path();
        if p.is_dir() {
            files(&p, root, out);
        } else {
            out.push(p.strip_prefix(root).unwrap().to_path_buf());
        }
    }
}

/// SHA-256 over (relative '/' path, NUL, u64-LE length, bytes) for every file, sorted.
fn tree_sha256(root: &Path) -> String {
    let mut list = Vec::new();
    files(root, root, &mut list);
    let mut rel: Vec<(String, PathBuf)> = list
        .into_iter()
        .map(|p| (p.components().map(|c| c.as_os_str().to_str().unwrap().to_string()).collect::<Vec<_>>().join("/"), p))
        .collect();
    rel.sort();
    let mut h = Sha256::new();
    for (name, p) in rel {
        let b = fs::read(root.join(p)).unwrap();
        h.update(name.as_bytes());
        h.update([0u8]);
        h.update((b.len() as u64).to_le_bytes());
        h.update(&b);
    }
    h.finalize().iter().map(|b| format!("{b:02x}")).collect()
}

fn main() {
    let lock = fs::read_to_string("Cargo.lock").expect("Cargo.lock is committed and required");
    let mut rows = Vec::new();
    let mut pkgs: Vec<(String, String, Option<String>)> = Vec::new();
    for block in lock.split("[[package]]").skip(1) {
        let field = |k: &str| {
            block.lines().find_map(|l| l.strip_prefix(&format!("{k} = \"")).map(|v| v.trim_end_matches('"').to_string()))
        };
        pkgs.push((field("name").unwrap(), field("version").unwrap(), field("checksum")));
    }
    let find = |n: &str| {
        let v: Vec<_> = pkgs.iter().filter(|p| p.0 == n).collect();
        assert_eq!(v.len(), 1, "exactly one {n} in Cargo.lock");
        v[0].clone()
    };
    for n in VENDORED {
        let (_, ver, sum) = find(n);
        assert!(sum.is_none(), "{n} must resolve to the vendored path");
        let root = Path::new("vendor").join(n);
        println!("cargo:rerun-if-changed={}", root.display());
        rows.push((n.to_string(), ver, "vendored-patched", tree_sha256(&root)));
    }
    for n in REGISTRY {
        let (_, ver, sum) = find(n);
        rows.push((n.to_string(), ver, "crates.io", sum.expect("registry checksum")));
    }
    rows.sort();
    let mut src = String::from("pub const LIBRARIES: &[(&str, &str, &str, &str)] = &[\n");
    for (n, v, k, s) in rows {
        src.push_str(&format!("    ({n:?}, {v:?}, {k:?}, {s:?}),\n"));
    }
    src.push_str("];\n");
    let out = PathBuf::from(std::env::var("OUT_DIR").unwrap()).join("libraries.rs");
    fs::write(out, src).unwrap();
    println!("cargo:rerun-if-changed=Cargo.lock");
    println!("cargo:rerun-if-changed=build.rs");
}
