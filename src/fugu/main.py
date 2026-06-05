import logging
import sys
import time
from os import path

from PyQt6.QtCore import QFile, QSize
from PyQt6.QtGui import QAction, QFont, QGuiApplication, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSplashScreen,
    QStackedWidget,
    QStyleFactory,
    QToolBar,
    QWidget,
    QWidgetAction,
)

from fugu.agent.AgentPresenter import AgentPresenter
from fugu.chat.ChatPresenter import ChatPresenter
from fugu.util.AnimatedProgressBar import AnimatedProgressBar
from fugu.util.AppInfoDialog import AppInfoDialog
from fugu.util.Constants import UI, AIProviderName, Constants, MainWidgetIndex
from fugu.util.DataManager import DataManager
from fugu.util.GlobalSetting import GlobalSetting
from fugu.util.Paths import user_data_base
from fugu.util.SettingsManager import SettingsManager
from fugu.util.Utility import Utility
from fugu.util.VerticalLine import VerticalLine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initialize_manager()
        self.initialize_variables()
        self.initialize_ui()

    def initialize_manager(self):
        if not QFile.exists(str(user_data_base() / Constants.SETTINGS_FILENAME)):
            QMessageBox.warning(self, UI.WARNING_TITLE, UI.WARNING_API_KEY_SETTING_MESSAGE)

        SettingsManager.initialize_settings()
        self._settings = SettingsManager.get_settings()

        DataManager.initialize_database()
        self._database = DataManager.get_database()

    def initialize_variables(self):
        self.progress_bar = None
        self.current_llm = None
        self.current_system = None
        self._status_bar_widgets = []

    def initialize_ui(self):

        self.initialize_window()

        self._chat = ChatPresenter()
        self._chat.model.thread_started_signal.connect(self.show_result_info)
        self._chat.model.response_finished_signal.connect(self.show_result_info)

        self._agent = AgentPresenter()
        self._agent.model.thread_started_signal.connect(self.show_result_info)
        self._agent.model.response_finished_signal.connect(self.show_result_info)

        self.set_main_widgets()

    def set_main_widgets(self):
        self._main_widget = QStackedWidget()

        self._main_widget_index = {
            MainWidgetIndex.CHAT_WIDGET: self._main_widget.addWidget(self._chat),
            MainWidgetIndex.AGENT_WIDGET: self._main_widget.addWidget(self._agent),
        }
        self.setCentralWidget(self._main_widget)
        self.set_current_widget(MainWidgetIndex.CHAT_WIDGET)

    def set_current_widget(self, index: MainWidgetIndex):
        self._settings.setValue("AI_Provider/llm", AIProviderName.SAKANA.value)
        self._main_widget.setCurrentIndex(self._main_widget_index[index])

    def initialize_window(self):
        self.setWindowTitle(Constants.APPLICATION_TITLE)
        self.setWindowIcon(QIcon(Utility.get_icon_path("ico", "app.svg")))
        self.setGeometry(*self.set_window_size(4 / 5))
        self.set_actions()
        self.set_menubar()
        self.set_toolbar()
        self.set_statusbar()

    def set_actions(self):
        self.chat_action = QAction("Chat", self)
        self.chat_action.setStatusTip(UI.CHAT_TIP)
        self.chat_action.triggered.connect(
            lambda: self.set_current_widget(MainWidgetIndex.CHAT_WIDGET)
        )

        self.agent_action = QAction("AGENT", self)
        self.agent_action.setStatusTip(UI.AGENT_TIP)
        self.agent_action.triggered.connect(
            lambda: self.set_current_widget(MainWidgetIndex.AGENT_WIDGET)
        )

        self.setting_action = QAction("Setting", self)
        self.setting_action.setStatusTip(UI.SETTING_TIP)
        self.setting_action.triggered.connect(self.open_global_setting)

        self.close_action = QAction("Close", self)
        self.close_action.setStatusTip(UI.CLOSE_TIP)
        self.close_action.triggered.connect(self.close)

        self.app_info_action = QAction("About", self)
        self.app_info_action.setStatusTip(UI.ABOUT_TIP)
        self.app_info_action.triggered.connect(self.show_app_info)

    def set_window_size(self, ratio):
        sg = QGuiApplication.primaryScreen().availableGeometry()

        width = int(sg.width() * ratio)
        height = int(sg.height() * ratio)
        left = int((sg.width() - width) / 2)
        top = int((sg.height() - height) / 2)
        return left, top, width, height

    def set_menubar(self):
        menubar = self.menuBar()

        file_menu = QMenu(UI.FILE, self)
        file_menu.addAction(self.setting_action)
        file_menu.addSeparator()
        file_menu.addAction(self.close_action)
        menubar.addMenu(file_menu)

        view_menu = QMenu(UI.VIEW, self)
        view_menu.addAction(self.chat_action)
        view_menu.addAction(self.agent_action)
        menubar.addMenu(view_menu)

        help_menu = QMenu(UI.HELP, self)
        help_menu.addAction(self.app_info_action)
        menubar.addMenu(help_menu)

    def set_toolbar(self):
        self.buttons = []

        icon_size = QSize(32, 32)
        main_toolbar = QToolBar()

        main_toolbar_layout = QHBoxLayout()

        self.setting_button = QPushButton(QIcon(Utility.get_icon_path("ico", "setting.svg")), "")
        self.setting_button.setFixedSize(40, 40)
        self.setting_button.setIconSize(icon_size)
        self.setting_button.setCheckable(True)
        self.setting_button.setToolTip(UI.SETTING_TIP)
        self.setting_button.clicked.connect(self.open_global_setting)

        self.exit_button = QPushButton(QIcon(Utility.get_icon_path("ico", "exit.svg")), "")
        self.exit_button.setFixedSize(40, 40)
        self.exit_button.setIconSize(icon_size)
        self.exit_button.setCheckable(True)
        self.exit_button.setToolTip(UI.CLOSE_TIP)
        self.exit_button.clicked.connect(self.close)

        self.kill_button = QPushButton(QIcon(Utility.get_icon_path("ico", "cross-shield.svg")), "")
        self.kill_button.setFixedSize(40, 40)
        self.kill_button.setIconSize(icon_size)
        self.kill_button.setCheckable(True)
        self.kill_button.setToolTip(UI.KILL_TIP)
        self.kill_button.clicked.connect(self.kill_all_threads)

        self.chat_button = self.create_button("chat.svg", UI.CHAT, MainWidgetIndex.CHAT_WIDGET)
        self.agent_button = self.create_button("a.svg", UI.AGENT, MainWidgetIndex.AGENT_WIDGET)

        self.buttons.extend(
            [
                self.chat_button,
                self.agent_button,
                self.setting_button,
                self.kill_button,
                self.exit_button,
            ]
        )

        main_toolbar_layout.addWidget(self.chat_button)
        main_toolbar_layout.addWidget(self.agent_button)
        main_toolbar_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )
        main_toolbar_layout.addWidget(self.setting_button)
        main_toolbar_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )
        main_toolbar_layout.addWidget(self.kill_button)
        main_toolbar_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )
        main_toolbar_layout.addWidget(self.exit_button)

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(main_toolbar_layout)

        self.toolbar_action = QWidgetAction(self)
        self.toolbar_action.setDefaultWidget(toolbar_widget)

        main_toolbar.addAction(self.toolbar_action)
        main_toolbar.setMovable(True)

        self.addToolBar(main_toolbar)

    def create_button(self, icon_path, tooltip, widget_index):
        button = QPushButton(QIcon(Utility.get_icon_path("ico", icon_path)), "")
        button.setFixedSize(40, 40)
        button.setIconSize(QSize(32, 32))
        button.setCheckable(True)
        button.setToolTip(tooltip)
        if widget_index:
            button.setProperty("widget_index", widget_index)
            button.clicked.connect(lambda _, btn=button: self.toggle_buttons(btn))
        return button

    def toggle_buttons(self, current_button):
        for button in self.buttons:
            button.setChecked(False)
        current_button.setChecked(True)
        widget_index = current_button.property("widget_index")
        if widget_index:
            self.set_current_widget(widget_index)

    def set_statusbar(self):
        self.status_bar = self.statusBar()

    def open_global_setting(self):
        self.toggle_buttons(self.setting_button)
        self.global_settings = GlobalSetting()
        self.global_settings.exec()

    def show_result_info(
        self, model=None, finish_reason=None, elapsed_time=None, stream=False, meta=None
    ):
        boldFont = QFont()
        boldFont.setBold(True)

        model_color = Utility.get_settings_value(
            section="Info_Label_Style", prop="model-color", default="green", save=True
        )

        model_time_label_style = f"""
                    QLabel {{
                        color: {model_color};
                    }}
                    """

        elapsed_time_color = Utility.get_settings_value(
            section="Info_Label_Style", prop="elapsedtime-color", default="orange", save=True
        )
        elapsed_time_label_style = f"""
                    QLabel {{
                        color: {elapsed_time_color};
                    }}
                    """

        finish_reason_color = Utility.get_settings_value(
            section="Info_Label_Style", prop="finishreason-color", default="blue", save=True
        )
        finish_reason_label_style = f"""
                    QLabel {{
                        color: {finish_reason_color};
                    }}
                    """

        token_color = Utility.get_settings_value(
            section="Info_Label_Style", prop="token-color", default="purple", save=True
        )
        token_label_style = f"""
                    QLabel {{
                        color: {token_color};
                    }}
                    """

        hints_color = Utility.get_settings_value(
            section="Info_Label_Style", prop="hints-color", default="teal", save=True
        )
        hints_label_style = f"""
                    QLabel {{
                        color: {hints_color};
                    }}
                    """

        status_bar = self.statusBar()
        status_bar.setFont(boldFont)

        for widget in self._status_bar_widgets:
            status_bar.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self._status_bar_widgets.clear()

        if self.progress_bar:
            self.progress_bar.stop_animation()
            self.progress_bar.deleteLater()
            self.progress_bar = None

        if all(parameter is not None for parameter in [model, finish_reason, elapsed_time]):
            model_label = QLabel()
            model_label.setText(Constants.MODEL_PREFIX + model)
            model_label.setFont(boldFont)
            model_label.setStyleSheet(model_time_label_style)

            elapsed_time_label = QLabel()
            elapsed_time_label.setText(Constants.ELAPSED_TIME + format(elapsed_time, ".2f"))
            elapsed_time_label.setFont(boldFont)
            elapsed_time_label.setStyleSheet(elapsed_time_label_style)

            finish_reason_label = QLabel()
            finish_reason_label.setText(Constants.FINISH_REASON + finish_reason)
            finish_reason_label.setFont(boldFont)
            if finish_reason == Constants.FORCE_STOP:
                finish_reason_label.setStyleSheet("color: red")
            else:
                finish_reason_label.setStyleSheet(finish_reason_label_style)

            def add_tracked(widget):
                status_bar.addPermanentWidget(widget)
                self._status_bar_widgets.append(widget)

            add_tracked(model_label)
            add_tracked(VerticalLine())
            add_tracked(elapsed_time_label)
            add_tracked(VerticalLine())
            add_tracked(finish_reason_label)
            add_tracked(VerticalLine())

            # ---- extra info derived from meta (usage / hints) ----
            meta = meta or {}
            usage = meta.get("usage", {})
            hints = meta.get("hints", [])

            if usage:
                total = usage.get("total_tokens", 0)
                reasoning = usage.get("reasoning_tokens", 0)
                input_t = usage.get("input_tokens", 0)
                output_t = usage.get("output_tokens", 0)

                token_label = QLabel()
                token_label.setText(
                    f"{Constants.TOKEN_PREFIX}{total} "
                    f"(in {input_t} / out {output_t} / reasoning {reasoning})"
                )
                token_label.setFont(boldFont)
                token_label.setStyleSheet(token_label_style)

                add_tracked(token_label)
                add_tracked(VerticalLine())

            if hints:
                hints_label = QLabel()
                hints_label.setText(Constants.WORKERS_PREFIX + ", ".join(hints))
                hints_label.setFont(boldFont)
                hints_label.setStyleSheet(hints_label_style)

                add_tracked(hints_label)
                add_tracked(VerticalLine())

        else:
            self.progress_bar = AnimatedProgressBar()
            self.progress_bar.start_animation()
            status_bar.addPermanentWidget(self.progress_bar)

    def show_app_info(self):
        aboutDialog = AppInfoDialog()
        aboutDialog.exec()

    def closeEvent(self, event):
        self.toggle_buttons(self.exit_button)
        should_close = Utility.confirm_dialog(
            UI.EXIT_APPLICATION_TITLE, UI.EXIT_APPLICATION_MESSAGE
        )
        if should_close:
            event.accept()
        else:
            event.ignore()

    def kill_all_threads(self):
        presenters = [
            getattr(self, "_chat", None),
            getattr(self, "_agent", None),
        ]

        for presenter in presenters:
            if not presenter:
                continue

            if hasattr(presenter.model, "force_stop"):
                presenter.model.force_stop()

            thread_obj = self._get_thread_from_presenter(presenter)

            if thread_obj and thread_obj.isRunning():
                if hasattr(thread_obj, "set_force_stop"):
                    thread_obj.set_force_stop(True)

                self._emit_thread_finish_signal(thread_obj, presenter)

        # Clean up UI elements
        self._cleanup_ui_elements(presenters)

        # Stop progress bar
        if self.progress_bar:
            self.progress_bar.stop_animation()
            self.progress_bar = None

        # Clear status
        if hasattr(self, "status_bar"):
            self.status_bar.clearMessage()
        self.show_result_info("Threads Killed", Constants.FORCE_STOP, 0.0, False)

        QMessageBox.information(
            self, Constants.THREAD_TERMINATION_TITLE, Constants.THREAD_TERMINATION_MESSAGE
        )

    def _get_thread_from_presenter(self, presenter):
        thread_attrs = ["chat_thread", "agent_thread"]

        for attr_name in thread_attrs:
            if hasattr(presenter.model, attr_name):
                return getattr(presenter.model, attr_name)
        return None

    def _emit_thread_finish_signal(self, thread_obj, presenter):
        try:
            current_time = time.time()
            elapsed_time = 0.0
            if hasattr(thread_obj, "start_time") and thread_obj.start_time:
                elapsed_time = current_time - thread_obj.start_time

            model_name = getattr(thread_obj, "model", "Unknown")
            presenter.model.response_finished_signal.emit(
                model_name, Constants.FORCE_STOP, elapsed_time, False, {}
            )
        except Exception as e:
            print(f"Error emitting finish signal: {e}")
            QMessageBox.warning(
                self, Constants.SIGNAL_ERROR, f"{Constants.ERROR_EMIT_SIGNAL}\n{e!s}"
            )

    def _cleanup_ui_elements(self, presenters):
        for presenter in presenters:
            if not presenter:
                continue

            # Find view attribute
            view = None
            for view_attr in ["chatView", "agentView"]:
                if hasattr(presenter, view_attr):
                    view = getattr(presenter, view_attr)
                    break

            if view:
                # Hide stop widget
                if hasattr(view, "stop_widget") and view.stop_widget:
                    view.stop_widget.setVisible(False)

                # Update UI
                if hasattr(view, "update_ui_finish"):
                    try:
                        view.update_ui_finish("Cancelled", Constants.FORCE_STOP, 0.0, False)
                    except Exception as e:
                        QMessageBox.warning(
                            self, Constants.SIGNAL_ERROR, f"{Constants.ERROR_UI_SIGNAL}\n{e!s}"
                        )


def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create(Constants.FUSION))

    base_path = sys._MEIPASS if getattr(sys, "frozen", False) else path.dirname(__file__)

    splash_image_path = path.join(base_path, "splash", "sakana-fugu.png")
    app_splash = QSplashScreen(QPixmap(splash_image_path))
    app_splash.show()
    app.processEvents()

    sg = QGuiApplication.primaryScreen().availableGeometry()
    screen_width = sg.width()

    mainWindow = MainWindow()

    if screen_width < 1450:
        mainWindow.showMaximized()
    else:
        mainWindow.show()

    app_splash.finish(mainWindow)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
