# Provenance

Each adapted file, the staged source it was cut from, and the symbols used.
Sources are identified by their row in the owner's private staging manifest (`_extracted/MANIFEST.tsv`, kept locally and not published):
the `candidate` column and the full `sha256`. That row gives the source path.
Paths and two symbol names are left out here because they contain words this
project must not carry; the sha256 resolves them. Only the named symbols were
used; the rest of each source file was not copied.

| File | MANIFEST candidate | sha256 | Symbols | Changes |
|---|---|---|---|---|
| `docpipe/ingest/hashing.py` | `chunked-sha256` | `A56892AEBDF7EAFFA730BE4232BF4EEF0CE3B5CA67D65EC0067BBC3D9A16B789` | `sha256_of` | Raises `OSError` instead of returning an "unreadable" string. Chunk size is now a parameter and must be positive. Comments rewritten. |
| `docpipe/enrich/normalize.py` | `ascii-fold` | `C33C0F287ED63492B1C588174328CCED00ACD25060565F44968E035ACDDF0410` | `MAX`, `fold` | `MAX` is now `LIMIT`. The signature is now `fold(value, limit=240)`, and the limit is passed to list items. A limit of 3 or less is a hard cut with no "...". Comments rewritten. |
| `docpipe/enrich/shape.py` | `text-shape-knn` | `21F28F9729CD281770FC32A133F29A0BA3C7A3946FA772EB9322861F1A82FD25` | The range `absSig`..`recordAge` (as in the MANIFEST row). | Ported from Go to Python and renamed: `absSig` -> `Signature`, `logKind` -> `Exemplar`, `logRecord` -> `Catalog`, `readLogRec` -> `load_catalog`, the measuring entry point -> `signature`, `profileOf` -> `profile`, `kinFallback` -> `FALLBACK_WEIGHTS`, `kinDistance` -> `distance`, `kinHit` -> `Hit`, the lookup entry point -> `nearest`, `recordAge` -> `age`. `SHOWN` mirrors the hint-count constant just above the range (L86). Caseless letters (category L other than Lu/Ll) get a new `caseless` axis instead of counting as punctuation. Weights come from an optional `load_weights(path=None)`, not a fixed path. Partial weights are filled from the fallback. The catalog path is a parameter. Catalog and weights values must be finite and non-negative, unknown signature keys are rejected, and both files may carry a UTF-8 byte-order mark. Line endings are not counted when measuring. A new `main()` replaces the source's command handler, which was not copied. |
| `docpipe/enrich/shape.py` | `text-shape-knn` (row shared with `load-score`) | `F839DF7AC056FA4FC15FE45CE5B57F3BCCDC2833C5E1D0D795528185A1261E2D` | Axis-name constants, age strings and formats (L202-213, 230-233). The L244 path constant was not copied. | Axis names kept (plus `caseless`). Age wording rewritten. The path became a function parameter. |
| `tests/test_shape.py` | `text-shape-knn` | `EF8D8DAA1324D4127D8255C4DA502945FC9BE1105A9AB70A222649DF87DA2C71` | `TestMissingWeightsFallBackRatherThanZero` | Ported as `test_missing_weights_fall_back_rather_than_zero`. The ranking and absent/corrupt/empty tests were rewritten with neutral fixtures. The input-validation, encoding and missing-input tests are new. |
| `tests/test_hashing.py`, `tests/test_normalize.py` | none | | | New. |
| `README.md`, `docpipe/__init__.py`, `docpipe/*/__init__.py` | none | | | New. |
