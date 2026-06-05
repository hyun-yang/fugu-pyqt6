from PyQt6.QtCore import QObject, pyqtSignal

from fugu.agent.model.EvaluatorOpenAIThread import EvaluatorOpenAIThread
from fugu.agent.model.OrchestratorOpenAIThread import OrchestratorOpenAIThread
from fugu.util.Constants import MODEL_MESSAGE, AgentPattern, AIProviderName


class AgentThreadFactory:
    @staticmethod
    def create_thread(args, llm, agent_pattern):
        args["llm"] = llm
        if agent_pattern == AgentPattern.ORCHESTRATOR.value:
            if llm == AIProviderName.OPENAI.value:
                return OrchestratorOpenAIThread(args)
            else:
                raise ValueError(f"{MODEL_MESSAGE.MODEL_UNSUPPORTED} {agent_pattern}")
        elif agent_pattern == AgentPattern.EVALUATOR.value:
            if llm == AIProviderName.SAKANA.value:
                return EvaluatorOpenAIThread(args)
            else:
                raise ValueError(f"{MODEL_MESSAGE.MODEL_UNSUPPORTED} {agent_pattern}")
        else:
            raise ValueError(f"{MODEL_MESSAGE.MODEL_UNSUPPORTED} {agent_pattern}")


class AgentModel(QObject):
    thread_started_signal = pyqtSignal()
    thread_finished_signal = pyqtSignal()
    response_signal = pyqtSignal(str, bool)
    response_finished_signal = pyqtSignal(str, str, float, bool, dict)

    def __init__(self):
        super().__init__()
        self.agent_thread = None

    def send_user_input(self, args, llm, agent_pattern):
        if self.agent_thread is not None and self.agent_thread.isRunning():
            print(f"{MODEL_MESSAGE.THREAD_RUNNING}")
            self.agent_thread.wait()

        self.agent_thread = AgentThreadFactory.create_thread(args, llm, agent_pattern)
        self.agent_thread.started.connect(self.thread_started_signal.emit)
        self.agent_thread.finished.connect(self.handle_thread_finished)
        self.agent_thread.response_signal.connect(self.response_signal.emit)
        self.agent_thread.response_finished_signal.connect(self.response_finished_signal.emit)
        self.agent_thread.start()

    def handle_thread_finished(self):
        print(f"{MODEL_MESSAGE.THREAD_FINISHED}")
        self.thread_finished_signal.emit()
        self.agent_thread = None

    def force_stop(self):
        if self.agent_thread is not None:
            self.agent_thread.set_force_stop(True)
