"""Minimal, fail-closed Telegram bridge for mobile training captures."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .contracts import canonical_json
from .validation_privacy import scan_for_pii


def _api(token: str, method: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=body,
        headers={"content-type": "application/json"} if body else {},
        method="POST" if body else "GET",
    )
    with urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Telegram API request failed")
    return result


def _capture_path(root: Path, capture_id: str) -> Path:
    return root / "telegram_captures" / f"{hashlib.sha256(capture_id.encode()).hexdigest()}.json"


def _write_capture(root: Path, capture: dict[str, object]) -> None:
    target = _capture_path(root, str(capture["capture_id"]))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(canonical_json(capture) + "\n", encoding="utf-8")
    temporary.replace(target)


def _authorized_chat(update: dict[str, object], allowed: str) -> bool:
    message = update.get("message")
    if not isinstance(message, dict):
        callback = update.get("callback_query")
        message = callback.get("message") if isinstance(callback, dict) else None
    chat = message.get("chat") if isinstance(message, dict) else None
    return isinstance(chat, dict) and str(chat.get("id")) == allowed


def _chat_id(update: dict[str, object]) -> str:
    message = update.get("message")
    if not isinstance(message, dict):
        callback = update.get("callback_query")
        message = callback.get("message") if isinstance(callback, dict) else None
    chat = message.get("chat") if isinstance(message, dict) else None
    return str(chat.get("id")) if isinstance(chat, dict) else ""


def _message_text(update: dict[str, object]) -> str:
    message = update.get("message")
    if not isinstance(message, dict):
        return ""
    return str(message.get("text") or message.get("caption") or "").strip()


def _button(capture_id: str) -> dict[str, object]:
    return {"inline_keyboard": [[
        {"text": "纳入训练", "callback_data": f"accept:{capture_id}"},
        {"text": "暂不纳入", "callback_data": f"defer:{capture_id}"},
    ]]}


def handle_update(update: dict[str, object], *, root: Path, allowed_chat_id: str) -> None:
    if not _authorized_chat(update, allowed_chat_id):
        return
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        data = str(callback.get("data") or "")
        action, _, capture_id = data.partition(":")
        path = _capture_path(root, capture_id)
        if not path.is_file():
            return
        capture = json.loads(path.read_text(encoding="utf-8"))
        capture["training_status"] = "accepted" if action == "accept" else "deferred"
        capture["decision_at"] = datetime.now(timezone.utc).isoformat()
        _write_capture(root, capture)
        _api(str(os.environ["TELEGRAM_BOT_TOKEN"]), "answerCallbackQuery", {"callback_query_id": callback.get("id"), "text": "已记录"})
        return

    text = _message_text(update)
    if not text or text.startswith("/start"):
        _api(str(os.environ["TELEGRAM_BOT_TOKEN"]), "sendMessage", {"chat_id": _chat_id(update), "text": "请转发命理分析文本；我会先脱敏检查，再由你选择是否纳入训练。"})
        return
    findings = scan_for_pii({"text": text})
    if findings:
        _api(str(os.environ["TELEGRAM_BOT_TOKEN"]), "sendMessage", {"chat_id": _chat_id(update), "text": "检测到未脱敏身份信息，未保存。请先删除姓名、电话、地址等信息后重试。"})
        return
    capture_id = "telegram-" + hashlib.sha256((text + str(update.get("update_id"))).encode("utf-8")).hexdigest()[:32]
    capture = {
        "record_type": "MingLiTelegramTrainingCapture",
        "capture_id": capture_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": "telegram_forward",
        "training_status": "pending_user_confirmation",
        "prediction_validity": "not_evaluated",
        "text": text,
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    _write_capture(root, capture)
    _api(str(os.environ["TELEGRAM_BOT_TOKEN"]), "sendMessage", {"chat_id": _chat_id(update), "text": "已完成脱敏检查。是否纳入训练捕获库？", "reply_markup": _button(capture_id)})


def run() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    allowed = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID", "").strip()
    store = os.environ.get("MINGLI_TRAINING_STORE", "").strip()
    if not token or not allowed or not store:
        raise SystemExit("TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_ID and MINGLI_TRAINING_STORE are required")
    root = Path(store)
    offset = 0
    while True:
        result = _api(token, "getUpdates", {"timeout": 25, "offset": offset, "allowed_updates": ["message", "callback_query"]})
        updates = result.get("result", [])
        if not isinstance(updates, list):
            continue
        for update in updates:
            if isinstance(update, dict):
                offset = max(offset, int(update.get("update_id", 0)) + 1)
                handle_update(update, root=root, allowed_chat_id=allowed)


if __name__ == "__main__":
    run()
