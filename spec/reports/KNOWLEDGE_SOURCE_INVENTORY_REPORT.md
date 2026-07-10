# Knowledge Source Inventory Report

- PDF 文件总数：40
- 重复哈希组：0
- P0/P1 候选来源：5

## 领域分布

- `bazi_yijing_prediction`：2
- `fengshui`：2
- `fengshui_course_navigation`：12
- `non_mingli_business_qa`：22
- `qimen_prediction_history`：1
- `yijing_hexagrams`：1

## 入库决策

- `exclude_no_substantive_content`：12
- `extract_or_ocr_then_review`：1
- `ocr_then_manual_review`：5
- `quarantine_out_of_domain`：22

## 高优先级候选

- **中国风水全书 (邵伟华)(1).pdf** — fengshui，418 页，image_scanned_or_stub，建议 `ocr_then_manual_review`
- **中国风水全书 (邵伟华).pdf** — fengshui，420 页，image_scanned_or_stub，建议 `ocr_then_manual_review`
- **周易与预测学 (邵伟华著).pdf** — bazi_yijing_prediction，439 页，image_scanned_or_stub，建议 `ocr_then_manual_review`
- **周易预测宝典 (邵伟华).pdf** — bazi_yijing_prediction，396 页，limited_text，建议 `extract_or_ocr_then_review`
- **未知之门 邵伟华与周易预测索秘 (张志春).pdf** — qimen_prediction_history，411 页，image_scanned_or_stub，建议 `ocr_then_manual_review`

## 已明确排除或隔离

- `01/11–21` 系列：单页课程二维码或入口，不是知识正文。
- `2019xxxx中危` 系列：内容表现为商业/职场知识星球问答，当前隔离为非命理资料。
- 扫描书籍：未执行全书 OCR，不声称已完成知识吸收。

## 重复文件

- 未发现完全相同的 SHA-256 文件。
