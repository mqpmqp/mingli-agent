# MingLi Image Chart Intake v1.1

Image input is untrusted. MingLi accepts only an image reference plus optional text extracted by an approved upstream OCR or vision provider. This repository does not contain an OCR or vision provider and never claims to recognize an image by itself.

`intake_image_chart` deterministically validates visible heavenly-stem/earthly-branch pairs and returns a candidate only when all four pillars are valid. It returns `provider_missing`, `not_a_chart`, or `low_confidence` otherwise. The candidate is shown to the user and always requires explicit confirmation. A correction creates a new candidate and requires confirmation again.

No analysis and no Phase 23 call occurs during image intake or confirmation. A confirmed candidate produces a `mingli-image-chart-confirmation@1.1` handoff only. Phase 23 still requires independently verified birth date, time, timezone, and location; four pillars extracted from an image must not be converted or inferred as those inputs.

The module has no logging. Callers must not log image bytes, image content, full OCR text, complete birth data, Runtime output body, or provider tokens. User-facing messages contain only the selected candidate pillars needed for confirmation, not the original OCR text or parsed birth date/time.

Hermes should call this contract after receiving Telegram image metadata. It must present the returned message, preserve the candidate only in the user session, and call confirmation only after a user reply. It must not deploy, invoke Runtime, or generate a reading before confirmation.
