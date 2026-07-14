# V2.0 Release Checklist

- [ ] Clean branch is based on current `origin/main`.
- [ ] `spec/` and `knowledge/` are unchanged.
- [ ] Full unittest and pytest suites pass.
- [ ] P16–P24 independent checks and benchmarks pass.
- [ ] sdist and wheel build successfully.
- [ ] Fresh isolated wheel installation imports from the isolated environment.
- [ ] Source and wheel canonical hashes match.
- [ ] GitHub PR CI passes on the exact head commit.
- [ ] Main push CI passes after merge.
- [ ] Annotated RC tag points to the verified main commit.

RC2 validation closure remains blocked while this item is open:

- [ ] At least 30 consented, de-identified validation cases pass provenance gates, including at least 10 Gold and no more than 20 Silver, with at least 100 comparable claims across at least 3 scenarios.

Complete ChengGu verses are out of RC2 scope. The core package must keep `verse_available=false` and contain no verse text, verse package-data, or modern paraphrase. A future optional verse pack requires a separate review.

Product accuracy claims have a stricter independent gate: at least 30 prospective Gold cases; Silver and Bronze never count.

Technical RC completion does not change `prediction_validity=not_evaluated` and does not authorize an accuracy claim.
