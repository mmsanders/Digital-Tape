# Format / duplicate product adapter — #156

Mechanical product binding for the independently published
`tests/format_dup_draft8` refusal tranche.

The product slice is intentionally narrow. `tape_format` implements only the
ordered read-only / geometry refusal boundary, and `tape_dup` implements only
the ordered alias / destination-writability / geometry / Side-A-capacity
boundary. Passing all those checks reaches an explicit zero-write coverage hold;
raw-superblock classification and destructive success construction are not
claimed by this issue.

The already-integrated authoritative `tape_promote` implementation supplies
the package's `PROMOTE-EMPTY` case.

Run:

    make -C engine all
    make -C tests/format_dup_adapter all
    tests/format_dup_adapter/build/wp_fmt_dup_probe --selfcheck-callback-trace
    python3 tests/format_dup_adapter/run_product.py \
      --evidence tests/format_dup_adapter/evidence/p1-r25-product

The callback self-check deliberately makes rejected out-of-range read/write
calls and proves the observer retains them. The package runner then applies the
unchanged verifier oracle to all 17 cases and retains hash-bound evidence.

A green run is Software product observation evidence for independent
Verification disposition, not package/source/golden acceptance.
