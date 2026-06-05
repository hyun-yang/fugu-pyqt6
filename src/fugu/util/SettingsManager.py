from PyQt6.QtCore import QSettings

from fugu.util.Constants import Constants
from fugu.util.Paths import user_data_base


class SettingsManager:
    __settings = None

    @classmethod
    def initialize_settings(cls):
        if cls.__settings is None:
            settings_path = str(user_data_base() / Constants.SETTINGS_FILENAME)
            cls.__settings = QSettings(settings_path, QSettings.Format.IniFormat)

    @classmethod
    def get_settings(cls) -> QSettings:
        if cls.__settings is None:
            cls.initialize_settings()
        return cls.__settings
