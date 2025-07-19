"""
Модуль для работы с базой данных SQLite.
"""
import sqlite3
import logging
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager
from pathlib import Path

from app.utils.paths import PROJECT_ROOT

from app.execution.models.db_models import User

from app.exceptions.db_exceptions import UserNotFoundException, CardNotFoundException
from app.exceptions.base_exceptions import DataBaseException

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Менеджер для работы с базой данных SQLite."""
    
    def __init__(self):
        self.db_path: Path = PROJECT_ROOT.parent / "user_cards.db"
        self._init_database()
    
    def _init_database(self):
        """Инициализация базы данных и создание таблиц."""
        try:
            with self._get_connection() as conn:
                self._create_tables(conn)
                self._create_indexes(conn)
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise DataBaseException(f"Database initialization failed: {e}")
    
    @contextmanager
    def _get_connection(self):
        """Контекстный менеджер для получения подключения к БД."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database transaction failed: {e}")
            raise
        finally:
            conn.close()
    
    def _create_tables(self, conn: sqlite3.Connection):
        """Создание таблиц в базе данных."""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE,
                image TEXT
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS cards (
                card_id TEXT,
                user_id TEXT NOT NULL,
                image TEXT NOT NULL,
                name TEXT,
                manga_name TEXT,
                data_id INTEGER,
                lock BOOLEAN,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (card_id, user_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
    
    def _create_indexes(self, conn: sqlite3.Connection):
        """Создание индексов для оптимизации запросов."""
        indexes = [
            # Индекс для быстрого поиска карточек по пользователю
            'CREATE INDEX IF NOT EXISTS idx_cards_user_id ON cards(user_id)',

            # Индекс для быстрого поиска карточек по card_id
            'CREATE INDEX IF NOT EXISTS idx_cards_card_id ON cards(card_id)',
        ]

        for index_sql in indexes:
            conn.execute(index_sql)

        conn.commit()
    
    def _fetch_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Выполнение запроса с возвращением одной записи."""
        try:
            with self._get_connection() as conn:
                return conn.execute(query, params).fetchone()
        except Exception as e:
            logger.error(f"Failed to fetch one record: {e}")
            raise DataBaseException(f"Database query failed: {e}")
    
    def _fetch_all(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Выполнение запроса с возвращением всех записей."""
        try:
            with self._get_connection() as conn:
                return conn.execute(query, params).fetchall()
        except Exception as e:
            logger.error(f"Failed to fetch records: {e}")
            raise DataBaseException(f"Database query failed: {e}")
    
    def _execute_query(self, query: str, params: tuple = ()) -> int:
        """Выполнение запроса без возвращения данных."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            raise DataBaseException(f"Database query failed: {e}")


class UserCardDB(DatabaseManager):
    """Класс для работы с карточками пользователей."""
    
    def _check_user_exists(self, user_id: str) -> bool:
        """Проверка существования пользователя."""
        result = self._fetch_one(
            'SELECT 1 FROM users WHERE user_id = ? LIMIT 1', 
            (user_id,)
        )
        return result is not None
    
    def _check_card_exists(self, user_id: str, card_id: str) -> bool:
        """Проверка существования карточки у пользователя."""
        result = self._fetch_one(
            'SELECT 1 FROM cards WHERE user_id = ? AND card_id = ? LIMIT 1',
            (user_id, card_id)
        )
        return result is not None
    
    def _validate_user_exists(self, user_id: str):
        """Валидация существования пользователя с выбросом исключения."""
        if not self._check_user_exists(user_id):
            raise UserNotFoundException(user_id)
    
    def _validate_card_exists(self, user_id: str, card_id: str):
        """Валидация существования карточки с выбросом исключения."""
        if not self._check_card_exists(user_id, card_id):
            raise CardNotFoundException(user_id, card_id)
    
    def add_user(self, user_id: str, username: Optional[str] = None, image: Optional[str] = None) -> int:
        """Удобная обертка над add_users для одного пользователя."""
        user = User(user_id=user_id, username=username, image=image)
        self.add_users([user])
        return user_id

    def add_users(self, users: List[User]) -> int:
        if not users:
            return 0

        try:
            prepared = [
                (
                    u.user_id,
                    u.username,
                    u.image
                )
                for u in users
            ]

            with self._get_connection() as conn:
                conn.executemany(
                    '''
                    INSERT INTO users (user_id, username, image)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        username = COALESCE(excluded.username, users.username),
                        image = COALESCE(excluded.image, users.image)
                    ''',
                    prepared
                )
                conn.commit()
                return conn.total_changes

        except Exception as e:
            logger.error(f"Failed to add or update users: {e}")
            raise DataBaseException(f"Failed to add or update users: {e}")

    def add_card(
        self,
        card_id: str,
        user_id: str,
        image: str,
        name: Optional[str] = None,
        manga_name: Optional[str] = None,
        lock: Optional[bool] = None,
        data_id: Optional[int] = None,
    ) -> str:
        """Добавление карточки пользователя."""
        self._validate_user_exists(user_id)
        
        try:
            query = '''
                INSERT OR IGNORE INTO cards 
                (card_id, user_id, image, name, manga_name, data_id, lock) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            '''
            params = (card_id, user_id, image, name, manga_name, data_id, lock)
            
            self._execute_query(query, params)
            logger.debug(f"Card {card_id} added for user {user_id}")
            return card_id
            
        except Exception as e:
            logger.error(f"Failed to add card {card_id} for user {user_id}: {e}")
            raise DataBaseException(f"Failed to add card: {e}")
        
    def delete_cards_batch(self, cards_to_delete: List[Dict[str, int]]) -> int:
        """
        Пакетное удаление карточек.
        cards_to_delete — список словарей с ключами 'user_id' и 'card_id'.
        Возвращает количество удалённых записей.
        """
        if not cards_to_delete:
            return 0

        # Подготовка параметров для SQL (кортежи (user_id, card_id))
        params = [(card['user_id'], card['card_id']) for card in cards_to_delete]

        try:
            with self._get_connection() as conn:
                # SQLite не поддерживает составные IN напрямую, используем цикл DELETE
                total_deleted = 0
                for user_id, card_id in params:
                    cursor = conn.execute(
                        'DELETE FROM cards WHERE user_id = ? AND card_id = ?',
                        (user_id, card_id)
                    )
                    total_deleted += cursor.rowcount
                conn.commit()

            logger.info(f"Batch deleted {total_deleted} cards")
            return total_deleted

        except Exception as e:
            logger.error(f"Failed batch delete cards: {e}")
            raise DataBaseException(f"Batch delete failed: {e}")
    
    def update_card_partial(self, user_id: str, card_id: str, **kwargs) -> None:
        """Частичное обновление карточки."""
        self._validate_user_exists(user_id)
        self._validate_card_exists(user_id, card_id)
        
        allowed_fields = {'image', 'name', 'manga_name', 'data_id', "lock"}
        fields = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
        
        if not fields:
            raise ValueError("No valid fields provided for update")
        
        try:
            set_clause = ', '.join(f"{k} = ?" for k in fields)
            values = list(fields.values()) + [user_id, card_id]
            
            query = f'UPDATE cards SET {set_clause} WHERE user_id = ? AND card_id = ?'
            affected_rows = self._execute_query(query, tuple(values))
            
            if affected_rows == 0:
                logger.ing(f"No rows updated for card {card_id}, user {user_id}")
            else:
                logger.info(f"Card {card_id} updated for user {user_id}")
                
        except Exception as e:
            logger.error(f"Failed to update card {card_id} for user {user_id}: {e}")
            raise DataBaseException(f"Failed to update card: {e}")
        
    def update_user_partial(self, user_id: str, **kwargs) -> None:
        """Частичное обновление данных пользователя."""
        self._validate_user_exists(user_id)

        allowed_fields = {'username', 'image'}
        fields = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}

        if not fields:
            raise ValueError("No valid fields provided for update")

        try:
            set_clause = ', '.join(f"{k} = ?" for k in fields)
            values = list(fields.values()) + [user_id]

            query = f'UPDATE users SET {set_clause} WHERE user_id = ?'
            affected_rows = self._execute_query(query, tuple(values))

            if affected_rows == 0:
                logger.ing(f"No rows updated for user {user_id}")
            else:
                logger.info(f"User {user_id} updated with fields: {list(fields.keys())}")

        except Exception as e:
            logger.error(f"Failed to update user {user_id}: {e}")
            raise DataBaseException(f"Failed to update user: {e}")

    def get_cards_by_user(self, user: User) -> List[Dict[str, Any]]:
        """Получение всех карточек пользователя."""
        user_id = user.user_id
        self._validate_user_exists(user_id)
        
        query = '''
            SELECT card_id, image, name, manga_name, data_id, lock, created_at
            FROM cards
            WHERE user_id = ?
            ORDER BY created_at DESC
        '''
        
        rows = self._fetch_all(query, (user_id,))
        return [dict(row) for row in rows]
    
    def get_specific_card_for_users(
        self,
        users: List[User],
        card_id: str
    ) -> Tuple[Dict[str, Optional[Dict[str, Any]]], List[User]]:
        """Получение определенной карточки для списка пользователей и возвращение недостающих как User."""
        if not users:
            return {}, []

        user_ids = [user.user_id for user in users]
        placeholders = ','.join('?' * len(user_ids))
        
        # Получаем только существующих пользователей по user_id
        existing_query = f'''
            SELECT user_id FROM users WHERE user_id IN ({placeholders})
        '''
        existing_rows = self._fetch_all(existing_query, tuple(user_ids))
        existing_ids = {row['user_id'] for row in existing_rows}
        
        # missing_users = те, чьи user_id отсутствуют в таблице users
        missing_users = [user for user in users if user.user_id not in existing_ids]

        # Инициализируем результат словарём user_id -> None
        result: Dict[int, Optional[Dict[str, Any]]] = {uid: None for uid in user_ids}

        # Получаем карточки с нужным card_id
        if existing_ids:
            card_placeholders = ','.join('?' * len(existing_ids))
            card_query = f'''
                SELECT user_id, card_id, image, name, manga_name, data_id, lock, created_at
                FROM cards
                WHERE user_id IN ({card_placeholders}) AND card_id = ?
            '''
            card_rows = self._fetch_all(card_query, tuple(existing_ids) + (card_id,))

            for row in card_rows:
                result[row['user_id']] = dict(row)

        return result, missing_users
    
    def add_users_from_payload(self, users: List[Dict[str, Any]]) -> int:
        """
        Добавление пользователей из словарей.
        """

        user_objs = [
            User(
                user_id=u.get("user_id"),
                username=u.get("username"),
                image=u.get("image")
            )
            for u in users if u.get("user_id") is not None
        ]

        return self.add_users(user_objs)
    
    def add_cards_from_payload(self, user: User, payload: List[Dict[str, Any]]):
        """Быстрое добавление карточек из полученных данных."""
        user_id = user.user_id
        self._validate_user_exists(user_id)

        valid_entries = []
        cards_skipped = 0

        for entry in payload:
            card_id = entry.get("card_id")
            image = entry.get("image", "")

            if not card_id or not image:
                cards_skipped += 1
                continue

            valid_entries.append((
                card_id,
                user_id,
                image,
                entry.get("name", ""),
                entry.get("manga_name", ""),
                entry.get("data_id"),
                entry.get("lock")
            ))

        cards_added = 0

        if valid_entries:
            try:
                with self._get_connection() as conn:
                    conn.executemany('''
                        INSERT OR IGNORE INTO cards
                        (card_id, user_id, image, name, manga_name, data_id, lock)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', valid_entries)
                    conn.commit()
                    cards_added = conn.total_changes
            except Exception as e:
                logger.error(f"Batch insert failed for user {user_id}: {e}")
                raise DataBaseException(f"Failed to process cards payload: {e}")

        logger.info(f"Added {cards_added} cards, skipped {cards_skipped} for user {user_id}")