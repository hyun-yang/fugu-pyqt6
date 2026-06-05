import asyncio
import base64
import json
import re
import time

from openai import AsyncOpenAI
from PyQt6.QtCore import QThread, pyqtSignal

from fugu.util.Constants import Constants

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


class OrchestratorOpenAIThread(QThread):
    response_signal = pyqtSignal(str, bool)
    response_finished_signal = pyqtSignal(str, str, float, bool, dict)

    def __init__(self, args):
        super().__init__()
        self.ai_arg = args["ai_arg"]
        self.stream = self.ai_arg["stream"]
        self.user_query = args["user_query"]

        self.orchestrator_prompt = args["orchestrator_prompt"]
        self.worker_prompt = args["worker_prompt"]
        self.aggregator_prompt = args["aggregator_prompt"]

        self.async_fugu = AsyncOpenAI(api_key=args["api_key"])
        self.force_stop = False
        self.start_time = None

        # accumulated across orchestrator + all worker + aggregator calls
        self._usage_acc: dict = {
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
        }
        self._hints_acc: set[str] = set()

    # ---------- accumulation / kwargs-conversion helpers ----------

    def _accumulate(self, resp) -> None:
        """Single-thread event loop with synchronous updates, so no lock is needed."""
        u = _extract_usage(getattr(resp, "usage", None))
        for k in self._usage_acc:
            self._usage_acc[k] += u.get(k, 0)
        for h in _extract_model_hints(resp):
            self._hints_acc.add(h)

    def _build_kwargs(self, ai_arg: dict, stream: bool) -> dict:
        src = ai_arg.copy()
        kwargs = {"model": src["model"]}

        # messages → input (responses API)
        if "messages" in src:
            kwargs["input"] = src["messages"]
        elif "input" in src:
            kwargs["input"] = src["input"]

        # max_tokens -> max_output_tokens (default to a generous value to avoid truncation)
        kwargs["max_output_tokens"] = src.get("max_tokens") or 32000

        # Note: if fugu-ultra rejects temperature, remove the block below.
        temperature = src.get("temperature")
        if temperature is not None:
            kwargs["temperature"] = temperature

        if stream:
            kwargs["stream"] = True
        return kwargs

    # ---------- entry point ----------

    def run(self):
        self.start_time = time.time()
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._async_run())
        except Exception as e:
            self.response_signal.emit(f"{Constants.ERROR_STOP} : {e!s}", self.stream)
            self.finish_run(self.ai_arg["model"], Constants.ERROR_STOP, self.stream)
        finally:
            if loop is not None and loop.is_running():
                loop.close()

    async def _async_run(self):
        try:
            # Orchestrator response
            if self.stream:
                self.response_signal.emit(Constants.ORCHESTRATOR_ANALYSIS_TASK, self.stream)
                response_stream = await self.get_response(self.ai_arg)
                full_response_stream = await self.dispatch_response_with_header(
                    response_stream, self.stream, Constants.ORCHESTRATOR_ANALYSIS
                )
                clean_result = self._clean_json_string(full_response_stream)
            else:
                response = await self.get_async_response(self.ai_arg)
                full_response_not_stream = response.output_text or ""
                clean_result = self._clean_json_string(full_response_not_stream)

            try:
                response_json = json.loads(clean_result)
                tasks = response_json.get("tasks", [])
                print(f"Tasks count: {len(tasks)}")

                worker_prompts = []
                for i, task in enumerate(tasks):
                    prompt = self.get_worker_prompt(
                        self.user_query, task["task"], task["description"]
                    )
                    worker_prompts.append(prompt)
                    print(f"Task {i + 1} prompt generation completed")

                # Worker response
                if self.stream:
                    self.response_signal.emit(Constants.ORCHESTRATOR_EXECUTING_TASKS, self.stream)
                    worker_responses = await self.run_llm_sequential_stream(
                        worker_prompts, tasks, self.ai_arg
                    )
                else:
                    print("Parallel LLM calls start")
                    worker_responses = await self.run_llm_parallel(worker_prompts, self.ai_arg)
                    print("Parallel LLM calls completed")

                # Aggregator response
                if self.stream:
                    self.response_signal.emit(
                        Constants.ORCHESTRATOR_GENERATING_FINAL_RESULTS, self.stream
                    )
                    aggregator_prompt = self.get_aggregator_prompt(self.user_query)
                    for i in range(len(worker_responses)):
                        aggregator_prompt += f"\n{i + 1}. {Constants.ORCHESTRATOR_TASK_QUESTION} {tasks[i]['task']}\n"
                        aggregator_prompt += (
                            f"\n{Constants.ORCHESTRATOR_RESPONSE} {worker_responses[i]}\n\n"
                        )

                    messages = [{"role": "user", "content": aggregator_prompt}]
                    ai_args = self.ai_arg.copy()
                    ai_args["messages"] = messages
                    final_response = await self.get_response(ai_args)
                    final_full_response = await self.dispatch_response_with_header(
                        final_response, self.stream, Constants.ORCHESTRATOR_FINAL_ANSWER
                    )
                    print(f"\n\n{final_full_response}")

                    self.finish_run(self.ai_arg["model"], Constants.NORMAL_STOP, self.stream)
                else:
                    aggregator_prompt = self.get_aggregator_prompt(self.user_query)
                    for i in range(len(worker_responses)):
                        aggregator_prompt += f"\n{i + 1}. {Constants.ORCHESTRATOR_TASK_QUESTION} {tasks[i]['task']}\n"
                        aggregator_prompt += (
                            f"\n{Constants.ORCHESTRATOR_RESPONSE} {worker_responses[i]}\n\n"
                        )

                    messages = [{"role": "user", "content": aggregator_prompt}]
                    ai_args = self.ai_arg.copy()
                    ai_args["messages"] = messages
                    final_response = await self.get_async_response(ai_args)
                    final_full_response = final_response.output_text or ""

                    combined_result = "\n\n".join(
                        [full_response_not_stream, *worker_responses, final_full_response]
                    )
                    self.response_signal.emit(combined_result, self.stream)
                    self.finish_run(self.ai_arg["model"], Constants.NORMAL_STOP, self.stream)

            except json.JSONDecodeError as je:
                self.response_signal.emit(
                    f"{Constants.ORCHESTRATOR_JSON_PARSING_ERROR} {je}\n{Constants.ORCHESTRATOR_ORIGINAL_RESPONSE} {clean_result}",
                    self.stream,
                )
                self.finish_run(self.ai_arg["model"], Constants.ERROR_STOP, self.stream)

        except Exception as e:
            self.response_signal.emit(
                f"{Constants.ORCHESTRATOR_ERROR_PROCESSING} {e!s}", self.stream
            )
            self.finish_run(self.ai_arg["model"], Constants.ERROR_STOP, self.stream)

    # ---------- API call (responses.create-based) ----------

    async def get_response(self, openai_arg):
        """Return a streaming response object."""
        kwargs = self._build_kwargs(openai_arg, stream=True)
        stream = await self.async_fugu.responses.create(**kwargs)
        return stream

    async def get_async_response(self, openai_arg):
        """Return a non-streaming response object (caller uses .output_text)."""
        kwargs = self._build_kwargs(openai_arg, stream=False)
        resp = await self.async_fugu.responses.create(**kwargs)
        self._accumulate(resp)
        return resp

    async def dispatch_response_with_header(self, response, stream, header_text):
        full_content = ""
        async for event in response:
            if self.force_stop:
                break
            etype = getattr(event, "type", "")
            if etype == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    full_content += delta
                    self.response_signal.emit(delta, stream)
            elif etype == "response.completed":
                resp = getattr(event, "response", None)
                if resp is not None:
                    self._accumulate(resp)

        self.response_signal.emit(
            f"\n--- {header_text} {Constants.ORCHESTRATOR_COMPLETED} ---\n\n", stream
        )
        return full_content

    async def dispatch_response(self, response, stream):
        full_content = ""
        async for event in response:
            if self.force_stop:
                break
            etype = getattr(event, "type", "")
            if etype == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    full_content += delta
                    self.response_signal.emit(delta, stream)
            elif etype == "response.completed":
                resp = getattr(event, "response", None)
                if resp is not None:
                    self._accumulate(resp)

        return full_content

    async def run_llm_parallel(self, prompt_list, ai_arg):
        tasks = []
        responses = []

        try:
            for prompt in prompt_list:
                task = self.call_llm_async(prompt, ai_arg)
                tasks.append(task)

            for task in asyncio.as_completed(tasks):
                try:
                    result = await task
                    responses.append(result)
                except Exception as e:
                    print(f"{Constants.ORCHESTRATOR_ERROR_PARALLEL}{e!s}")
                    responses.append(f"{Constants.ORCHESTRATOR_ERROR} {e!s}")
        except Exception as e:
            print(f"{Constants.ORCHESTRATOR_ERROR_PARALLEL_PROCESSING} {e!s}")

        return responses

    async def run_llm_sequential_stream(self, prompt_list, sub_tasks, ai_arg):
        responses = []

        try:
            for i, prompt in enumerate(prompt_list):
                try:
                    task_header = f"\n--- {Constants.ORCHESTRATOR_SUBTASK} {i + 1}: {sub_tasks[i]['task']} ---\n"
                    self.response_signal.emit(task_header, self.stream)

                    result = await self.call_llm_async_stream_sequential(prompt, ai_arg)
                    responses.append(result)

                    self.response_signal.emit(
                        f"\n--- {Constants.ORCHESTRATOR_TASK} {i + 1} {Constants.ORCHESTRATOR_COMPLETED} ---\n",
                        self.stream,
                    )

                except Exception as e:
                    print(
                        f"{Constants.ORCHESTRATOR_WORKER} {i} {Constants.ORCHESTRATOR_ERROR}{e!s}"
                    )
                    responses.append(f"{Constants.ORCHESTRATOR_ERROR} {e!s}")

        except Exception as e:
            print(f"{Constants.ORCHESTRATOR_ERROR_SEQUENTIAL_PROCESSING} {e!s}")

        return responses

    async def call_llm_async(self, prompt: str, ai_arg: dict) -> str:
        try:
            messages = [{"role": "user", "content": prompt}]
            ai_args = ai_arg.copy()
            ai_args["messages"] = messages

            kwargs = self._build_kwargs(ai_args, stream=False)
            resp = await self.async_fugu.responses.create(**kwargs)
            self._accumulate(resp)
            print(ai_args["model"], "Completed")
            return resp.output_text or ""
        except Exception as e:
            print(f"LLM call error: {e!s}")
            return f"{Constants.ORCHESTRATOR_ERROR_OCCURRED} {e!s}"

    async def call_llm_async_stream_sequential(self, prompt: str, ai_arg: dict) -> str:
        try:
            messages = [{"role": "user", "content": prompt}]
            ai_args = ai_arg.copy()
            ai_args["messages"] = messages

            kwargs = self._build_kwargs(ai_args, stream=True)
            stream = await self.async_fugu.responses.create(**kwargs)
            full_response = await self.dispatch_response(stream, self.stream)
            print(f"Sequential Worker ({ai_args['model']}) completed")
            return full_response
        except Exception as e:
            print(f"Sequential streaming LLM call error: {e!s}")
            return f"{Constants.ORCHESTRATOR_ERROR_OCCURRED} {e!s}"

    # ---------- utilities / prompts (logic unchanged) ----------

    def _clean_json_string(self, json_str):
        json_str = json_str.replace("```json", "").replace("```", "")
        json_str = json_str.replace("{{", "{").replace("}}", "}")
        json_str = re.sub(r"//.*", "", json_str)
        json_str = json_str.strip()
        return json_str

    def get_worker_prompt(self, user_query, task, description):
        return self.worker_prompt.format(user_query=user_query, task=task, description=description)

    def get_aggregator_prompt(self, user_query):
        return self.aggregator_prompt.format(user_query=user_query)

    def set_force_stop(self, force_stop):
        self.force_stop = force_stop

    def finish_run(self, model, finish_reason, stream):
        elapsed_time = time.time() - self.start_time
        meta = {
            "usage": dict(self._usage_acc),  # orchestrator + workers + aggregator accumulated
            "hints": sorted(self._hints_acc),
        }
        self.response_finished_signal.emit(
            model or "",
            finish_reason or "",
            elapsed_time,
            stream,
            meta,
        )
