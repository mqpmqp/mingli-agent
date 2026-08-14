# Hermes handoff: MingLi Core focused rendering

## Stable entry

Use either of these Core-only entry points:

- Python: `mingli.service.analyze_mingli_payload(payload)`
- HTTP: `POST /v1/mingli/analyze`
- MCP: `analyze_mingli` for full birth metadata, with optional `question` and
  `context`.

`final_answer` remains the stable consumer field. The response also includes
`render_intent`, `topic`, `sections`, `full_report_generated`, and `confidence`.

## Rendering contract

```text
DEFAULT_RENDER_INTENT=focused_question
FULL_READING_EXPLICIT_ONLY=true
YUAN_EIGHT_SECTIONS_DEFAULT=false
```

The supported values are `full_reading`, `focused_question`, `follow_up`,
`timing`, `comparison`, `decision`, and `comment`. Any unrecognized request or
classifier failure falls back to `focused_question`; it never falls back to a
full report.

A full report is allowed only for an explicit whole-chart request such as
"完整分析这个命盘", "全盘分析", "给我一份完整命盘报告", or
"按八段报告". Words such as "详细" or "全面" alone do not
activate `full_reading`.

When no question or no usable topic is provided, Core returns one short
clarification instead of an eight-section report. `/new` returns
`conversation_reset: true`, uses `focused_question`, leaves `sections` empty,
and does not analyze the preceding case. Hermes should clear its own
conversation state after receiving that flag.

## Inputs

For a focused direct Hermes call, provide `question`, `gender`, four `pillars`,
and optional `context`:

```json
{
  "question": "她的事业怎么样",
  "gender": "female",
  "pillars": {
    "year": "庚寅",
    "month": "丙戌",
    "day": "戊午",
    "hour": "丙辰"
  },
  "context": {}
}
```

Four-pillar input supports focused/static answers. It does not invent missing
birth date, time, location, or timeline information. For the complete
birth-metadata path, provide `chart_input` with `gender`, `calendar`,
`birth_date`, `birth_time`, `timezone`, `birth_location`, and optional
`true_solar_time`; provide `anchor_year`, `reality`, and `fusion_evidence` as
needed by the existing deterministic contract.

## Response examples

Focused question:

```json
{
  "render_intent": "focused_question",
  "topic": "career",
  "final_answer": "...",
  "sections": [],
  "full_report_generated": false,
  "confidence": "medium"
}
```

Explicit full report with complete birth metadata:

```json
{
  "render_intent": "full_reading",
  "topic": null,
  "final_answer": "...",
  "sections": ["... eight Yuan sections ..."],
  "full_report_generated": true,
  "confidence": "medium"
}
```

Every user-facing `final_answer` contains exactly one disclaimer:

```
仅供文化研究与娱乐参考。
```

## Minimal Python call

```python
from mingli.service import analyze_mingli_payload

result = analyze_mingli_payload(
    {
        "question": "她的事业怎么样",
        "gender": "female",
        "pillars": {
            "year": "庚寅",
            "month": "丙戌",
            "day": "戊午",
            "hour": "丙辰",
        },
        "context": {},
    }
)
print(result["final_answer"])
```

## Responsibility boundary

Hermes receives Telegram messages, reads images, performs OCR/Vision or chart
extraction, manages confirmation/session state, and passes only the confirmed
structured data plus the user question to MingLi Core. MingLi Core does not
download Telegram images, perform OCR or Vision, manage candidate pools or image
confirmation, handle Telegram updates, or read Bot tokens.
