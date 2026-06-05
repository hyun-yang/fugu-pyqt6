import base64
import logging
import re
import time

from openai import OpenAI
from PyQt6.QtCore import QThread, pyqtSignal

from fugu.util.Constants import Constants

logger = logging.getLogger(__name__)

_MODEL_HINT_PATTERN = re.compile(rb"(claude[-\w.]+|gemini[-\w.]+|gpt[-\w.]+|o\d[-\w.]*)")


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


class EvaluatorOpenAIThread(QThread):
    response_signal = pyqtSignal(str, bool)
    response_finished_signal = pyqtSignal(str, str, float, bool, dict)

    def __init__(self, args):
        super().__init__()
        self.ai_arg = args["ai_arg"]
        self.stream = self.ai_arg["stream"]
        self.user_query = args["user_query"]
        self.max_retries = args["max_retries"]
        self.model = self.ai_arg["model"]

        self.evaluator_prompt = args["evaluator_prompt"]
        self.generator_prompt = args["generator_prompt"]
        self.task_prompt = args["task_prompt"]

        self.fugu = OpenAI(base_url="https://api.sakana.ai/v1", api_key=args["api_key"])
        self.force_stop = False
        self.start_time = None

        # accumulated across the entire loop
        self._usage_acc: dict = {
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
        }
        self._hints_acc: set[str] = set()

    # ---------- accumulation / response-creation helpers ----------

    def _accumulate(self, resp) -> None:
        """Accumulate usage / hints from a single responses-call result."""
        u = _extract_usage(getattr(resp, "usage", None))
        for k in self._usage_acc:
            self._usage_acc[k] += u.get(k, 0)
        for h in _extract_model_hints(resp):
            self._hints_acc.add(h)

    def _build_kwargs(self, messages: list, stream: bool) -> dict:
        kwargs = {
            "model": self.ai_arg["model"],
            "input": messages,  # the responses API uses 'input'
        }
        # Note: fugu-ultra is a reasoning model and may reject temperature.
        if stream:
            kwargs["stream"] = True
        return kwargs

    # ---------- main loop (logic unchanged) ----------

    def run(self):
        self.start_time = time.time()
        try:
            result, _chain_of_thought = self.loop(
                self.task_prompt, self.evaluator_prompt, self.generator_prompt
            )

            if not self.force_stop:
                self.response_signal.emit(result, self.stream)
                self.finish_run(self.model, Constants.FORCE_STOP, self.stream)

        except Exception as e:
            self.response_signal.emit(str(e), self.stream)
            self.finish_run(self.model, Constants.ERROR_STOP, self.stream)

    def loop(
        self, task: str, evaluator_prompt: str, generator_prompt: str
    ) -> tuple[str, list[dict]]:
        memory = []
        chain_of_thought = []
        attempt_count = 0

        thoughts, result = self.generate(generator_prompt, task)
        if self.force_stop:
            self.finish_run(self.model, Constants.FORCE_STOP, self.stream)
            return result, chain_of_thought

        memory.append(result)
        chain_of_thought.append({Constants.THOUGHTS_TAG: thoughts, Constants.RESULT_TAG: result})
        attempt_count += 1

        while not self.force_stop and attempt_count < self.max_retries:
            evaluation, feedback = self.evaluate(evaluator_prompt, result, task)
            if self.force_stop:
                self.finish_run(self.model, Constants.FORCE_STOP, self.stream)
                break

            if evaluation == Constants.EVALUATION_PASS:
                return result, chain_of_thought

            context = "\n".join(
                [
                    Constants.EVALUATION_PREVIOUS_ATTEMPTS,
                    *[f"- {m}" for m in memory],
                    f"\n{Constants.EVALUATION_FEEDBACK}: {feedback}",
                ]
            )

            thoughts, result = self.generate(generator_prompt, task, context)
            if self.force_stop:
                self.finish_run(self.model, Constants.FORCE_STOP, self.stream)
                break

            memory.append(result)
            chain_of_thought.append(
                {Constants.THOUGHTS_TAG: thoughts, Constants.RESULT_TAG: result}
            )

            attempt_count += 1

            retry_info = f"\n[Attempt {attempt_count} of {self.max_retries}]\n"
            self.response_signal.emit(retry_info, self.stream)

        if attempt_count >= self.max_retries and not self.force_stop:
            max_retry_message = (
                f"\n[Maximum retry limit of {self.max_retries} reached. Stopping iterations.]\n"
            )
            self.response_signal.emit(max_retry_message, self.stream)

        return result, chain_of_thought

    # ---------- API call (responses.create-based) ----------

    def get_response(self, prompt: str, system_prompt: str = "") -> str:
        if self.force_stop:
            self.finish_run(self.model, Constants.FORCE_STOP, self.stream)
            return ""

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if self.stream:
            return self.dispatch_response(messages)
        else:
            resp = self.fugu.responses.create(**self._build_kwargs(messages, stream=False))
            self._accumulate(resp)
            return getattr(resp, "output_text", "") or ""

    def dispatch_response(self, messages: list) -> str:
        if self.force_stop:
            self.finish_run(self.model, Constants.FORCE_STOP, self.stream)
            return ""

        stream = self.fugu.responses.create(**self._build_kwargs(messages, stream=True))

        current_model = None
        full_text = ""

        for event in stream:
            if self.force_stop:
                if current_model:
                    self.finish_run(current_model, Constants.FORCE_STOP, self.stream)
                return full_text

            etype = getattr(event, "type", "")
            if etype == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    self.response_signal.emit(delta, self.stream)
                    full_text += delta
            elif etype == "response.completed":
                resp = getattr(event, "response", None)
                if resp is not None:
                    current_model = getattr(resp, "model", None) or current_model
                    self._accumulate(resp)  # accumulate usage / hints from the completed event

        return full_text

    # ---------- XML parsing / generate / evaluate (logic unchanged) ----------

    def extract_xml(self, text: str, tag: str) -> str:
        match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
        return match.group(1).strip() if match else ""

    def generate(self, prompt: str, task: str, context: str = "") -> tuple[str, str]:
        if self.force_stop:
            self.finish_run(self.model, Constants.FORCE_STOP, self.stream)
            return "", ""

        full_prompt = (
            f"{prompt}\n{context}\n{Constants.EVALUATION_TASK} {task}"
            if context
            else f"{prompt}\n{Constants.EVALUATION_TASK} {task}"
        )

        if self.stream:
            generation_header = f"\n{Constants.GENERATION_START}\n"
            self.response_signal.emit(generation_header, self.stream)

        response = self.get_response(full_prompt)
        thoughts = self.extract_xml(response, Constants.THOUGHTS_TAG)
        result = self.extract_xml(response, Constants.RESPONSE_TAG)

        if self.stream:
            generation_info = f"\n{Constants.GENERATION_THOUGHTS}\n{thoughts}\n\n{Constants.GENERATION_GENERATED}\n{result}\n{Constants.GENERATION_END}\n"
        else:
            generation_info = f"\n{Constants.GENERATION_START}\n{Constants.GENERATION_THOUGHTS}\n{thoughts}\n\n{Constants.GENERATION_GENERATED}\n{result}\n{Constants.GENERATION_END}\n"

        self.response_signal.emit(generation_info, self.stream)

        return thoughts, result

    def evaluate(self, prompt: str, content: str, task: str) -> tuple[str, str]:
        if self.force_stop:
            self.finish_run(self.model, Constants.FORCE_STOP, self.stream)
            return "", ""

        full_prompt = (
            f"{prompt}\n{Constants.ORIGINAL_TASK} {task}\n{Constants.CONTENT_TO_EVALUATE} {content}"
        )

        if self.stream:
            evaluation_header = f"{Constants.EVALUATION_START}\n"
            self.response_signal.emit(evaluation_header, self.stream)

        response = self.get_response(full_prompt)
        evaluation = self.extract_xml(response, Constants.EVALUATION_TAG)
        feedback = self.extract_xml(response, Constants.FEEDBACK_TAG)

        if self.stream:
            evaluation_info = f"{Constants.EVALUATION_STATUS_EX} {evaluation}\n{Constants.EVALUATION_FEEDBACK_EX} {feedback}\n{Constants.EVALUATION_END}\n"
        else:
            evaluation_info = f"{Constants.EVALUATION_START}\n{Constants.EVALUATION_STATUS_EX} {evaluation}\n{Constants.EVALUATION_FEEDBACK_EX} {feedback}\n{Constants.EVALUATION_END}\n"

        self.response_signal.emit(evaluation_info, self.stream)

        return evaluation, feedback

    # ---------- common ----------

    def set_force_stop(self, force_stop):
        self.force_stop = force_stop

    def finish_run(self, model, finish_reason, stream):
        elapsed_time = time.time() - self.start_time
        meta = {
            "usage": dict(self._usage_acc),  # total accumulated across the loop
            "hints": sorted(self._hints_acc),
        }
        self.response_finished_signal.emit(
            model or "",
            finish_reason or "",
            elapsed_time,
            stream,
            meta,
        )
