from PyQt6.QtCore import QObject, pyqtSignal

from fugu.chat.model.SakanaAIThread import SakanaAIThread
from fugu.util.Constants import MODEL_MESSAGE, AIProviderName


class AIThreadFactory:
    @staticmethod
    def create_thread(args, chat_llm):
        if chat_llm == AIProviderName.SAKANA.value:
            return SakanaAIThread(args)
        else:
            raise ValueError(f"{MODEL_MESSAGE.MODEL_UNSUPPORTED} {chat_llm}")


class ChatModel(QObject):
    thread_started_signal = pyqtSignal()
    thread_finished_signal = pyqtSignal()
    response_signal = pyqtSignal(str, bool)
    response_finished_signal = pyqtSignal(str, str, float, bool, dict)

    def __init__(self):
        super().__init__()
        self.chat_thread = None

    def send_user_input(self, args, chat_llm):
        if self.chat_thread is not None and self.chat_thread.isRunning():
            print(f"{MODEL_MESSAGE.THREAD_RUNNING}")
            self.chat_thread.wait()

        self.chat_thread = AIThreadFactory.create_thread(args, chat_llm)
        self.chat_thread.started.connect(self.thread_started_signal.emit)
        self.chat_thread.finished.connect(self.handle_thread_finished)
        self.chat_thread.response_signal.connect(self.response_signal.emit)
        self.chat_thread.response_finished_signal.connect(self.response_finished_signal.emit)
        self.chat_thread.start()

    def handle_thread_finished(self):
        print(f"{MODEL_MESSAGE.THREAD_FINISHED}")
        self.thread_finished_signal.emit()
        self.chat_thread = None

    def force_stop(self):
        if self.chat_thread is not None:
            self.chat_thread.set_force_stop(True)
