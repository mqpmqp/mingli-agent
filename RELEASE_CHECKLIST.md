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

Product release remains blocked while either item is open:

- [ ] Complete ChengGu verses have traceable sources and authorization approval.
- [ ] At least 30 consented, de-identified, externally observed real cases pass provenance gates.

Technical RC completion does not change `prediction_validity=not_evaluated` and does not authorize an accuracy claim.
