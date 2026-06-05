from enum import Enum, auto
from typing import ClassVar


class Constants:
    # Application Title
    APPLICATION_TITLE = "Sakana AI"

    # Setting file name
    SETTINGS_FILENAME = "settings.ini"

    # App Style
    FUSION = "Fusion"

    TOKEN_PREFIX = "Tokens: "
    WORKERS_PREFIX = "Workers: "

    # API Call User Stop
    MODEL_PREFIX = "Model: "
    ELAPSED_TIME = "Elapsed Time: "
    FINISH_REASON = "Finish Reason: "

    FORCE_STOP = "Force Stop"
    NORMAL_STOP = "stop"
    ERROR_STOP = "Error"
    RESPONSE_TIME = " | Response Time : "

    ORCHESTRATOR_ANALYSIS = "Orchestrator Analysis"
    ORCHESTRATOR_ANALYSIS_TASK = "=== Analyzing Task ===\n"
    ORCHESTRATOR_EXECUTING_TASKS = "\n=== Executing Tasks ===\n"
    ORCHESTRATOR_GENERATING_FINAL_RESULTS = "\n=== Generating Final Results ===\n"

    ORCHESTRATOR_TASK = "Task"
    ORCHESTRATOR_SUBTASK = "Subtask"
    ORCHESTRATOR_WORKER = "Worker"
    ORCHESTRATOR_TASK_QUESTION = "Task : "
    ORCHESTRATOR_ORIGINAL_RESPONSE = "Original Response:"
    ORCHESTRATOR_RESPONSE = "Response: "
    ORCHESTRATOR_COMPLETED = "Completed "
    ORCHESTRATOR_ERROR = "Error: "
    ORCHESTRATOR_FINAL_ANSWER = "Final Answer"
    ORCHESTRATOR_ERROR_OCCURRED = "Error occurred: "

    ORCHESTRATOR_JSON_PARSING_ERROR = "JSON Parsing Error: "
    ORCHESTRATOR_ERROR_PROCESSING = "Error during processing: "
    ORCHESTRATOR_ERROR_PARALLEL = "Parallel task error: "
    ORCHESTRATOR_ERROR_PARALLEL_PROCESSING = "Error during parallel task processing: "
    ORCHESTRATOR_ERROR_SEQUENTIAL_PROCESSING = "Error during sequential streaming task processing: "

    EVALUATION_PASS = "PASS"
    EVALUATION_PREVIOUS_ATTEMPTS = "Previous attempts:"
    EVALUATION_FEEDBACK = "Feedback"

    THOUGHTS_TAG = "thoughts"
    RESULT_TAG = "result"
    RESPONSE_TAG = "response"
    EVALUATION_TAG = "evaluation"
    FEEDBACK_TAG = "feedback"

    GENERATION_START = "=== GENERATION START ==="
    GENERATION_END = "=== GENERATION END ==="
    EVALUATION_START = "=== EVALUATION START ==="
    EVALUATION_END = "=== EVALUATION END ==="

    GENERATION_THOUGHTS = "Thoughts:"
    GENERATION_GENERATED = "Generated:"
    EVALUATION_STATUS_EX = "Status:"
    EVALUATION_FEEDBACK_EX = "Feedback:"

    EVALUATION_TASK = "Task:"

    ORIGINAL_TASK = "Original task: "
    CONTENT_TO_EVALUATE = "Content to evaluate: "

    # Database
    DATABASE_NAME = "fugu.db"
    SQLITE_DATABASE = "QSQLITE"

    CHAT_MAIN_TABLE = "chat_main"
    CHAT_DETAIL_TABLE = "chat_detail"

    AGENT_MAIN_TABLE = "agent_main"
    AGENT_DETAIL_TABLE = "agent_detail"

    CHAT_PROMPT_TABLE = "chat_prompt"
    AGENT_PROMPT_TABLE = "agent_prompt"

    FILES = "Files"
    NEW_CHAT = "New Chat"
    NEW_AGENT = "New Agent"

    SIGNAL_ERROR = "Signal Error"
    ERROR_EMIT_SIGNAL = "Error emitting finish signal: "
    ERROR_UI_SIGNAL = "Error updating UI finish: "

    ABOUT_TEXT = (
        "<b>Sakana Fugu Test</b><br>"
        "Version: 1.0.0<br><br>"
        "Author: Hayden Yang(양 현석)<br>"
        "Github: <a href='https://github.com/hyun-yang'>https://github.com/hyun-yang</a><br><br>"
        "Contact: iamyhs@gmail.com<br>"
    )

    def __setattr__(self, name, value):
        if name in self.__dict__:
            raise ValueError(f"Cannot reassign constant '{name}'")
        self.__dict__[name] = value


class UI:
    FILE = "File"
    VIEW = "View"
    HELP = "Help"

    UI = "UI"
    FOUNDS = "founds"
    NOT_FOUND = "not found"
    METHOD = "Method "

    CHAT = "Chat"
    CHAT_TIP = "Chat"
    CHAT_LIST = "Chat List"

    AGENT = "Agent"
    AGENT_TIP = "Agent"
    AGENT_LIST = "Agent List"

    SETTING_TIP = "Setting"

    CLOSE_TIP = "Exit App"

    KILL_TIP = "Terminate Thread"

    ABOUT_TIP = "About"

    ADD = "Add"
    DELETE = "Delete"
    RENAME = "Rename"
    STOP = "Stop"
    COPY = "Copy"
    CLEAR_ALL = "Clear All"
    COPY_ALL = "Copy All"
    RELOAD_ALL = "Reload All"
    OK = "Ok"
    CANCEL = "Cancel"
    SHOW_ORIGINAL_OR_FORMATTED = "Show original or formatted text"
    SHOW_OR_HIDE = "Show/Hide text"

    FILE_READ_IN_BINARY_MODE = "rb"
    UTF_8 = "utf-8"

    CHAT_PROMPT_PLACEHOLDER = (
        "Enter your query here.\nPress Shift+Enter to add a new line, then Enter to send."
    )
    SEARCH_PROMPT_PLACEHOLDER = "Enter your search term."
    SEARCH_PROMPT_DB_PLACEHOLDER = "Search..."

    TITLE = "Title"
    PROMPT = "Prompt"

    EXIT_APPLICATION_TITLE = "Exit Application"
    EXIT_APPLICATION_MESSAGE = "Are you sure you want to exit?"

    WARNING_TITLE = "Warning"
    WARNING_API_KEY_SETTING_MESSAGE = "Please set the API key in Setting->AI Provider."
    WARNING_TITLE_NO_ROW_SELECT_MESSAGE = "No row selected for saving."
    WARNING_TITLE_NO_ROW_DELETE_MESSAGE = "No row selected for deletion."
    WARNING_TITLE_SELECT_FILE_MESSAGE = "Select file first."
    WARNING_TITLE_NO_PROMPT_MESSAGE = "Enter your prompt."

    FILE_FILTER = "Files (*.*)"

    CONFIRM_DELETION_TITLE = "Confirm Deletion"
    CONFIRM_DELETION_ROW_MESSAGE = "Are you sure you want to delete the selected row?"
    CONFIRM_DELETION_CHAT_MESSAGE = "Are you sure you want to delete this chat?"
    CONFIRM_DELETION_AGENT_MESSAGE = "Are you sure you want to delete this agent?"
    CONFIRM_CHOOSE_CHAT_MESSAGE = "Choose chat first to delete"
    CONFIRM_CHOOSE_AGENT_MESSAGE = "Choose agent first to delete"

    LABEL_ENTER_NEW_NAME = "Enter new name:"

    SETTINGS = "Settings"
    SETTINGS_PIXEL = "px"

    ICON_FILE_ERROR = "Error: The icon file"
    ICON_FILE_NOT_EXIST = "does not exist."

    ITEM_ICON_SIZE = 32
    ITEM_EXTRA_SIZE = 20
    ITEM_PADDING = 5

    QSPLITTER_LEFT_WIDTH = 200
    QSPLITTER_RIGHT_WIDTH = 800
    QSPLITTER_HANDLEWIDTH = 3

    PROGRESS_BAR_STYLE = """
            QProgressBar{
                border: 1px grey;
                border-radius: 5px;
            }

            QProgressBar::chunk {
                background-color: lightgreen;
                width: 10px;
                margin: 1px;
            }
            """

    OPENAI_DOCUMENT_TYPE_MAPPING: ClassVar[dict[str, str]] = {
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }

    OPENAI_DOCUMENT_TYPE_EXTENSIONS: ClassVar[list[str]] = ["pdf", "doc", "docx", "pptx"]

    TEXT_FILE_EXTENSIONS: ClassVar[list[str]] = [
        "txt",
        "md",
        "csv",
        "tsv",
        "py",
        "ts",
        "tsx",
        "js",
        "jsx",
        "cs",
        "java",
        "kt",
        "swift",
        "go",
        "c",
        "cpp",
        "rb",
        "tex",
        "html",
        "xhtml",
        "htm",
        "css",
        "scss",
        "sass",
        "less",
        "json",
        "xml",
        "resx",
        "ini",
        "mjs",
        "pcfproj",
        "csproj",
        "pbxproj",
        "xcworkspacedata",
        "plist",
        "storyboard",
        "svg",
        "ipynb",
        "bat",
        "cmd",
        "ps1",
        "sh",
    ]

    def __setattr__(self, name, value):
        if name in self.__dict__:
            raise ValueError(f"Cannot reassign constant '{name}'")
        self.__dict__[name] = value


class MODEL_MESSAGE:
    MODEL_UNSUPPORTED = "Unsupported LLM:"
    THREAD_RUNNING = "Previous thread is still running!"
    THREAD_FINISHED = "Thread has been finished"
    UNEXPECTED_ERROR = "An unexpected error occurred: "
    AUTHENTICATION_FAILED_OPENAI = "Authentication failed. The OpenAI API key is not valid."

    def __setattr__(self, name, value):
        if name in self.__dict__:
            raise ValueError(f"Cannot reassign constant '{name}'")
        self.__dict__[name] = value


class DATABASE_MESSAGE:
    DATABASE_TITLE_ERROR = "Database Error"
    DATABASE_FETCH_ERROR = "Failed to fetch prompt from the database."
    DATABASE_ADD_ERROR = "Failed to add new row from the database."
    DATABASE_DELETE_ERROR = "Failed to delete row from the database."
    DATABASE_UPDATE_ERROR = "Failed to update row from the database."

    DATABASE_CHAT_CREATE_TABLE_ERROR = "Failed to create chat_main table: "
    DATABASE_CHAT_ADD_ERROR = "Failed to add chat main: "
    DATABASE_CHAT_UPDATE_ERROR = "Failed to update chat main: "
    DATABASE_CHAT_MAIN_ENTRY_SUCCESS = "Successfully deleted chat main entry with id: "
    DATABASE_CHAT_MAIN_ENTRY_FAIL = "Failed to delete chat main entry with id "

    DATABASE_CHAT_DETAIL_CREATE_TABLE_ERROR = "Failed to create chat detail table for chat_main_id "
    DATABASE_CHAT_DETAIL_INSERT_ERROR = "Failed to insert chat detail: "
    DATABASE_CHAT_DETAIL_DELETE_ERROR = "Failed to delete chat detail table "
    DATABASE_CHAT_DETAIL_FETCH_ERROR = "Failed to fetch chat details for chat_main_id"

    DATABASE_PROMPT_CREATE_TABLE_ERROR = "Failed to create prompt table: "
    DATABASE_PROMPT_ADD_ERROR = "Failed to add prompt: "
    DATABASE_PROMPT_UPDATE_ERROR = "Failed to update prompt: "
    DATABASE_PROMPT_DELETE_SUCCESS = "Successfully deleted prompt with id: "
    DATABASE_PROMPT_DELETE_FAIL = "Failed to delete prompt with id "

    DATABASE_AGENT_CREATE_TABLE_ERROR = "Failed to create agent_main table: "
    DATABASE_AGENT_ADD_ERROR = "Failed to add agent main: "
    DATABASE_AGENT_UPDATE_ERROR = "Failed to update agent main: "
    DATABASE_AGENT_MAIN_ENTRY_SUCCESS = "Successfully deleted agent main entry with id: "
    DATABASE_AGENT_MAIN_ENTRY_FAIL = "Failed to delete agent main entry with id "

    DATABASE_AGENT_DETAIL_CREATE_TABLE_ERROR = (
        "Failed to create agent detail table for agent_main_id "
    )
    DATABASE_AGENT_DETAIL_INSERT_ERROR = "Failed to insert agent detail: "
    DATABASE_AGENT_DETAIL_DELETE_ERROR = "Failed to delete agent detail table "
    DATABASE_AGENT_DETAIL_FETCH_ERROR = "Failed to fetch agent details for agent_main_id"

    DATABASE_RETRIEVE_DATA_FAIL = "Failed to retrieve data from "
    DATABASE_DELETE_TABLE_SUCCESS = "Successfully deleted table: "
    DATABASE_EXECUTE_QUERY_ERROR = "Failed to execute query: "

    DATABASE_FAILED_OPEN = "Failed to open database."
    DATABASE_ENABLE_FOREIGN_KEY = "Failed to enable foreign key: "
    DATABASE_PRAGMA_FOREIGN_KEYS_ON = "PRAGMA foreign_keys = ON;"

    NEW_TITLE = "New Title"
    NEW_PROMPT = "New Prompt"


class AIProviderName(Enum):
    OPENAI = "OpenAI"
    SAKANA = "Sakana"


class AgentPattern(Enum):
    ORCHESTRATOR = "Orchestrator"
    WORKER = "Worker"
    AGGREGATOR = "Aggregator"
    EVALUATOR = "Evaluator"
    GENERATOR = "Generator"
    TASK = "Task"


class MainWidgetIndex(Enum):
    CHAT_WIDGET = auto()
    AGENT_WIDGET = auto()


def get_ai_provider_names():
    return [ai_provider.value for ai_provider in AIProviderName]
