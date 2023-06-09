import random
import re
from functools import partial
from abc import abstractmethod
from aiogram import exceptions as aiogram_exceptions
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message
from loguru import logger

from keyboards.simple_row import make_row_keyboard, start_buttons

from db.db import db



AVAILABLE_TERM_TYPES = ["term", "english_word"]
NUMBER_OF_WORDS = ["4", "6", "8", "10"]
NUMBER_TRANSLATION = {
    1: "одно повторение",
    2: "два повторения",
    3: "три повторения",
    4: "четыре повторения",
    5: "пять повторений",
    6: "шесть повторений",
    7: "семь повторений",
}


class BaseTrainings:

    def __init__(self, training_state: StatesGroup):
        self.training_state = training_state
        self.db = db
        self.available_term_types = AVAILABLE_TERM_TYPES
        self.number_of_words = NUMBER_OF_WORDS

    @staticmethod
    async def send_message_with_keyboard(message: Message, text: str, keyboard_options: list):
        await message.answer(text=text, reply_markup=make_row_keyboard(keyboard_options))

    @staticmethod
    def escape_special_characters(text: str) -> str:
        return re.sub(r"(-|\(|\)|`)", r"\\\1", text)

    async def check_len_words(self, message, words: dict, chosen_number: int) -> bool:
        if not words:
            await message.answer(
                text="Произошла супер непредвиденная ошибка, напишите админу"
            )
            return False

        if len(words.keys()) < chosen_number:
            await self.send_message_with_keyboard(
                message,
                "у вас недостаточно слов, подучите еще",
                ["/learn_words", "/add_terms", "/check_progress"],
            )
            return False

        return True

    async def sending_words_with_invisible_definitions(self, message, words: dict) -> None:
        await message.answer(text="Ниже слова")
        for word, definition in words.items():
            word = self.escape_special_characters(word)
            definition = self.escape_special_characters(definition)
            try:
                await message.answer(
                    text=f"{word}  \-  ||{definition}||", parse_mode="MarkdownV2"
                )
            except aiogram_exceptions.TelegramBadRequest as error:
                logger.error(
                    f"{error}, слово {word} и определение {definition} выдали ошибку при словаре {words}"
                )
                raise error

    async def send_term_and_definitions(self, message: Message, state: FSMContext, term_key: str):
        """term here is a name of word or definition.
        on first_step term is a word and answer is a definition,
        on second_step and third_step - term is definition and answer is a word
        """
        user_data = await state.get_data()
        terms_dict, answers_list = self._get_terms_dict_and_answers(user_data, term_key)
        if not answers_list:
            await self.send_message_with_keyboard(
                message, "Этап завершен! Вы молодец!", ["перейти на следующий этап"]
            )
            next_state = user_data.get("next_state")
            await state.set_state(next_state)
            return
        current_state = user_data.get("current_state")
        term, correct_answer, other_answers = self._get_term_and_answers(
            terms_dict, answers_list, term_key
        )
        random_answers = random.sample(other_answers, 3)
        answers = [correct_answer, *random_answers]
        random.shuffle(answers)
        await self._send_or_remove_keyboard(message, answers, term, current_state)
        await state.update_data(chosen_term=term, correct_answer=correct_answer)

    @staticmethod
    def _get_terms_dict_and_answers(user_data: dict, term_key: str):
        terms_dict = user_data.get("terms", {})
        answers_list = user_data[term_key]
        return terms_dict, answers_list

    def _get_term_and_answers(self, terms_dict: dict, answers_list: list, term_key: str):
        term = answers_list.pop(0)
        correct_answer, other_answers = self._get_words_or_definitions_based_on_term_key(
            terms_dict, term, term_key
        )
        return term, correct_answer, other_answers

    @staticmethod
    def _get_words_or_definitions_based_on_term_key(
            terms_dict: dict, term: str, term_key: str
    ) -> [str, list]:
        if term_key == "words":
            current_definition = terms_dict[term]
            other_definitions = [
                definition
                for word, definition in terms_dict.items()
                if definition != current_definition
            ]
            return current_definition, other_definitions

        current_word = {word: definition for definition, word in terms_dict.items()}[term]
        other_words = [
            word for word, definition in terms_dict.items() if word != current_word
        ]
        return current_word, other_words

    async def _send_or_remove_keyboard(
            self, message: Message, answers: list, term: str, current_state: str
    ):
        if current_state == "third_step":
            await message.answer(text=term, ReplyKeyboardRemove=True)
        else:
            await self.send_message_with_keyboard(message, term, answers)

    @staticmethod
    async def check_user_answer(
            message: Message, state: FSMContext, send_term_and_definitions_function
    ):
        user_data = await state.get_data()
        correct_answer = user_data["correct_answer"].strip().lower()
        user_answer = message.text.strip().lower()
        if user_answer == correct_answer or (
                len(user_answer) > 10 and user_answer[:-3] in correct_answer
        ):
            await message.answer(text="Правильно!")
            await send_term_and_definitions_function()
        else:
            await message.answer(text="Неправильно! Попробуй еще раз.")

    @staticmethod
    async def shuffle_and_update_state(
            state: FSMContext, term_key: str, next_state: State, current_state: str
    ):
        user_data = await state.get_data()
        terms = user_data.get("terms", {})
        words_or_definitions = (
            list(terms.keys()) if term_key == "words" else list(terms.values())
        )
        random.shuffle(words_or_definitions)
        user_data["term_key"] = term_key
        user_data[term_key] = words_or_definitions
        user_data["next_state"] = next_state
        user_data["current_state"] = current_state
        await state.update_data(user_data)

    async def get_started_and_choosing_term_type(self, text, message, state, type_of_learning):
        """
            get from db all user's words depends on learning type=repeat group by types and sending them to user
        """
        types_and_counts = await self.db.get_count_user_words(
            telegram_id=str(message.from_user.id), learning=type_of_learning
        )
        for type_and_count in types_and_counts:
            text += f"{type_and_count['type']}: {type_and_count['count']}\n"
        await message.answer(text=text)
        await self.send_message_with_keyboard(
            message, "Выберите тип слов:", self.available_term_types
        )
        await state.set_state(self.training_state.chosen_type_object)

    async def choosing_count_words(self, text, message, state):
        chosen_type = message.text
        await state.update_data(chosen_type=chosen_type)
        await self.send_message_with_keyboard(
            message, text, self.number_of_words
        )
        await state.set_state(self.training_state.get_words_state)

    async def get_words(self, message, state, type_of_learning):
        """
            get words from db and check if user has enough words to repeat.
            """

        user_data = await state.get_data()
        chosen_type = user_data.get("chosen_type")
        words = await self.db.get_words_to_train(
            user_id=str(message.from_user.id),
            type_of_words=chosen_type,
            number_of_words=int(message.text),
            type_of_learning=type_of_learning,
        )
        if await self.check_len_words(message, words, int(message.text)):
            await self.sending_words_with_invisible_definitions(message, words)
            await state.update_data(terms=words)
            await self.send_message_with_keyboard(message, "Начать?", ["Начать"])
            await state.set_state(self.training_state.first_step)
        else:
            await state.clear()

    async def check_answer_state(self, message, state):
        user_data = await state.get_data()
        term_key = user_data["term_key"]
        send_term_and_definitions_function = partial(
            self.send_term_and_definitions, message, state, term_key
        )
        await self.check_user_answer(message, state, send_term_and_definitions_function)

    async def first_step_state(self, message, state):
        text = 'Сейчас я буду тебе присылать слово, а ты выбирай определение'
        next_state = self.training_state.second_step
        key_type = "words"
        current_step = 'first_step'
        await self.step_logic(message, state, text, next_state, current_step, key_type)

    async def second_step_state(self, message, state):
        text = 'Сейчас я буду тебе присылать определение, а ты выбирай правильное слово'
        next_state = self.training_state.third_step
        key_type = "definitions"
        current_step = 'second_step'
        await self.step_logic(message, state, text, next_state, current_step, key_type)

    async def third_step_state(self, message, state):
        text = 'Сейчас я буду тебе присылать определение, а ты вводи правильное слово'
        next_state = self.training_state.finish
        key_type = "definitions"
        current_step = 'third_step'
        await self.step_logic(message, state, text, next_state, current_step, key_type)

    async def step_logic(self, message: Message, state: FSMContext, text: str, next_state: State, current_state: str,
                         key_type: str):
        await message.answer(text=text)
        await self.shuffle_and_update_state(
            state, key_type, next_state, current_state
        )
        logger.debug(f"{next_state}, {current_state}, {key_type}")
        await self.send_term_and_definitions(message, state, key_type)
        await state.set_state(self.training_state.check_answer)

    async def finish(self, message, state):
        user_data = await state.get_data()
        terms = user_data.get("terms", {})
        learn_terms = list(terms.keys())
        answer = await self.db.change_learn_type(telegram_id=str(message.from_user.id), words=learn_terms)

        await message.answer(
            text=f"а на этом повторение слов окончено {answer}",
            reply_markup=make_row_keyboard(start_buttons),
        )
        await state.clear()


class LearnTraining(BaseTrainings):

    async def get_words(self, message, state, type_of_learning):
        """
            get words from db and check if user has enough words to repeat.
            """
        user_data = await state.get_data()
        chosen_type = user_data.get("chosen_type")
        words = await LearnTraining.db.get_words_to_train(
            user_id=str(message.from_user.id),
            type_of_words=chosen_type,
            number_of_words=int(message.text),
            type_of_learning=type_of_learning,
        )
        if await self.check_len_words(message, words, int(message.text)):
            await self._send_words_and_definitions(message, words)
            await self.send_message_with_keyboard(message, "Нужен cамоповтор?", ["Повтор для себя"])
            await state.update_data(terms=words)
            await state.set_state(self.training_state.pre_learn_part)
        else:
            await state.clear()

    @staticmethod
    async def _send_words_and_definitions(message, words: dict) -> None:
        await message.answer(text="Ниже слова")
        for word, definition in words.items():
            await message.answer(text=f"{word} - {definition}")

    async def pre_learn_part(self, message, state):
        await message.answer(
            text="Ниже слова................................................................................................"
        )
        user_data = await state.get_data()
        words = user_data.get("terms")
        await self.sending_words_with_invisible_definitions(message, words)
        await self.send_message_with_keyboard(message, "Начать?", ["Начать"])
        await state.set_state(self.training_state.first_step)


class RepeatTraining(BaseTrainings):

    def __init__(self, training_state: StatesGroup):
        super().__init__(training_state)
        self.answer_slovarik = NUMBER_TRANSLATION

    @staticmethod
    def get_word_form(count: int) -> str:
        if count == 1:
            return "слово"
        elif 1 < count < 5:
            return "слова"
        else:
            return "слов"

    async def choosing_count_words(self, text: str, message: Message, state: FSMContext) -> None:
        chosen_type = message.text
        await state.update_data(chosen_type=chosen_type)
        records = await self.db.get_count_repeat_words_types(
            telegram_id=str(message.from_user.id), term_type=chosen_type
        )
        for record in records:
            word_form = self.get_word_form(record['count'])
            text += f"{self.answer_slovarik[record['number_of_repetitions']]}:  {record['count']} {word_form}\n"
        await message.answer(text=text)
        await self.send_message_with_keyboard(
            message, 'Выбирете, сколько слов будем повторять:', self.number_of_words
        )

        await state.set_state(self.training_state.get_words_state)


class RepeatLearnedWordsTraining(BaseTrainings):
    """
    add new logic, how we check user answer. If answer is not correct, we add a term to incorrect set
    """

    @staticmethod
    async def check_user_answer(
            message: Message, state: FSMContext, send_term_and_definitions_function
    ):
        user_data = await state.get_data()
        correct_answer = user_data["correct_answer"].strip().lower()
        user_answer = message.text.strip().lower()
        if user_answer == correct_answer or (
                len(user_answer) > 10 and user_answer[:-3] in correct_answer
        ):
            await message.answer(text="Правильно!")
            await send_term_and_definitions_function()
            return

        term_key = user_data["term_key"]
        if term_key == 'words':
            chosen_term = user_data["chosen_term"]
        else:
            chosen_term = correct_answer
        incorrect_terms = user_data.get('incorrect_terms', set())
        logger.debug(f'{incorrect_terms} {chosen_term}')
        incorrect_terms.add(chosen_term)
        await state.update_data(incorrect_terms=incorrect_terms)
        await message.answer(text="Неправильно! Попробуй еще раз.")

    async def finish(self, message, state):
        user_data = await state.get_data()
        incorrect_terms = (user_data.get('incorrect_terms', set()))
        if incorrect_terms:
            await self.db.repeat_learned_words(telegram_id=str(message.from_user.id),
                                               terms=incorrect_terms)
            await message.answer(
                text=f"В ходе повторения ты забыл {incorrect_terms}, теперь снова повторяй их",
                reply_markup=make_row_keyboard([start_buttons])
            )
        await message.answer(
            text="Поздравляю! Ты все помнишь.",
            reply_markup=make_row_keyboard([start_buttons])
        )
        await state.clear()
