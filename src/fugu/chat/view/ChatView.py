import contextlib
import logging
from functools import partial

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fugu.chat.view.ChatHistory import ChatHistory
from fugu.chat.view.ChatWidget import ChatWidget
from fugu.custom.CheckDoubleSpinBox import CheckDoubleSpinBox
from fugu.custom.CheckSpinBox import CheckSpinBox
from fugu.custom.PromptListWidget import PromptListWidget
from fugu.custom.PromptTextEdit import PromptTextEdit
from fugu.util.ChatType import ChatType
from fugu.util.Constants import UI, AIProviderName, Constants
from fugu.util.SettingsManager import SettingsManager
from fugu.util.Utility import Utility


def format_chat_header(model, finish_reason, elapsed_time, meta):
    """One-line label for the chat header (the red area). Used by both live responses and DB replay."""
    parts = [
        f"{Constants.MODEL_PREFIX}{model}",
        f"{Constants.ELAPSED_TIME}{format(float(elapsed_time), '.2f')}",
    ]
    meta = meta or {}
    finish_reason = (finish_reason or "").strip()
    if finish_reason:
        parts.append(f"{Constants.FINISH_REASON}{finish_reason}")
    usage = meta.get("usage") or {}
    if usage and usage.get("total_tokens"):
        total = usage.get("total_tokens", 0)
        input_t = usage.get("input_tokens", 0)
        output_t = usage.get("output_tokens", 0)
        reasoning = usage.get("reasoning_tokens", 0)
        parts.append(
            f"{Constants.TOKEN_PREFIX}{total} "
            f"(in {input_t} / out {output_t} / reasoning {reasoning})"
        )
    hints = meta.get("hints") or []
    if hints:
        parts.append(f"{Constants.WORKERS_PREFIX}{', '.join(hints)}")
    return " | ".join(parts)


class ChatView(QWidget):
    submitted_signal = pyqtSignal(str)
    stop_signal = pyqtSignal()
    chat_llm_signal = pyqtSignal(str)
    reload_chat_detail_signal = pyqtSignal(int)
    new_chat_signal = pyqtSignal()

    def __init__(self, model):
        super().__init__()
        self.model = model
        self._settings = SettingsManager.get_settings()
        self._current_chat_llm = Utility.get_settings_value(
            section="AI_Provider", prop="llm", default="OpenAI", save=True
        )
        self.found_text_positions = []
        self.current_position_index = -1

        self.initialize_ui()

    def initialize_ui(self):
        self.create_all_ui_components()
        self.setup_layouts()
        self.initialize_data()
        self.connect_signals()

    def create_all_ui_components(self):
        self.create_top_control_components()
        self.create_chat_display_components()
        self.create_user_input_components()
        self.create_config_tab_components()
        self.create_bottom_control_components()

    def create_top_control_components(self):
        # Top layout
        self.top_layout = QVBoxLayout()
        self.top_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Create buttons
        self.clear_all_button = QPushButton(
            QIcon(Utility.get_icon_path("ico", "bin.png")), UI.CLEAR_ALL
        )
        self.copy_all_button = QPushButton(
            QIcon(Utility.get_icon_path("ico", "cards-stack.png")), UI.COPY_ALL
        )
        self.reload_button = QPushButton(
            QIcon(Utility.get_icon_path("ico", "cards-address.png")), UI.RELOAD_ALL
        )

        # Search components
        self.search_text = PromptTextEdit()
        self.search_text.setPlaceholderText(UI.SEARCH_PROMPT_PLACEHOLDER)
        self.search_text.setFixedHeight(self.clear_all_button.sizeHint().height())
        self.search_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.search_result = QLabel()

        # Navigation buttons
        self.prev_button = QPushButton(QIcon(Utility.get_icon_path("ico", "arrow-180.png")), "")
        self.next_button = QPushButton(QIcon(Utility.get_icon_path("ico", "arrow.png")), "")

        # Create the top widget container
        self.top_widget = QWidget()
        self.top_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

    def create_chat_display_components(self):
        # Result layout for chat messages
        self.result_layout = QVBoxLayout()
        self.result_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.result_layout.setSpacing(0)
        self.result_layout.setContentsMargins(0, 0, 0, 0)

        self.result_widget = QWidget()

        # Scroll area for chat messages
        self.ai_answer_scroll_area = QScrollArea()
        self.ai_answer_scroll_area.setWidgetResizable(True)

        # Stop button and its container
        self.stop_button = QPushButton(
            QIcon(Utility.get_icon_path("ico", "minus-circle.png")), UI.STOP
        )

        self.stop_widget = QWidget()
        self.stop_widget.setVisible(False)

    def create_user_input_components(self):
        # Prompt text input
        self.prompt_text = PromptTextEdit()
        self.prompt_text.setPlaceholderText(UI.CHAT_PROMPT_PLACEHOLDER)

        # Prompt container
        self.prompt_widget = QWidget()
        self.prompt_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

    def create_bottom_control_components(self):
        # File button
        self.file_button = QPushButton(
            QIcon(Utility.get_icon_path("ico", "folder-open-image.png")), Constants.FILES
        )

        # Model selector components
        self.main_model_combo = QComboBox()
        self.main_model_combo.setMinimumWidth(150)

        # New chat button
        self.new_chat_button = QPushButton(
            QIcon(Utility.get_icon_path("ico", "plus.png")), Constants.NEW_CHAT
        )

        # Container for bottom controls
        self.bottom_control_widget = QWidget()
        self.bottom_control_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )

    def create_config_tab_components(self):
        # Config tabs
        self.config_tabs = QTabWidget()

        # Tab for LLM providers
        self.tabs = QTabWidget()

    def setup_layouts(self):
        self.setup_top_control_layout()
        self.setup_chat_display_layout()
        self.setup_user_input_layout()
        self.setup_config_tabs_layout()
        self.setup_bottom_control_layout()
        self.setup_main_layout()

    def setup_top_control_layout(self):
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.search_text)
        button_layout.addWidget(self.search_result)
        button_layout.addWidget(self.prev_button)
        button_layout.addWidget(self.next_button)
        button_layout.addWidget(self.copy_all_button)
        button_layout.addWidget(self.clear_all_button)
        button_layout.addWidget(self.reload_button)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.top_layout.addLayout(button_layout)
        self.top_widget.setLayout(self.top_layout)

    def setup_chat_display_layout(self):
        self.result_widget.setLayout(self.result_layout)
        self.ai_answer_scroll_area.setWidget(self.result_widget)

        stop_layout = QHBoxLayout()
        stop_layout.setContentsMargins(0, 0, 0, 0)
        stop_layout.setSpacing(0)
        stop_layout.addWidget(self.stop_button)
        stop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stop_widget.setLayout(stop_layout)

    def setup_user_input_layout(self):
        prompt_layout = QVBoxLayout()
        prompt_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        prompt_layout.addWidget(self.prompt_text)
        prompt_layout.setSpacing(0)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        self.prompt_widget.setLayout(prompt_layout)

    def setup_bottom_control_layout(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 5, 0, 0)

        model_label = QLabel("Model")

        layout.addWidget(self.file_button)
        layout.addWidget(model_label)
        layout.addWidget(self.main_model_combo)
        layout.addStretch()
        layout.addWidget(self.new_chat_button)

        self.bottom_control_widget.setLayout(layout)

    def setup_config_tabs_layout(self):
        chat_icon = QIcon(Utility.get_icon_path("ico", "users.png"))
        self.config_tabs.addTab(self.create_parameters_tab(), chat_icon, UI.CHAT)
        self.config_tabs.addTab(self.create_chatdb_tab(), chat_icon, UI.CHAT_LIST)
        self.config_tabs.addTab(self.create_prompt_tab(), chat_icon, UI.PROMPT)

    def setup_main_layout(self):
        # Chat section layout
        chat_layout = QVBoxLayout()
        chat_layout.addWidget(self.top_widget)
        chat_layout.addWidget(self.ai_answer_scroll_area)
        chat_layout.addWidget(self.stop_widget)
        chat_layout.addWidget(self.prompt_widget)
        chat_layout.addWidget(self.bottom_control_widget)

        chatWidget = QWidget()
        chatWidget.setLayout(chat_layout)

        # Config section layout
        config_layout = QVBoxLayout()
        config_layout.addWidget(self.config_tabs)

        configWidget = QWidget()
        configWidget.setLayout(config_layout)

        # Main splitter
        mainWidget = QSplitter(Qt.Orientation.Horizontal)
        mainWidget.addWidget(configWidget)
        mainWidget.addWidget(chatWidget)
        mainWidget.setSizes([UI.QSPLITTER_LEFT_WIDTH, UI.QSPLITTER_RIGHT_WIDTH])
        mainWidget.setHandleWidth(UI.QSPLITTER_HANDLEWIDTH)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(mainWidget)
        self.setLayout(main_layout)

    def initialize_data(self):
        self.set_initial_llm_tab()
        self.update_main_model_list()
        self.reset_search_bar()

    def set_initial_llm_tab(self):
        index = self.tabs.indexOf(self.tabs.findChild(QWidget, self._current_chat_llm))
        if index != -1:
            self.tabs.setCurrentIndex(index)

    def connect_signals(self):
        self.connect_top_control_signals()
        self.connect_chat_display_signals()
        self.connect_user_input_signals()
        self.connect_config_tab_signals()
        self.connect_bottom_control_signals()

    def connect_top_control_signals(self):
        self.clear_all_button.clicked.connect(lambda: self.clear_all())
        self.copy_all_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.get_all_text())
        )
        self.reload_button.clicked.connect(lambda: self.reload_chat_detail_signal.emit(-1))

        self.search_text.submitted_signal.connect(self.search)
        self.prev_button.clicked.connect(self.scroll_to_previous_match_widget)
        self.next_button.clicked.connect(self.scroll_to_next_match_widget)

    def connect_chat_display_signals(self):
        self.stop_button.clicked.connect(self.force_stop)

    def connect_user_input_signals(self):
        self.prompt_text.submitted_signal.connect(self.handle_submitted_signal)

    def connect_config_tab_signals(self):
        self.tabs.currentChanged.connect(self.on_tab_change)

    def connect_bottom_control_signals(self):
        self.file_button.clicked.connect(lambda: self.select_files(self._current_chat_llm))
        self.main_model_combo.currentTextChanged.connect(self.sync_model_selection)
        self.new_chat_button.clicked.connect(self.create_new_chat)

    def update_main_model_list(self):
        saved_model = Utility.get_settings_value(
            section=f"{self._current_chat_llm}_Model_Parameter",
            prop="model_name",
            default=self.get_default_model_for_provider(self._current_chat_llm),
            save=True,
        )

        self.main_model_combo.blockSignals(True)
        try:
            self.main_model_combo.clear()
            current_model_combo = self.findChild(QComboBox, f"{self._current_chat_llm}_ModelList")
            if current_model_combo:
                for i in range(current_model_combo.count()):
                    self.main_model_combo.addItem(current_model_combo.itemText(i))

                saved_model_index = self.main_model_combo.findText(saved_model)
                if saved_model_index >= 0:
                    self.main_model_combo.setCurrentIndex(saved_model_index)
        finally:
            self.main_model_combo.blockSignals(False)

    def sync_model_selection(self, model_name):
        if not model_name:
            return

        current_model_combo = self.findChild(QComboBox, f"{self._current_chat_llm}_ModelList")
        if current_model_combo and current_model_combo.count() > 0:
            # Block signals to prevent recursive calls
            current_model_combo.blockSignals(True)
            index = current_model_combo.findText(model_name)
            if index >= 0:
                current_model_combo.setCurrentIndex(index)
            current_model_combo.blockSignals(False)

    def on_tab_change(self, index):
        self._current_chat_llm = self.tabs.tabText(index)
        self._settings.setValue("AI_Provider/llm", self._current_chat_llm)
        self.chat_llm_signal.emit(self._current_chat_llm)
        self.update_main_model_list()

    def create_new_chat(self):
        self.new_chat_signal.emit()

    def reset_search_bar(self):
        self.found_text_positions = []
        self.search_result.clear()
        self.current_position_index = -1
        self.update_navigation_buttons()

    def search(self, text: str):
        if text and text.strip() and len(text) >= 2:
            self.found_text_positions = []
            self.current_position_index = -1

            search_text_lower = text.lower()

            for i in range(self.result_layout.count()):
                current_widget = self.result_layout.itemAt(i).widget()
                current_text = current_widget.get_original_text()
                current_text_lower = current_text.lower()

                if search_text_lower in current_text_lower:
                    self.found_text_positions.append(i)
                    highlight_text = current_widget.highlight_search_text(current_text, text)
                    current_widget.apply_highlight(highlight_text)
                else:
                    current_widget.show_original_text()

            if self.found_text_positions:
                self.current_position_index = 0
                self.scroll_to_match_widget(self.found_text_positions[self.current_position_index])
        if len(self.found_text_positions) > 0:
            self.search_result.setText(f"{len(self.found_text_positions)} {UI.FOUNDS}")
        else:
            self.search_result.clear()
        self.update_navigation_buttons()
        self.search_text.clear()

    def scroll_to_match_widget(self, position):
        self.ai_answer_scroll_area.ensureWidgetVisible(self.result_layout.itemAt(position).widget())

    def scroll_to_previous_match_widget(self):
        if len(self.found_text_positions) > 0 and self.current_position_index > 0:
            self.current_position_index -= 1
            self.scroll_to_match_widget(self.found_text_positions[self.current_position_index])
            self.update_navigation_buttons()

    def scroll_to_next_match_widget(self):
        if (
            len(self.found_text_positions) > 0
            and self.current_position_index < len(self.found_text_positions) - 1
        ):
            self.current_position_index += 1
            self.scroll_to_match_widget(self.found_text_positions[self.current_position_index])
            self.update_navigation_buttons()

    def update_navigation_buttons(self):
        self.prev_button.setEnabled(self.current_position_index > 0)
        self.next_button.setEnabled(
            self.current_position_index < len(self.found_text_positions) - 1
        )

    def create_parameters_tab(self):
        layoutWidget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Tabs for LLM
        self.tabs = QTabWidget()
        self.tabs.addTab(
            self.create_sakanaai_tabcontent(AIProviderName.SAKANA.value),
            AIProviderName.SAKANA.value,
        )
        self.tabs.currentChanged.connect(self.on_tab_change)

        layout.addWidget(self.tabs)
        layoutWidget.setLayout(layout)

        layoutWidget.setMinimumWidth(300)
        layoutWidget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(layoutWidget)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_area.setMinimumWidth(320)

        return scroll_area

    def set_default_tab(self, name):
        index = self.tabs.indexOf(self.tabs.findChild(QWidget, name))
        if index != -1:
            self.tabs.setCurrentIndex(index)

    def on_system_change(self, name):
        current_text = self.findChild(QComboBox, f"{name}_systemList").currentText()
        system_values = Utility.get_system_value(
            section=f"{name}_System",
            prefix="system",
            default="You are a helpful assistant.",
            length=5,
        )
        current_system = self.findChild(QTextEdit, f"{name}_current_system")
        if current_text in system_values:
            current_system.setText(system_values[current_text])
        else:
            current_system.clear()

    def save_system_value(self, name):
        current_systemList = self.findChild(QComboBox, f"{name}_systemList")
        current_system = self.findChild(QTextEdit, f"{name}_current_system")
        selected_key = current_systemList.currentText()
        value = current_system.toPlainText()
        self._settings.setValue(f"{name}_System/{selected_key}", value)
        self.update_system_list(name, Utility.extract_number_from_end(selected_key) - 1)

    def update_system_list(self, name, index=0):
        current_systemList = self.findChild(QComboBox, f"{name}_systemList")
        system_values = Utility.get_system_value(
            section=f"{name}_System",
            prefix="system",
            default="You are a helpful assistant.",
            length=5,
        )
        if current_systemList:
            current_systemList.clear()
            current_systemList.addItems(system_values.keys())

        if system_values and current_systemList:
            current_systemList.setCurrentIndex(index)

    def create_sakanaai_tabcontent(self, name):
        tabWidget = QWidget()
        tabWidget.setObjectName(name)
        layoutMain = QVBoxLayout()
        layoutMain.setContentsMargins(10, 10, 10, 10)
        layoutMain.setSpacing(10)

        groupSystem = self.create_system_layout(name)
        layoutMain.addWidget(groupSystem)

        groupModel = QGroupBox(f"{name} Model")
        modelLayout = QFormLayout()
        modelLabel = QLabel(f"{name} Model List")
        modelList = QComboBox()
        modelList.setObjectName(f"{name}_ModelList")
        modelList.clear()

        self.set_model_list(modelList, name)

        modelLayout.addRow(modelLabel)
        modelLayout.addRow(modelList)
        groupModel.setLayout(modelLayout)
        layoutMain.addWidget(groupModel)

        # Add QListWidget to show selected File list
        listGroup = QGroupBox(f"{name} File List")
        fileListLayout = QVBoxLayout()
        listGroup.setLayout(fileListLayout)

        fileListWidget = QListWidget()
        fileListWidget.setObjectName(f"{name}_FileList")
        fileListLayout.addWidget(fileListWidget)

        # Add buttons
        buttonLayout = QHBoxLayout()
        selectButton = QPushButton(
            QIcon(Utility.get_icon_path("ico", "folder-open-image.png")), "Files"
        )
        selectButton.setObjectName(f"{name}_SelectButton")

        deleteButton = QPushButton(
            QIcon(Utility.get_icon_path("ico", "folder--minus.png")), "Remove"
        )
        deleteButton.setObjectName(f"{name}_DeleteButton")
        deleteButton.setEnabled(False)

        buttonLayout.addWidget(selectButton)
        buttonLayout.addWidget(deleteButton)

        fileListLayout.addLayout(buttonLayout)

        submitLayout = QHBoxLayout()
        submitButton = QPushButton(
            QIcon(Utility.get_icon_path("ico", "inbox-document-text.png")), "Submit"
        )
        submitButton.setObjectName(f"{name}_SubmitButton")
        submitButton.setEnabled(False)
        submitLayout.addWidget(submitButton)

        fileListLayout.addLayout(submitLayout)

        selectButton.clicked.connect(partial(self.select_files, name))
        deleteButton.clicked.connect(partial(self.delete_file_from_list, name))
        submitButton.clicked.connect(partial(self.submit_file, name, None))

        fileListWidget.itemSelectionChanged.connect(partial(self.on_item_selection_changed, name))

        layoutMain.addWidget(listGroup)

        # Parameters Group
        groupParam = QGroupBox(f"{name} Parameters")
        paramLayout = QFormLayout()

        max_tokensSpinBox = CheckSpinBox()
        max_tokensSpinBox.setObjectName(f"{name}_max_tokensSpinBox")
        max_tokensSpinBox.spin_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        max_tokensSpinBox.spin_box.setRange(0, 128000)
        max_tokensSpinBox.spin_box.setAccelerated(True)
        max_tokensSpinBox.spin_box.setSingleStep(1)
        max_tokensSpinBox.spin_box.setValue(
            int(
                Utility.get_settings_value(
                    section=f"{name}_Model_Parameter",
                    prop="max_output_tokens",
                    default="12800",
                    save=True,
                )
            )
        )
        max_tokensSpinBox.valueChanged.connect(
            lambda value: self.maxoutputtokens_changed(value, name)
        )
        paramLayout.addRow("Max Tokens", max_tokensSpinBox)

        temperatureSpinBox = CheckDoubleSpinBox()
        temperatureSpinBox.setObjectName(f"{name}_temperatureSpinBox")
        temperatureSpinBox.spin_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        temperatureSpinBox.spin_box.setRange(0, 2)
        temperatureSpinBox.spin_box.setAccelerated(True)
        temperatureSpinBox.spin_box.setSingleStep(0.1)
        temperatureSpinBox.spin_box.setValue(
            float(
                Utility.get_settings_value(
                    section=f"{name}_Model_Parameter", prop="temperature", default="0.2", save=True
                )
            )
        )
        temperatureSpinBox.check_box.setChecked(False)
        temperatureSpinBox.valueChanged.connect(lambda value: self.temperature_changed(value, name))
        paramLayout.addRow("Temperature", temperatureSpinBox)

        groupParam.setLayout(paramLayout)
        layoutMain.addWidget(groupParam)

        optionGroup = QGroupBox(f"{name} Options")
        optionLayout = QVBoxLayout()

        streamCheckbox = QCheckBox("Stream")
        streamCheckbox.setObjectName(f"{name}_streamCheckbox")
        streamCheckbox.setChecked(
            (
                Utility.get_settings_value(
                    section=f"{name}_Model_Parameter", prop="stream", default="True", save=True
                )
            )
            == "True"
        )
        streamCheckbox.toggled.connect(lambda value: self.stream_changed(value, name))

        optionLayout.addWidget(streamCheckbox)
        optionGroup.setLayout(optionLayout)

        layoutMain.addWidget(optionGroup)
        layoutMain.addStretch()

        tabWidget.setLayout(layoutMain)
        tabWidget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        return tabWidget

    def get_default_model_for_provider(self, provider_name):
        if provider_name == AIProviderName.SAKANA.value:
            return "fugu-mini"
        else:
            return ""

    def set_model_list(self, modelList, name):
        if name == AIProviderName.SAKANA.value:
            api_key = self._settings.value("AI_Provider/Sakana")
            if api_key:
                modelList.addItems(Utility.get_sakanaai_model_list(api_key))
                llm_model = Utility.get_settings_value(
                    section=f"{name}_Model_Parameter",
                    prop="model_name",
                    default="fugu_mini",
                    save=True,
                )
                # Block signals during initial setup
                modelList.blockSignals(True)
                modelList.setCurrentIndex(modelList.findText(llm_model))
                modelList.blockSignals(False)

                # Disconnect any existing connections to avoid multiple connections
                with contextlib.suppress(BaseException):
                    modelList.currentTextChanged.disconnect()

                # Connect the signal
                modelList.currentTextChanged.connect(
                    lambda current_text: self.model_list_changed(current_text, name)
                )

    def select_files(self, llm):
        fileListWidget = self.findChild(QListWidget, f"{llm}_FileList")
        selected_files = self.show_file_explorer(llm)
        if selected_files:
            for file in selected_files:
                fileListWidget.addItem(file)
            self.update_submit_status(llm)

    def delete_file_from_list(self, llm):
        fileListWidget = self.findChild(QListWidget, f"{llm}_FileList")
        for item in fileListWidget.selectedItems():
            fileListWidget.takeItem(fileListWidget.row(item))
        self.update_submit_status(llm)

    def update_submit_status(self, llm):
        fileListWidget = self.findChild(QListWidget, f"{llm}_FileList")
        submitButton = self.findChild(QPushButton, f"{llm}_SubmitButton")
        submitButton.setEnabled(bool(fileListWidget.count()))

    def on_item_selection_changed(self, llm):
        self.reset_file_list(llm)

    def show_file_explorer(self, llm=None):
        file_filter = UI.FILE_FILTER

        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter(file_filter)

        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            return selected_files
        else:
            return [] if llm != AIProviderName.SAKANA.value else None

    def get_selected_files(self, llm):
        fileListWidget = self.findChild(QListWidget, f"{llm}_FileList")
        return [fileListWidget.item(i).text() for i in range(fileListWidget.count())]

    def reset_file_list(self, llm, clear: bool = False):
        fileListWidget = self.findChild(QListWidget, f"{llm}_FileList")
        deleteButton = self.findChild(QPushButton, f"{llm}_DeleteButton")
        submitButton = self.findChild(QPushButton, f"{llm}_SubmitButton")

        if clear:
            fileListWidget.clear()

        deleteButton.setEnabled(bool(fileListWidget.selectedItems()))
        submitButton.setEnabled(bool(fileListWidget.count()))

    def submit_file(self, llm, text):
        if text is None:
            text = self.prompt_text.toPlainText().strip()
        file_list = self.get_selected_files(llm)
        if file_list:
            self.submitted_signal.emit(text)
        else:
            self.submitted_signal.emit(text)

    def validate_input(self, text, file_list):
        if not file_list:
            self.show_warning(UI.WARNING_TITLE_SELECT_FILE_MESSAGE)
            return False
        if not text:
            self.show_warning(UI.WARNING_TITLE_NO_PROMPT_MESSAGE)
            return False
        return True

    def show_warning(self, message):
        QMessageBox.warning(self, UI.WARNING_TITLE, message)

    def model_list_changed(self, current_text, name):
        self._settings.setValue(f"{name}_Model_Parameter/model_name", current_text)
        # Sync with main model combo box if the current provider is active
        if name == self._current_chat_llm and hasattr(self, "main_model_combo"):
            self.main_model_combo.blockSignals(True)  # Prevent recursive signal calls
            index = self.main_model_combo.findText(current_text)
            if index >= 0:
                self.main_model_combo.setCurrentIndex(index)
            self.main_model_combo.blockSignals(False)

    def temperature_changed(self, value, name):
        self._settings.setValue(f"{name}_Model_Parameter/temperature", value)

    def maxoutputtokens_changed(self, value, name):
        self._settings.setValue(f"{name}_Model_Parameter/max_output_tokens", value)

    def stream_changed(self, checked, name):
        if checked:
            self._settings.setValue(f"{name}_Model_Parameter/stream", "True")
        else:
            self._settings.setValue(f"{name}_Model_Parameter/stream", "False")

    def create_system_layout(self, name):
        groupSystem = QGroupBox(f"{name} System")
        systemLayout = QFormLayout()
        systemLabel = QLabel("Select System")
        systemList = QComboBox()
        systemList.setObjectName(f"{name}_systemList")
        system_values = Utility.get_system_value(
            section=f"{name}_System",
            prefix="system",
            default="You are a helpful assistant.",
            length=5,
        )
        systemList.addItems(system_values.keys())
        systemList.currentIndexChanged.connect(lambda: self.on_system_change(name))

        current_system = QTextEdit()
        current_system.setObjectName(f"{name}_current_system")
        current_system.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred
        )
        current_system.setText(system_values["system1"])

        save_system_button = QPushButton(
            QIcon(Utility.get_icon_path("ico", "disk-black.png")), "Save"
        )
        save_system_button.clicked.connect(lambda: self.save_system_value(name))

        systemLayout.addRow(systemLabel)
        systemLayout.addRow(systemList)
        systemLayout.addRow(current_system)
        systemLayout.addRow(save_system_button)
        groupSystem.setLayout(systemLayout)
        return groupSystem

    def create_chatdb_tab(self):
        layoutWidget = QWidget()
        layout = QVBoxLayout()

        self._chat_history = ChatHistory(self.model)

        layout.addWidget(self._chat_history)

        layoutWidget.setLayout(layout)
        return layoutWidget

    def create_prompt_tab(self):
        layoutWidget = QWidget()
        layout = QVBoxLayout()

        self._prompt_list = PromptListWidget(
            table_name=Constants.CHAT_PROMPT_TABLE, db_connection_name="ChatPromptDBConnection"
        )
        layout.addWidget(self.prompt_list)

        layoutWidget.setLayout(layout)
        return layoutWidget

    def create_system_tab(self):
        layoutWidget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("System"))

        layoutWidget.setLayout(layout)
        return layoutWidget

    def update_ui_submit(self, chatType, text):
        self.ai_answer_scroll_area.verticalScrollBar().rangeChanged.connect(self.adjust_scroll_bar)
        self.add_user_question(chatType, text)
        self.stop_widget.setVisible(True)

    def add_user_question(self, chatType, text):
        user_question = ChatWidget(chatType, text)
        self.result_layout.addWidget(user_question)

    def adjust_scroll_bar(self, min_val, max_val):
        self.ai_answer_scroll_area.verticalScrollBar().setSliderPosition(max_val)

    def update_ui(self, result, stream):
        if stream:
            chatWidget = self.get_last_ai_widget()

            if chatWidget:
                chatWidget.add_text(result)
            else:
                chatWidget = ChatWidget(ChatType.AI)
                chatWidget.add_text(result)
                self.result_layout.addWidget(chatWidget)

        else:
            ai_answer = ChatWidget(ChatType.AI, result)
            self.result_layout.addWidget(ai_answer)

    def disconnect_scroll_range_changed(self):
        try:
            scroll_bar = self.ai_answer_scroll_area.verticalScrollBar()
            if scroll_bar.receivers(scroll_bar.rangeChanged) > 0:
                scroll_bar.rangeChanged.disconnect()
        except (TypeError, RuntimeError):
            # print("Scrollbar error")
            pass

    def update_ui_finish(self, model, finish_reason, elapsed_time, stream, meta=None):
        self.disconnect_scroll_range_changed()
        chatWidget = self.get_last_ai_widget()
        if stream:
            if chatWidget:
                chatWidget.apply_style()
                self.stop_widget.setVisible(False)
        else:
            self.stop_widget.setVisible(False)

        if chatWidget and chatWidget.get_chat_type() == ChatType.AI:
            chatWidget.set_model_name(format_chat_header(model, finish_reason, elapsed_time, meta))

    def get_last_ai_widget(self) -> ChatWidget | None:
        layout_item = self.result_widget.layout().itemAt(self.result_widget.layout().count() - 1)
        if layout_item:
            last_ai_widget = layout_item.widget()
            if last_ai_widget.get_chat_type() == ChatType.AI:
                return last_ai_widget
        else:
            return None

    def handle_submitted_signal(self, text):
        if text:
            self.submit_file(self._current_chat_llm, text)

    def start_chat(self):
        self.prompt_text.clear()
        self.prompt_text.setEnabled(False)

    def finish_chat(self):
        self.prompt_text.setEnabled(True)
        self.prompt_text.setFocus()

    def clear_prompt(self):
        self.prompt_text.clear()

    def set_focus(self):
        self.prompt_text.setFocus()

    def set_prompt(self, prompt):
        self.prompt_text.setText(prompt)

    def get_all_text(self):
        question = Utility.get_settings_value(
            section="AI_Provider", prop="question", default="[Question]", save=True
        )

        answer = Utility.get_settings_value(
            section="AI_Provider", prop="answer", default="[Answer]", save=True
        )

        all_previous_qa = []
        for i in range(self.result_layout.count()):
            current_widget = self.result_layout.itemAt(i).widget()
            if (
                current_widget.get_chat_type() == ChatType.HUMAN
                and len(current_widget.get_text()) > 0
            ):
                all_previous_qa.append(f"{question}: {current_widget.get_text()}")
            elif (
                current_widget.get_chat_type() == ChatType.AI and len(current_widget.get_text()) > 0
            ):
                all_previous_qa.append(f"{answer}: {current_widget.get_text()}")
        return "\n".join(all_previous_qa)

    def create_args(self, text, chat_llm):
        method_name = f"create_args_{chat_llm.lower()}"
        method = getattr(self, method_name, None)
        if callable(method):
            return method(text, chat_llm)
        else:
            raise ValueError(f"{UI.METHOD} {method_name} {UI.NOT_FOUND}")

    def create_args_sakana(self, text, chat_llm):
        api_key = self._settings.value(f"AI_Provider/{chat_llm}")
        model = self.findChild(QComboBox, f"{chat_llm}_ModelList").currentText()

        system_role = "system"

        stream = self.findChild(QCheckBox, f"{chat_llm}_streamCheckbox").isChecked()

        max_tokens_spin_box = self.findChild(CheckSpinBox, f"{chat_llm}_max_tokensSpinBox").spin_box
        max_output_tokens = max_tokens_spin_box.value() if max_tokens_spin_box.isEnabled() else None

        temperature_spin_box = self.findChild(
            CheckDoubleSpinBox, f"{chat_llm}_temperatureSpinBox"
        ).spin_box
        temperature = temperature_spin_box.value() if temperature_spin_box.isEnabled() else None

        file_list = self.get_selected_files(chat_llm)

        content = []

        if file_list:
            text_file_contents = ""

            for _index, file_name in enumerate(file_list):
                file_extension = file_name.split(".")[-1].lower()

                # Handle text files
                if file_extension in UI.TEXT_FILE_EXTENSIONS:
                    try:
                        with open(file_name, encoding="utf-8") as file:
                            file_content = file.read()
                            if text_file_contents:
                                text_file_contents += f"\n\n{file_name}\n{file_content}"
                            else:
                                text_file_contents = f"{file_name}\n{file_content}"
                    except Exception as e:
                        logging.error(f"Error reading text file {file_name}: {e!s}")

                # Handle image files
                elif file_extension in UI.IMAGE_TYPE_EXTENSIONS:
                    media_type = UI.IMAGE_TYPE_MAPPING.get(file_extension)
                    image_data = Utility.base64_encode_file(file_name)
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_data}",
                                "detail": "auto",
                            },
                        }
                    )

                # Handle document files
                elif file_extension in UI.OPENAI_DOCUMENT_TYPE_EXTENSIONS:
                    media_type = UI.OPENAI_DOCUMENT_TYPE_MAPPING.get(file_extension)
                    document_data = Utility.base64_encode_file(file_name)
                    content.append(
                        {
                            "type": "file",
                            "file": {
                                "filename": f"{file_name}",
                                "file_data": f"data:{media_type};base64,{document_data}",
                            },
                        }
                    )

            # Add collected text file contents to content
            if text_file_contents:
                content.append({"type": "text", "text": text_file_contents.strip()})

        # Add user's main text input
        content.append({"type": "text", "text": text})

        messages = [
            {
                "role": system_role,
                "content": self.findChild(QTextEdit, f"{chat_llm}_current_system").toPlainText(),
            },
            {"role": "assistant", "content": self.get_all_text()},
            {"role": "user", "content": content},
        ]

        ai_arg = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        ai_arg["max_output_tokens"] = max_output_tokens
        ai_arg["temperature"] = temperature

        args = {
            "api_key": api_key,
            "ai_arg": ai_arg,
        }

        return args

    def clear_all(self):
        target_layout = self.result_layout
        if target_layout is not None:
            while target_layout.count():
                item = target_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    def force_stop(self):
        self.stop_signal.emit()
        self.stop_widget.setVisible(False)

    @property
    def chat_history(self):
        return self._chat_history

    @property
    def prompt_list(self):
        return self._prompt_list
