import base64
import json
import logging
import re
import time

from openai import OpenAI
from PyQt6.QtCore import QThread, pyqtSignal

from fugu.util.Constants import Constants

logger = logging.getLogger(__name__)


def _summarize(value, max_str: int = 300):
    """Truncate long strings (encrypted_content / output_text, etc.) to keep the console readable."""
    if isinstance(value, str):
        if len(value) > max_str:
            return value[:max_str] + f"… [+{len(value) - max_str} chars]"
        return value
    if isinstance(value, list):
        return [_summarize(v, max_str) for v in value]
    if isinstance(value, dict):
        return {k: _summarize(v, max_str) for k, v in value.items()}
    return value


def _dump_response(resp) -> str:
    """Serialize the full Sakana response shape to JSON. Useful for tracing where worker / reasoning info actually lives."""
    try:
        data = resp.model_dump()
    except Exception:
        try:
            data = json.loads(resp.model_dump_json())
        except Exception:
            return repr(resp)
    return json.dumps(_summarize(data), indent=2, ensure_ascii=False, default=str)


_MODEL_HINT_PATTERN = re.compile(rb"(claude[-\w.]+|gemini[-\w.]+|gpt[-\w.]+|o[134][-.][\w.-]+)")


def _clean_model_name(name: str) -> str:
    """Strip trailing noise from a model name extracted out of encrypted_content.
    Example: 'claude-opus-4-78' -> 'claude-opus-4-7'
    """
    return re.sub(r"(\d)\d$", r"\1", name) if re.search(r"\d\d$", name) else name


def _extract_model_hints(resp) -> list[str]:
    """Scrape model-name fragments out of a responses.create() response's encrypted_content."""
    hints: set[str] = set()
    output = getattr(resp, "output", None) or []
    for item in output:
        if getattr(item, "type", None) != "reasoning":
            continue
        enc = getattr(item, "encrypted_content", None)
        if not enc:
            continue
        try:
            raw = base64.b64decode(enc + "===")
        except Exception:
            continue
        for m in _MODEL_HINT_PATTERN.findall(raw):
            hints.add(_clean_model_name(m.decode("ascii", errors="ignore")))
    return sorted(hints)


def _extract_usage(usage) -> dict:
    """Safely pull input / output / reasoning / total token counts."""
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}

    reasoning_tokens = 0
    details = getattr(usage, "output_tokens_details", None)
    if details is not None:
        reasoning_tokens = getattr(details, "reasoning_tokens", 0) or 0

    return {
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }


class SakanaAIThread(QThread):
    response_signal = pyqtSignal(str, bool)
    response_finished_signal = pyqtSignal(str, str, float, bool, dict)

    def __init__(self, args):
        super().__init__()
        self.ai_arg = dict(args["ai_arg"])
        self.fugu = OpenAI(base_url="https://api.sakana.ai/v1", api_key=args["api_key"])
        self.stream = self.ai_arg.get("stream", False)
        self.force_stop = False
        self.start_time = None

        self._last_usage: dict = {}
        self._last_hints: list[str] = []

    def run(self):
        self.start_time = time.time()
        try:
            kwargs = dict(self.ai_arg)
            # the responses API uses 'input' instead of 'messages'
            if "messages" in kwargs and "input" not in kwargs:
                kwargs["input"] = kwargs.pop("messages")

            if self.stream:
                stream = self.fugu.responses.create(**kwargs)
                self._handle_stream(stream)
            else:
                resp = self.fugu.responses.create(**kwargs)
                self._handle_response(resp)
        except Exception as e:
            self.response_signal.emit(str(e), self.stream)
            self.finish_run("", f"error: {e}", self.stream)

    def _handle_response(self, resp):
        if self.force_stop:
            self.finish_run(resp.model, Constants.FORCE_STOP, self.stream)
            return
        logger.info("Sakana non-stream response dump:\n%s", _dump_response(resp))
        text = getattr(resp, "output_text", "") or ""
        self.response_signal.emit(text, self.stream)
        self._last_usage = _extract_usage(getattr(resp, "usage", None))
        self._last_hints = _extract_model_hints(resp)
        self.finish_run(resp.model, "stop", self.stream)

    def _handle_stream(self, stream):
        last_model = ""
        for event in stream:
            if self.force_stop:
                self.finish_run(last_model, Constants.FORCE_STOP, self.stream)
                return

            etype = getattr(event, "type", "")
            if etype == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    self.response_signal.emit(delta, self.stream)
            elif etype == "response.completed":
                resp = getattr(event, "response", None)
                if resp is not None:
                    logger.info("Sakana stream response.completed dump:\n%s", _dump_response(resp))
                    last_model = getattr(resp, "model", "") or last_model
                    self._last_usage = _extract_usage(getattr(resp, "usage", None))
                    self._last_hints = _extract_model_hints(resp)

        self.finish_run(last_model, "stop", self.stream)

    def set_force_stop(self, force_stop):
        self.force_stop = force_stop

    def finish_run(self, model, finish_reason, stream):
        elapsed_time = time.time() - self.start_time
        meta = {
            "usage": self._last_usage or {},
            "hints": self._last_hints or [],
        }
        self.response_finished_signal.emit(
            model or "",
            finish_reason or "",
            elapsed_time,
            stream,
            meta,
        )
