# V2.0 Release Checklist

- [x] Independent clean worktree was created from the exact PR head and reviewed against `origin/main`.
- [x] `spec/` and `knowledge/` are unchanged.
- [x] Full unittest and pytest suites pass.
- [x] P12–P24 independent checks and benchmarks pass in source and wheel environments.
- [x] sdist and wheel build successfully.
- [x] Fresh isolated wheel installation imports from the isolated environment.
- [x] Source and wheel canonical hashes match.
- [ ] GitHub PR CI passes on the exact head commit.
- [ ] Main push CI passes after merge.
- [ ] Annotated RC tag points to the verified main commit.

V2 product validation closure remains blocked while this item is open:

- [ ] At least 30 consented, de-identified validation cases pass provenance gates, including at least 10 Gold and no more than 20 Silver, with at least 100 comparable claims across at least 3 scenarios.

Complete ChengGu verses are out of V2.0 scope. The core package must keep `verse_available=false` and contain no verse text, verse package-data, or modern paraphrase. A future optional verse pack requires a separate review.

Product accuracy claims have a stricter independent gate: at least 30 prospective Gold cases; Silver and Bronze never count.

Technical RC completion does not change `prediction_validity=not_evaluated` and does not authorize an accuracy claim.
