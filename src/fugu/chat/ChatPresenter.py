from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QDialog, QMessageBox, QVBoxLayout, QWidget

from fugu.chat.model.ChatModel import ChatModel
from fugu.chat.view.ChatView import ChatView, format_chat_header
from fugu.custom.ChatListModel import ChatListModel
from fugu.util.ChatType import ChatType
from fugu.util.ConfirmationDialog import ConfirmationDialog
from fugu.util.Constants import UI, Constants
from fugu.util.DataManager import DataManager
from fugu.util.SettingsManager import SettingsManager
from fugu.util.Utility import Utility


class ChatPresenter(QWidget):
    def __init__(self):
        super().__init__()
        self._chat_main_id = None
        self._chat_main_index = None
        self.initialize_manager()
        self.initialize_ui()

    def initialize_manager(self):
        self._settings = SettingsManager.get_settings()
        self._database = DataManager.get_database()
        self.llm = Utility.get_settings_value(
            section="AI_Provider", prop="llm", default="OpenAI", save=True
        )

    def initialize_ui(self):

        # View
        self.chatViewModel = ChatListModel(self._database)
        self.chatViewModel.new_chat_main_id_signal.connect(self.set_chat_main_id)
        self.chatViewModel.remove_chat_signal.connect(self.clear_chat)
        self.chatView = ChatView(self.chatViewModel)

        # Model
        self.chatModel = ChatModel()

        # View signal
        self.chatView.submitted_signal.connect(self.submit)
        self.chatView.stop_signal.connect(self.chatModel.force_stop)
        self.chatView.chat_llm_signal.connect(self.set_current_llm_signal)
        self.chatView.reload_chat_detail_signal.connect(self.show_chat_detail)
        self.chatView.new_chat_signal.connect(self.create_new_chat)

        self.chatView.prompt_list.sendPromptSignal.connect(self.chatView.set_prompt)

        self.chatView.chat_history.new_chat_signal.connect(self.create_new_chat)
        self.chatView.chat_history.delete_chat_signal.connect(self.confirm_delete_chat)
        self.chatView.chat_history.chat_list.delete_id_signal.connect(self.delete_chat_table)
        self.chatView.chat_history.filter_signal.connect(self.filter_list)

        self.chatView.set_default_tab(self.llm)

        self.initialize_chat_history()

        # Model signal
        self.chatModel.thread_started_signal.connect(self.chatView.start_chat)
        self.chatModel.thread_finished_signal.connect(self.chatView.finish_chat)
        self.chatModel.response_signal.connect(self.chatView.update_ui)
        self.chatModel.response_finished_signal.connect(self.handle_response_finished_signal)

        # View
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.chatView)

        self.setLayout(main_layout)

    def initialize_chat_history(self):
        self.chat_list = self.chatView.chat_history.chat_list
        self.chat_list.chat_id_signal.connect(self.show_chat_detail)

    def set_chat_main_id(self, chat_main_id):
        self.chat_main_id = chat_main_id
        self.view.clear_all()

    @pyqtSlot(str, str, float, bool, dict)
    def handle_response_finished_signal(self, model, finish_reason, elapsed_time, stream, meta):
        self.view.reset_file_list(self.llm, True)
        last_ai_widget = self.view.get_last_ai_widget()
        if last_ai_widget:
            self.chatView.update_ui_finish(model, finish_reason, elapsed_time, stream, meta)
            meta = meta or {}
            self._database.insert_chat_detail(
                self.chat_main_id,
                ChatType.AI.value,
                model,
                self.view.get_last_ai_widget().get_original_text(),
                elapsed_time,
                finish_reason,
                usage=meta.get("usage") or {},
                workers=meta.get("hints") or [],
            )

    @property
    def model(self):
        return self.chatModel

    @property
    def view(self):
        return self.chatView

    @property
    def chat_main_id(self):
        return self._chat_main_id

    @chat_main_id.setter
    def chat_main_id(self, value):
        self._chat_main_id = value

    @pyqtSlot(str)
    def set_current_llm_signal(self, llm_name):
        self.llm = llm_name

    @pyqtSlot(int)
    def clear_chat(self, delete_id):
        if self.chat_main_id == delete_id:
            self.chat_main_id = None
            self.view.clear_all()

    @pyqtSlot()
    def confirm_delete_chat(self):
        if self.chat_main_id:
            title = UI.CONFIRM_DELETION_TITLE
            message = UI.CONFIRM_DELETION_CHAT_MESSAGE
            dialog = ConfirmationDialog(title, message)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.delete_chat(self.chatViewModel.get_index_by_chat_main_id(self.chat_main_id))
        else:
            QMessageBox.information(self, UI.DELETE, UI.CONFIRM_CHOOSE_CHAT_MESSAGE)

    @pyqtSlot(int)
    def delete_chat_table(self, id):
        self._database.delete_chat_main(id)

    @pyqtSlot(str)
    def filter_list(self, text):
        self.chatViewModel.filter_by_title(text)

    def show_chat_detail(self, id):
        if id == -1:
            self.get_chat_detail(self.chat_main_id)
        elif id != self.chat_main_id:
            self.chat_main_id = id
            self.get_chat_detail(self.chat_main_id)

    def get_chat_detail(self, id):
        self.view.clear_all()
        self.view.reset_search_bar()
        chat_detail_list = self._database.get_all_chat_details_list(id)
        for chat_detail in chat_detail_list:
            if chat_detail["chat_type"] == ChatType.HUMAN.value:
                self.view.add_user_question(ChatType.HUMAN, chat_detail["chat"])
            else:
                self.view.add_user_question(ChatType.AI, chat_detail["chat"])
                meta = self._meta_from_row(chat_detail)
                label = format_chat_header(
                    chat_detail["chat_model"],
                    chat_detail.get("finish_reason"),
                    chat_detail["elapsed_time"] or 0,
                    meta,
                )
                self.view.get_last_ai_widget().set_model_name(label)

    @staticmethod
    def _meta_from_row(row):
        """Rebuild a meta dict from a DB row in the same shape as a live response."""

        def _int_or_none(v):
            try:
                return int(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None

        usage = {}
        for key in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"):
            v = _int_or_none(row.get(key))
            if v is not None:
                usage[key] = v
        workers_str = row.get("workers") or ""
        hints = [w.strip() for w in workers_str.split(",") if w.strip()] if workers_str else []
        return {"usage": usage, "hints": hints}

    def delete_chat(self, index):
        self.chatViewModel.remove_chat(index)

    def create_new_chat(self, title=Constants.NEW_CHAT):
        self.chatViewModel.add_new_chat(title)

    def add_human_chat(self, text):
        if self.chat_main_id:
            self._database.insert_chat_detail(
                self.chat_main_id, ChatType.HUMAN.value, None, text, None, None
            )
        else:
            self.create_new_chat()
            self._database.insert_chat_detail(
                self.chat_main_id, ChatType.HUMAN.value, None, text, None, None
            )

    def update_chat(self, index, new_title):
        self.chatViewModel.update_chat(index, new_title)

    def read_chat(self, index):
        return self.chatViewModel.get_chat(index)

    @pyqtSlot(str)
    def submit(self, text):
        if text and text.strip():
            self.add_human_chat(text)
            self.chatView.update_ui_submit(ChatType.HUMAN, text)
            self.chatModel.send_user_input(self.chatView.create_args(text, self.llm), self.llm)
