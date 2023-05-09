from contextlib import asynccontextmanager
from config.config import settings

import asyncpg


class DB:
    def __init__(self):
        self.connection = None

    @asynccontextmanager
    async def _connect(self):
        conn = await asyncpg.connect(
            user=settings.USER,
            password=settings.PASSWORD,
            database=settings.DATABASE,
            host=settings.HOST,
        )
        try:
            yield conn
        finally:
            await conn.close()

    async def _fetch(self, query, *params):
        async with self._connect() as connection:
            return await connection.fetch(query, *params)

    async def _fetchrow(self, query, *params):
        async with self._connect() as connection:
            return await connection.fetchrow(query, *params)

    async def _execute(self, query, *params):
        async with self._connect() as connection:
            return await connection.execute(query, *params)

    async def _fetchval(self, query, *params):
        async with self._connect() as connection:
            return await connection.fetchval(query, *params)

    async def _fetch(self, query, *params):
        async with self._connect() as connection:
            return await connection.fetch(query, *params)

    async def add_user(
            self, user_id: str, user_name: str) -> str:
        query = await self._fetchrow(
            """
                SELECT EXISTS (
                    SELECT 1
                    FROM users
                    WHERE telegram_id = $1 
                )
            """,
            user_id
        )
        if query.get("exists"):
            return 'exists'

        await self._execute(
            """
                INSERT INTO users(telegram_id, name) VALUES ($1, $2)
            """,
            user_id, user_name)
        return 'ok'

    async def add_term(self, term: str, definition: str, type: str, telegram_id: str) -> str:
        try:
            # Получаем user_id по telegram_id
            user_id = await self._fetchval(
                """
                SELECT user_id FROM users WHERE telegram_id = $1
                """,
                telegram_id
            )

            if not user_id:
                # Если пользователь не найден, вернуть сообщение об ошибке
                return "Пользователь не найден"

            # Добавляем термин в таблицу terms, если его там нет
            term_id = await self._fetchval(
                """
                INSERT INTO terms (term, definition, type) VALUES ($1, $2, $3)
                RETURNING term_id
                """,
                term, definition, type
            )

            # Добавляем запись в таблицу user_terms_progress
            await self._execute(
                """
                INSERT INTO user_terms_progress (term_id, user_id) VALUES ($1, $2)
                """,
                term_id, user_id
            )

            return 'good'
        except Exception as e:
            return f'{e}'

    async def get_term(self, telegram_id: str, term_type: str, learn='learning') -> dict | str:
        try:
            terms = await self._fetch(
                """
                SELECT t.term, t.definition
                FROM terms t
                JOIN user_terms_progress utp ON t.term_id = utp.term_id
                JOIN USERS u on utp.user_id=u.user_id
                WHERE u.telegram_id =$1 AND t.type = $2 AND utp.learning = $3
                LIMIT 4
                """,
                telegram_id, term_type, learn
            )

            # Преобразование списка кортежей в словарь
            terms_dict = {term: definition for term, definition in terms}
            return terms_dict

        except Exception as e:
            return f'{e}'

    async def change_learn_type (self, telegram_id, terms: list,  change_learn='repeat') -> dict | str:
        try:
            terms = await self._execute(
                """
               UPDATE user_terms_progress
                SET number_of_repetitions = number_of_repetitions + 1, learning = $3
                FROM users, terms
                WHERE user_terms_progress.user_id = users.user_id
                AND user_terms_progress.term_id = terms.term_id
                AND users.telegram_id = $1
                AND terms.term = ANY($2::varchar[])
                """,
                telegram_id, terms, change_learn
            )

            # Преобразование списка кортежей в словарь
            return f' top {terms}'

        except Exception as e:
            return f'{e}'
