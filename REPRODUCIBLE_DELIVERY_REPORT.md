# Reproducible Delivery Report

## Decision

```text
REPRODUCIBLE_LOCAL_RC2_CANDIDATE_COMPLETE
PRODUCT_RELEASE_HOLD_REMAINS
```

The candidate is reproducible and source-bound. It is not an independently reviewed or remotely approved release artifact.

## Defect found and closed

A raw `python -m build` run with `SOURCE_DATE_EPOCH` produced byte-identical wheels but different sdists. The sdist gzip header and 176 tar members retained build-time metadata. Extracted file contents were identical, proving a container metadata defect rather than source drift.

`scripts/build_reproducible_dist.py` now canonicalizes member order, timestamps, ownership, permissions, PAX metadata, and the gzip header. `scripts/build_astro_etl_toolkit.py` creates a sorted, fixed-timestamp, fixed-permission ZIP with an embedded per-file SHA-256 manifest and rejects unsafe archive paths.

## TDD evidence

| Journey | RED commit | GREEN commit | Coverage |
|---|---|---|---:|
| Identical source produces identical wheel and sdist | `2cec5bb` | `a7bcb0f` | 99% for `build_reproducible_dist.py` |
| Identical inputs produce an identical safe toolkit ZIP | `2e00179` | `06e9af5` | 98% for `build_astro_etl_toolkit.py` |

The tests cover metadata normalization, stable ordering, directory and symlink modes, clean output enforcement, empty-build failure, CLI forwarding, manifest hashing, missing payloads, duplicate names, reserved names, and path traversal rejection.

## Candidate source and hashes

Source commit: `dfc7727701f56abc529cbc4b5fa24ca14159d736`

Source date epoch: `1784121044`

| Artifact | SHA-256 | Bytes |
|---|---|---:|
| `mingli_agent-2.0.0-py3-none-any.whl` | `195D0C6AFCB077902E28FBCB7B538CDD3216E562E22738638B53488EF4ACBD1C` | 299876 |
| `mingli_agent-2.0.0.tar.gz` | `C4E86DA9F7BB8D75250AF85DCAF83FCC6B60725CA77D6D8334E945D699F726E2` | 275748 |
| `real_case_etl_toolkit_hardened_rc2.zip` | `5B4AA93570CCFDC5888B297DE67BE11C2EA87A0A86D4F502EEB32BD5CFB9EC21` | 604253 |

Two detached worktrees at the same commit independently produced the same wheel, sdist, and toolkit hashes. Rebuilding a wheel from the canonical sdist reproduced the wheel hash exactly.

## Installation and integrity evidence

- Wheel ZIP integrity and required module/entry-point membership passed.
- Sdist membership and extraction passed.
- Fresh virtual-environment installation resolved all declared dependencies.
- `pip check` reported no broken requirements.
- `mingli.validation_astro_etl` and `mingli.test_gates` imported from the installed wheel.
- `mingli-validation --help` exited with code 0.
- Toolkit ZIP integrity passed; all 14 payload hashes matched `MANIFEST.json`.
- The embedded manifest records `product_release_status` as `HOLD`.

## Frozen predecessor

The original `real_case_etl_toolkit_hardened.zip` remains unchanged:

```text
681F9467F0568ED64F8C5A5FFEBD2F3D4B033B9A941B4A6A313F0F09C8703233
```

The RC2 uses a separate filename and does not replace the frozen predecessor.
