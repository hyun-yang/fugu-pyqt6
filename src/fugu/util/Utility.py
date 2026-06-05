import base64
import os
import re
import sys
import tempfile
from pathlib import Path

import openai
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox, QVBoxLayout

from fugu.util.Constants import MODEL_MESSAGE, UI
from fugu.util.SettingsManager import SettingsManager


class Utility:
    @staticmethod
    def check_openai_api_key(api_key):
        openai.api_key = api_key

        try:
            response = openai.models.list().model_dump()
            return bool(response["data"])
        except openai.AuthenticationError:
            print(f"{MODEL_MESSAGE.AUTHENTICATION_FAILED_OPENAI}")
            return False
        except Exception as exception:
            print(f"{MODEL_MESSAGE.UNEXPECTED_ERROR} {exception!s}")
            return False

    @staticmethod
    def get_openai_model_list(api_key):
        openai.api_key = api_key

        try:
            response = openai.models.list().model_dump()
            response_data = response["data"]
            gtp_ids = sorted(
                [
                    item["id"]
                    for item in response_data
                    if "instruct" not in item["id"]
                    and (
                        item["id"].strip().startswith("gpt-4")
                        or item["id"].strip().startswith("gpt-5")
                    )
                ]
            )
            return gtp_ids
        except openai.AuthenticationError:
            print(f"{MODEL_MESSAGE.AUTHENTICATION_FAILED_OPENAI}")
            return []
        except Exception as exception:
            print(f"{MODEL_MESSAGE.UNEXPECTED_ERROR} {exception!s}")
            return []

    @staticmethod
    def check_sakana_api_key(api_key):
        return bool(api_key and api_key.strip())

    @staticmethod
    def get_sakanaai_model_list(api_key):
        try:
            return ["fugu-mini", "fugu-ultra"]
        except openai.AuthenticationError:
            print(f"{MODEL_MESSAGE.AUTHENTICATION_FAILED_OPENAI}")
            return []
        except Exception as exception:
            print(f"{MODEL_MESSAGE.UNEXPECTED_ERROR} {exception!s}")
            return []

    @staticmethod
    def parse_version_from_id(model_id: str) -> tuple[int, int] | None:
        """
        Handles:
        - claude-3-5-sonnet-20240620 -> (3, 5)
        - claude-4-opus-20240620 -> (4, 0)
        - claude-3-haiku-20240307 -> (3, 0)
        - claude-sonnet-4-20250514 -> (4, 0)
        - claude-opus-4-20250514 -> (4, 0)
        """
        # Pattern 1: claude-3-5-sonnet-20240620, claude-3-haiku-20240307, etc.
        m = re.match(r"claude-(\d+)(?:-(\d+))?", model_id)
        if m:
            major = int(m.group(1))
            minor = int(m.group(2)) if m.group(2) else 0
            return (major, minor)
        # Pattern 2: claude-sonnet-4-20250514, claude-opus-4-20250514, etc.
        m2 = re.match(r"claude-(?:[a-z]+)-(\d+)(?:-(\d+))?", model_id)
        if m2:
            major = int(m2.group(1))
            minor = int(m2.group(2)) if m2.group(2) else 0
            return (major, minor)
        return None

    @staticmethod
    def is_version_gte(version: tuple[int, int], base_version: tuple[int, int]) -> bool:
        return version >= base_version

    @staticmethod
    def filter_models(models: list, min_version=(3, 5)):
        """
        models: List[ModelInfo]
        min_version: tuple, e.g. (3, 5)
        """
        filtered = []
        for m in models:
            version = Utility.parse_version_from_id(m.id)
            if version and Utility.is_version_gte(version, min_version):
                filtered.append(m.id)
        return filtered

    @staticmethod
    def get_icon_path(folder: str, icon: str):
        if getattr(sys, "frozen", False):
            base_path = sys._MEIPASS
        else:
            base_path = Path(os.path.dirname(__file__))
            base_path = base_path.parents[0]  # root path

        icon_path = os.path.join(base_path, folder, icon)
        icon_path = icon_path.replace(os.sep, "/")

        if not os.path.exists(icon_path):
            print(f"{UI.ICON_FILE_ERROR} {icon_path} {UI.ICON_FILE_NOT_EXIST}")
            return None
        return icon_path

    @staticmethod
    def get_settings_value(section: str, prop: str, default: str, save: bool) -> str:
        settings = SettingsManager.get_settings()
        settings.beginGroup(section)

        value = settings.value(prop, None)

        if value is None:
            if save:
                settings.setValue(prop, default)
                settings.sync()
            value = default

        settings.endGroup()
        return value

    @staticmethod
    def get_system_value(section: str, prefix: str, default: str, length: int) -> dict:
        settings = SettingsManager.get_settings()

        if section not in settings.childGroups():
            settings.beginGroup(section)
            for i in range(1, length + 1):
                settings.setValue(f"{prefix}{i}", default)
            settings.endGroup()

        settings.beginGroup(section)
        values = {
            f"{prefix}{i}": settings.value(f"{prefix}{i}", default) for i in range(1, length + 1)
        }
        settings.endGroup()

        return values

    @staticmethod
    def extract_number_from_end(name):
        match = re.search(r"\d+$", name)
        if match:
            return int(match.group())
        return None

    @staticmethod
    def confirm_dialog(title: str, message: str) -> bool:
        dialog = QDialog()
        dialog.setWindowTitle(title)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setLayout(QVBoxLayout())

        message_label = QLabel(message)
        dialog.layout().addWidget(message_label)

        dialog_buttonbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
        )
        dialog.layout().addWidget(dialog_buttonbox)

        no_button = dialog_buttonbox.button(QDialogButtonBox.StandardButton.No)
        no_button.setDefault(True)
        no_button.setFocus()

        def on_click(button):
            dialog.done(
                dialog_buttonbox.standardButton(button) == QDialogButtonBox.StandardButton.Yes
            )

        dialog_buttonbox.clicked.connect(on_click)

        result = dialog.exec()
        return result == QDialog.DialogCode.Accepted

    @staticmethod
    def show_alarm_message(
        title: str,
        message: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Yes
        | QMessageBox.StandardButton.No
        | QMessageBox.StandardButton.Cancel,
    ):
        message_box = QMessageBox()
        message_box.setWindowTitle(title)
        message_box.setText(message)
        message_box.setStandardButtons(buttons)
        return message_box.exec()

    @staticmethod
    def base64_encode_file(path):
        with open(path, UI.FILE_READ_IN_BINARY_MODE) as file:
            return base64.b64encode(file.read()).decode(UI.UTF_8)

    @staticmethod
    def create_temp_file(content, extension_name, apply_decode):
        with tempfile.NamedTemporaryFile(delete=False, suffix="." + extension_name) as temp_file:
            if apply_decode:
                temp_file.write(base64.b64decode(content))
            else:
                temp_file.write(content)
            temp_file.flush()
            temp_file_name = temp_file.name
        return temp_file_name
