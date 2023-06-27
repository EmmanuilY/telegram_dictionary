from contextlib import asynccontextmanager
from config.config import settings
from loguru import logger
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

    async def add_user(self, user_id: str, user_name: str) -> str:
        result = await self._execute(
            """
                INSERT INTO users(telegram_id, name) 
                VALUES ($1, $2)
                ON CONFLICT (telegram_id) DO NOTHING
            """,
            user_id, user_name
        )
        return 'exists' if result == 'INSERT 0 0' else 'register_user'

    async def add_term(self, term: str, definition: str, type: str, telegram_id: str) -> bool:
        # add term to terms table and add to user_terms_progress user_id and term_id
        response = await self._execute(
            """
            WITH ins1 AS (
                INSERT INTO terms (term, definition, type) 
                VALUES ($1, $2, $3)
                RETURNING term_id
            ), 
            ins2 AS (
                SELECT user_id FROM users WHERE telegram_id = $4
            )
            INSERT INTO user_terms_progress (term_id, user_id) 
            SELECT ins1.term_id, ins2.user_id FROM ins1, ins2
            """,
            term, definition, type, telegram_id
        )

        if response == 'INSERT 0 0':
            logger.debug(f"Пользователь не найден или что-то другое {response}")
            return False

        else:
            return True

    async def change_learn_type(self, telegram_id, words: list) -> dict | str:

        request_to_db = await self._execute(
            """
           UPDATE user_terms_progress
            SET number_of_repetitions = number_of_repetitions + 1, learning = CASE
                           WHEN number_of_repetitions < 7 THEN 'repeat'::step_of_learning
                           ELSE 'learned'::step_of_learning
                       END
            FROM users, terms
            WHERE user_terms_progress.user_id = users.user_id
            AND user_terms_progress.term_id = terms.term_id
            AND users.telegram_id = $1
            AND terms.term = ANY($2::varchar[])
            """,
            telegram_id, words
        )

        return f' request_to_db {request_to_db}'

    async def get_terms_progress(self, telegram_id: str) -> dict | str:

        terms = await self._fetch(
            """
           SELECT learning, COUNT(*) 
           FROM user_terms_progress u JOIN users u2 on u.user_id=u2.user_id
           WHERE telegram_id = $1 
           group by learning;

            """,
            telegram_id
        )
        progress_dict = {"learning": 0, "repeat": 0, "learned": 0}
        progress_dict.update(dict(terms))
        return progress_dict

    async def get_user_terms_and_definitions(self, telegram_id: str, progress: str, term_type: str, ) -> dict | str:

        terms = await self._fetch(
            """
          SELECT term, definition
          FROM terms t JOIN user_terms_progress ut ON t.term_id=ut.term_id 
          JOIN users u ON u.user_id = ut.user_id
          WHERE telegram_id = $1 AND learning = $2 AND type=$3;

            """,
            telegram_id, progress, term_type
        )
        progress = {}
        progress.update(dict(terms))
        return progress

    async def get_count_user_words(self, telegram_id: str, learning: str) -> dict:

        terms_count = await self._fetch(
            """
       SELECT type, COUNT(*) 
           FROM user_terms_progress u JOIN users u2 on u.user_id=u2.user_id join terms t on u.term_id=t.term_id
           WHERE  telegram_id = $1 and learning = $2 group by type

            """,
            telegram_id, learning
        )
        return terms_count

    async def get_count_user_words_by_type(self, telegram_id: str, term_type: str) -> dict:

        terms_count = await self._fetch(
            """
       SELECT learning, COUNT(*) 
           FROM user_terms_progress u JOIN users u2 on u.user_id=u2.user_id join terms t on u.term_id=t.term_id
           WHERE  telegram_id = $1 and type = $2 group by learning

            """,
            telegram_id, term_type
        )
        progress = {'repeat': 0, 'learned': 0, 'learning': 0}
        progress.update(dict(terms_count))
        logger.debug(f"{progress}")
        return progress if terms_count else False

    async def get_count_repeat_words_types(self, telegram_id: str, term_type: str, ) -> dict | str:

        terms_type_count = await self._fetch(
            """
           SELECT number_of_repetitions, COUNT(*) 
           FROM user_terms_progress u JOIN users u2 on u.user_id=u2.user_id join terms t on u.term_id=t.term_id
           WHERE   telegram_id = $1 and learning = 'repeat' and type = $2 group by number_of_repetitions

            """,
            telegram_id, term_type
        )
        logger.debug(f'get_count_repeat_words_types{terms_type_count}')
        return terms_type_count

    async def get_words_to_train(self, user_id, type_of_words, number_of_words, type_of_learning) -> dict | bool:

        words = await self._fetch(
            """
        SELECT t.term, t.definition
            FROM terms t
            JOIN user_terms_progress utp ON t.term_id = utp.term_id
            JOIN USERS u on utp.user_id=u.user_id
            WHERE u.telegram_id =$1 AND t.type = $2 AND utp.learning = $4
            ORDER BY RANDOM()
            LIMIT $3

            """,
            user_id, type_of_words, number_of_words, type_of_learning
        )

        words_dict = {word: definition for word, definition in words}
        return words_dict

    async def repeat_learned_words(self, telegram_id, terms: list) -> dict | str:

        request_to_db = await self._execute(
            """
           UPDATE user_terms_progress
            SET number_of_repetitions = 4, learning = 'repeat' 
            FROM users, terms
            WHERE user_terms_progress.user_id = users.user_id
            AND user_terms_progress.term_id = terms.term_id
            AND users.telegram_id = $1
            AND terms.term = ANY($2::varchar[])
            """,
            telegram_id, terms
        )

        return f' request_to_db {request_to_db}'

db = DB()