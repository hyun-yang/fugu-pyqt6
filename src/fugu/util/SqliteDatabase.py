import logging
import os
from typing import ClassVar

from PyQt6.QtSql import QSqlDatabase, QSqlQuery, QSqlTableModel

from fugu.util.Constants import DATABASE_MESSAGE, Constants
from fugu.util.Paths import user_data_base


class SqliteDatabase:
    def __init__(self, db_filename=Constants.DATABASE_NAME):
        self.initialize_vars(db_filename)
        self.initialize_db()
        logging.basicConfig(level=logging.INFO)

    def initialize_vars(self, db_filename):
        if not os.path.isabs(db_filename):
            db_filename = str(user_data_base() / db_filename)
        self.db_filename = db_filename
        self.db = None
        self.model = None

        # Chat
        self.chat_main_table_name = Constants.CHAT_MAIN_TABLE
        self.chat_detail_table_name = Constants.CHAT_DETAIL_TABLE
        self.chat_prompt_table_name = Constants.CHAT_PROMPT_TABLE

        # AGENT
        self.agent_main_table_name = Constants.AGENT_MAIN_TABLE
        self.agent_detail_table_name = Constants.AGENT_DETAIL_TABLE
        self.agent_prompt_table_name = Constants.AGENT_PROMPT_TABLE

        # Prompt
        self.prompt_table_name = Constants.CHAT_PROMPT_TABLE

    def initialize_db(self):
        self.db = QSqlDatabase.addDatabase(Constants.SQLITE_DATABASE)
        self.db.setDatabaseName(self.db_filename)
        if not self.db.open():
            print(f"{DATABASE_MESSAGE.DATABASE_FAILED_OPEN}")
            return

        self.enable_foreign_key()
        self.create_all_tables()

    def enable_foreign_key(self):
        query = QSqlQuery(db=self.db)
        query_string = DATABASE_MESSAGE.DATABASE_PRAGMA_FOREIGN_KEYS_ON
        if not query.exec(query_string):
            print(f"{DATABASE_MESSAGE.DATABASE_ENABLE_FOREIGN_KEY} {query.lastError().text()}")

    def setup_model(self, table_name, filter=""):
        self.model = QSqlTableModel(db=self.db)
        self.model.setTable(table_name)
        self.model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
        if filter:
            self.model.setFilter(filter)
        self.model.select()

    def create_all_tables(self):
        self.create_chat_main()

        # Create prompt tables for Chat and Agent
        self.create_prompt_table(self.chat_prompt_table_name)
        self.create_prompt_table(self.agent_prompt_table_name)

        self.create_agent_main()

    def create_chat_main(self):
        query = QSqlQuery()
        query_string = f"""
                        CREATE TABLE IF NOT EXISTS {self.chat_main_table_name}
                         (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                        )
                        """
        try:
            query.exec(query_string)
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_CHAT_CREATE_TABLE_ERROR} {e}")

    def add_chat_main(self, title):
        query = QSqlQuery()
        query.prepare(f"INSERT INTO {self.chat_main_table_name} (title) VALUES (:title)")
        query.bindValue(":title", title)
        try:
            if query.exec():
                chat_main_id = query.lastInsertId()
                self.create_chat_detail(chat_main_id)
                return chat_main_id
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_CHAT_ADD_ERROR} {e}")
        return None

    def update_chat_main(self, id, title):
        query = QSqlQuery()
        query.prepare(f"UPDATE {self.chat_main_table_name} SET title = :title WHERE id = :id")
        query.bindValue(":title", title)
        query.bindValue(":id", id)
        try:
            if query.exec():
                return True
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_CHAT_UPDATE_ERROR} {e}")
        return False

    def delete_chat_main_entry(self, id):
        try:
            query = QSqlQuery()
            query.prepare(f"DELETE FROM {self.chat_main_table_name} WHERE id = :id")
            query.bindValue(":id", id)
            if not query.exec():
                raise Exception(query.lastError().text())
            logging.info(f"{DATABASE_MESSAGE.DATABASE_CHAT_MAIN_ENTRY_SUCCESS} {id}")
        except Exception as e:
            logging.error(f"{DATABASE_MESSAGE.DATABASE_CHAT_MAIN_ENTRY_FAIL} {id}: {e}")
            return False
        return True

    def delete_chat_main(self, id):
        try:
            if not self.delete_chat_detail(id):
                raise Exception(f"Failed to delete chat details for id {id}")
            if not self.delete_chat_main_entry(id):
                raise Exception(f"Failed to delete chat main entry for id {id}")
        except Exception as e:
            logging.error(f"Error deleting chat main for id {id}: {e}")
            return False
        return True

    def get_all_chat_main_list(self):
        query = QSqlQuery()
        query.prepare(f"SELECT * FROM {self.chat_main_table_name} ORDER BY created_at DESC")
        try:
            if query.exec():
                results = []
                while query.next():
                    id = query.value(0)
                    title = query.value(1)
                    created_at = query.value(2)
                    results.append({"id": id, "title": title, "created_at": created_at})
                return results
        except Exception as e:
            print(
                f"{DATABASE_MESSAGE.DATABASE_RETRIEVE_DATA_FAIL} {self.chat_main_table_name}: {e}"
            )
        return []

    _CHAT_DETAIL_EXTRA_COLUMNS: ClassVar[dict[str, str]] = {
        "input_tokens": "INTEGER",
        "output_tokens": "INTEGER",
        "reasoning_tokens": "INTEGER",
        "total_tokens": "INTEGER",
        "workers": "TEXT",
    }

    def create_chat_detail(self, chat_main_id):
        query = QSqlQuery()
        chat_detail_table = f"{self.chat_detail_table_name}_{chat_main_id}"
        query_string = f"""
          CREATE TABLE IF NOT EXISTS {chat_detail_table}
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_main_id INTEGER,
                chat_type TEXT,
                chat_model TEXT,
                chat TEXT,
                elapsed_time TEXT,
                finish_reason TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                reasoning_tokens INTEGER,
                total_tokens INTEGER,
                workers TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(chat_main_id) REFERENCES {self.chat_main_table_name}(id) ON DELETE CASCADE
            )
         """
        try:
            query.exec(query_string)
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_CHAT_DETAIL_CREATE_TABLE_ERROR} {chat_main_id}: {e}")

    def _ensure_chat_detail_columns(self, chat_main_id):
        """Add any missing columns (input_tokens, etc.) to an existing chat-detail table via ALTER."""
        chat_detail_table = f"{self.chat_detail_table_name}_{chat_main_id}"
        info = QSqlQuery()
        if not info.exec(f"PRAGMA table_info({chat_detail_table})"):
            return
        existing = set()
        while info.next():
            existing.add(info.value("name"))
        for col, ctype in self._CHAT_DETAIL_EXTRA_COLUMNS.items():
            if col in existing:
                continue
            alter = QSqlQuery()
            try:
                alter.exec(f"ALTER TABLE {chat_detail_table} ADD COLUMN {col} {ctype}")
            except Exception as e:
                print(f"chat_detail migrate error ({col}): {e}")

    def insert_chat_detail(
        self,
        chat_main_id,
        chat_type,
        chat_model,
        chat,
        elapsed_time,
        finish_reason,
        usage=None,
        workers=None,
    ):
        chat_detail_table = f"{self.chat_detail_table_name}_{chat_main_id}"
        self._ensure_chat_detail_columns(chat_main_id)
        usage = usage or {}
        workers_str = ", ".join(workers) if workers else None
        query = QSqlQuery()
        query.prepare(
            f"INSERT INTO {chat_detail_table} "
            f"(chat_main_id, chat_type, chat_model, chat, elapsed_time, finish_reason, "
            f" input_tokens, output_tokens, reasoning_tokens, total_tokens, workers) "
            f" VALUES (:chat_main_id, :chat_type, :chat_model, :chat, :elapsed_time, :finish_reason, "
            f"         :input_tokens, :output_tokens, :reasoning_tokens, :total_tokens, :workers)"
        )
        query.bindValue(":chat_main_id", chat_main_id)
        query.bindValue(":chat_type", chat_type)
        query.bindValue(":chat_model", chat_model)
        query.bindValue(":chat", chat)
        query.bindValue(":elapsed_time", elapsed_time)
        query.bindValue(":finish_reason", finish_reason)
        query.bindValue(":input_tokens", usage.get("input_tokens"))
        query.bindValue(":output_tokens", usage.get("output_tokens"))
        query.bindValue(":reasoning_tokens", usage.get("reasoning_tokens"))
        query.bindValue(":total_tokens", usage.get("total_tokens"))
        query.bindValue(":workers", workers_str)
        try:
            return query.exec()
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_CHAT_DETAIL_INSERT_ERROR} {e}")
            return False

    def delete_chat_detail(self, id):
        try:
            query = QSqlQuery()
            table_name = f"{self.chat_detail_table_name}_{id}"
            query.prepare(f"DROP TABLE IF EXISTS {table_name}")
            if not query.exec():
                raise Exception(query.lastError().text())
            logging.info(f"{DATABASE_MESSAGE.DATABASE_DELETE_TABLE_SUCCESS} {table_name}")
        except Exception as e:
            logging.error(f"{DATABASE_MESSAGE.DATABASE_CHAT_DETAIL_DELETE_ERROR} {id}: {e}")
            return False
        return True

    def get_all_chat_details_list(self, chat_main_id):
        chat_detail_table = f"{self.chat_detail_table_name}_{chat_main_id}"
        self._ensure_chat_detail_columns(chat_main_id)
        query = QSqlQuery()
        query.prepare(f"SELECT * FROM {chat_detail_table}")

        try:
            if not query.exec():
                print(
                    f"{DATABASE_MESSAGE.DATABASE_CHAT_DETAIL_FETCH_ERROR} {chat_main_id}: {query.lastError().text()}"
                )
                return []
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_EXECUTE_QUERY_ERROR} {e}")
            return []

        chat_details_list = []
        while query.next():
            chat_detail = {
                "id": query.value("id"),
                "chat_main_id": query.value("chat_main_id"),
                "chat_type": query.value("chat_type"),
                "chat_model": query.value("chat_model"),
                "chat": query.value("chat"),
                "elapsed_time": query.value("elapsed_time"),
                "finish_reason": query.value("finish_reason"),
                "input_tokens": query.value("input_tokens"),
                "output_tokens": query.value("output_tokens"),
                "reasoning_tokens": query.value("reasoning_tokens"),
                "total_tokens": query.value("total_tokens"),
                "workers": query.value("workers"),
                "created_at": query.value("created_at"),
            }
            chat_details_list.append(chat_detail)

        return chat_details_list

    def create_prompt_table(self, table_name):
        """Create a prompt table with the given name"""
        query = QSqlQuery()
        query_string = f"""
                        CREATE TABLE IF NOT EXISTS {table_name}
                         (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT NOT NULL,
                            prompt TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                        )
                        """
        try:
            query.exec(query_string)
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_PROMPT_CREATE_TABLE_ERROR} {e}")

    def add_prompt(self, title, prompt):
        query = QSqlQuery()
        query_string = f"""
                        INSERT INTO {self.prompt_table_name} (title, prompt)
                        VALUES (:title, :prompt)
                        """
        try:
            query.prepare(query_string)
            query.bindValue(":title", title)
            query.bindValue(":prompt", prompt)
            if not query.exec():
                raise Exception(query.lastError().text())
            return query.lastInsertId()
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_PROMPT_ADD_ERROR} {e}")
        return None

    def update_prompt(self, id, title, prompt):
        query = QSqlQuery()
        query_string = f"""
                        UPDATE {self.prompt_table_name}
                        SET title = :title, prompt = :prompt
                        WHERE id = :id
                        """
        try:
            query.prepare(query_string)
            query.bindValue(":title", title)
            query.bindValue(":prompt", prompt)
            query.bindValue(":id", id)
            if not query.exec():
                raise Exception(query.lastError().text())
            return True
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_PROMPT_UPDATE_ERROR} {e}")
        return False

    def delete_prompt(self, id):
        query = QSqlQuery()
        query_string = f"""
                        DELETE FROM {self.prompt_table_name}
                        WHERE id = :id
                        """
        try:
            query.prepare(query_string)
            query.bindValue(":id", id)
            if not query.exec():
                raise Exception(query.lastError().text())
            logging.info(f"{DATABASE_MESSAGE.DATABASE_PROMPT_DELETE_SUCCESS} {id}")
            return True
        except Exception as e:
            logging.error(f"{DATABASE_MESSAGE.DATABASE_PROMPT_DELETE_FAIL} {id}: {e}")
        return False

    def create_agent_main(self):
        query = QSqlQuery()
        query_string = f"""
                        CREATE TABLE IF NOT EXISTS {self.agent_main_table_name}
                         (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                        )
                        """
        try:
            query.exec(query_string)
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_AGENT_CREATE_TABLE_ERROR} {e}")

    def add_agent_main(self, title):
        query = QSqlQuery()
        query.prepare(f"INSERT INTO {self.agent_main_table_name} (title) VALUES (:title)")
        query.bindValue(":title", title)
        try:
            if query.exec():
                agent_main_id = query.lastInsertId()
                self.create_agent_detail(agent_main_id)
                return agent_main_id
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_AGENT_ADD_ERROR} {e}")
        return None

    def update_agent_main(self, id, title):
        query = QSqlQuery()
        query.prepare(f"UPDATE {self.agent_main_table_name} SET title = :title WHERE id = :id")
        query.bindValue(":title", title)
        query.bindValue(":id", id)
        try:
            if query.exec():
                return True
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_AGENT_UPDATE_ERROR} {e}")
        return False

    def delete_agent_main_entry(self, id):
        try:
            query = QSqlQuery()
            query.prepare(f"DELETE FROM {self.agent_main_table_name} WHERE id = :id")
            query.bindValue(":id", id)
            if not query.exec():
                raise Exception(query.lastError().text())
            logging.info(f"{DATABASE_MESSAGE.DATABASE_AGENT_MAIN_ENTRY_SUCCESS} {id}")
        except Exception as e:
            logging.error(f"{DATABASE_MESSAGE.DATABASE_AGENT_MAIN_ENTRY_FAIL} {id}: {e}")
            return False
        return True

    def delete_agent_main(self, id):
        try:
            if not self.delete_agent_detail(id):
                raise Exception(f"Failed to delete agent details for id {id}")
            if not self.delete_agent_main_entry(id):
                raise Exception(f"Failed to delete agent main entry for id {id}")
        except Exception as e:
            logging.error(f"Error deleting agent main for id {id}: {e}")
            return False
        return True

    def get_all_agent_main_list(self):
        query = QSqlQuery()
        query.prepare(f"SELECT * FROM {self.agent_main_table_name} ORDER BY created_at DESC")
        try:
            if query.exec():
                results = []
                while query.next():
                    id = query.value(0)
                    title = query.value(1)
                    created_at = query.value(2)
                    results.append({"id": id, "title": title, "created_at": created_at})
                return results
        except Exception as e:
            print(
                f"{DATABASE_MESSAGE.DATABASE_RETRIEVE_DATA_FAIL} {self.agent_main_table_name}: {e}"
            )
        return []

    def create_agent_detail(self, agent_main_id):
        query = QSqlQuery()
        agent_detail_table = f"{self.agent_detail_table_name}_{agent_main_id}"
        query_string = f"""
          CREATE TABLE IF NOT EXISTS {agent_detail_table}
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_main_id INTEGER,
                agent_type TEXT,
                agent_model TEXT,
                agent TEXT,
                elapsed_time TEXT,
                finish_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(agent_main_id) REFERENCES {self.agent_main_table_name}(id) ON DELETE CASCADE
            )
         """
        try:
            query.exec(query_string)
        except Exception as e:
            print(
                f"{DATABASE_MESSAGE.DATABASE_AGENT_DETAIL_CREATE_TABLE_ERROR} {agent_main_id}: {e}"
            )

    def insert_agent_detail(
        self, agent_main_id, agent_type, agent_model, agent, elapsed_time, finish_reason
    ):
        agent_detail_table = f"{self.agent_detail_table_name}_{agent_main_id}"
        query = QSqlQuery()
        query.prepare(
            f"INSERT INTO {agent_detail_table} (agent_main_id, agent_type, agent_model, agent, elapsed_time, finish_reason) "
            f" VALUES (:agent_main_id, :agent_type, :agent_model, :agent, :elapsed_time, :finish_reason)"
        )
        query.bindValue(":agent_main_id", agent_main_id)
        query.bindValue(":agent_type", agent_type)
        query.bindValue(":agent_model", agent_model)
        query.bindValue(":agent", agent)
        query.bindValue(":elapsed_time", elapsed_time)
        query.bindValue(":finish_reason", finish_reason)
        try:
            return query.exec()
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_AGENT_DETAIL_INSERT_ERROR} {e}")
            return False

    def delete_agent_detail(self, id):
        try:
            query = QSqlQuery()
            table_name = f"{self.agent_detail_table_name}_{id}"
            query.prepare(f"DROP TABLE IF EXISTS {table_name}")
            if not query.exec():
                raise Exception(query.lastError().text())
            logging.info(f"{DATABASE_MESSAGE.DATABASE_DELETE_TABLE_SUCCESS} {table_name}")
        except Exception as e:
            logging.error(f"{DATABASE_MESSAGE.DATABASE_AGENT_DETAIL_DELETE_ERROR} {id}: {e}")
            return False
        return True

    def get_all_agent_details_list(self, agent_main_id):
        agent_detail_table = f"{self.agent_detail_table_name}_{agent_main_id}"
        query = QSqlQuery()
        query.prepare(f"SELECT * FROM {agent_detail_table}")

        try:
            if not query.exec():
                print(
                    f"{DATABASE_MESSAGE.DATABASE_AGENT_DETAIL_FETCH_ERROR} {agent_main_id}: {query.lastError().text()}"
                )
                return []
        except Exception as e:
            print(f"{DATABASE_MESSAGE.DATABASE_EXECUTE_QUERY_ERROR} {e}")
            return []

        agent_details_list = []
        while query.next():
            agent_detail = {
                "id": query.value("id"),
                "agent_main_id": query.value("agent_main_id"),
                "agent_type": query.value("agent_type"),
                "agent_model": query.value("agent_model"),
                "agent": query.value("agent"),
                "elapsed_time": query.value("elapsed_time"),
                "finish_reason": query.value("finish_reason"),
                "created_at": query.value("created_at"),
            }
            agent_details_list.append(agent_detail)

        return agent_details_list
