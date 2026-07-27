# Hermes Image Intake Handoff

Replace the current Telegram image reply that says image-chart OCR is unavailable with a MingLi image-intake request. Do not add OCR implementation to Hermes.

1. Pass `source="telegram"`, an opaque `image_ref`, and `ocr_text` only when Hermes has obtained it from an approved provider.
2. Call `mingli.intake.image_chart.intake_image_chart`.
3. Render `user_message` verbatim for `candidate_requires_confirmation`, `provider_missing`, `not_a_chart`, and `low_confidence`. Store only the candidate needed for the active session; do not log image contents or OCR text.
4. On a user confirmation or correction, call `confirm_image_chart_candidate` with the stored candidate and reply.
5. Only on `confirmed_runtime_ready`, collect or validate the separately required birth date, time, timezone, and location before constructing the existing Phase 23 Runtime input. The returned handoff explicitly says `runtime_dispatch="requires_verified_birth_input"`; it is not itself executable Phase 23 input.

Never call Runtime or produce a MingLi analysis before the user confirms. Do not send full OCR text, full birth data, image content, Runtime analysis body, or provider tokens to logs.
