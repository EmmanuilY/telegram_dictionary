import random
import re
from functools import partial

from aiogram import Router, F
from aiogram import exceptions as aiogram_exceptions
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ErrorEvent
from loguru import logger

from keyboards.simple_row import make_row_keyboard, start_buttons

from models.models import BaseTrainings

router = Router()


class LearnTrainingState(StatesGroup):
    chosen_type_object = State()
    get_words_state = State()
    pre_learn_part = State() # only in learn training
    first_step = State()
    check_answer = State()
    second_step = State()
    third_step = State()
    finish = State()



class Learn(BaseTrainings):


    async def get_words(self, message, state, type_of_learning):
        """
            get words from db and check if user has enough words to repeat.
            """
        user_data = await state.get_data()
        chosen_type = user_data.get("chosen_type")
        words = await LearnTraining.db.get_words(
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


LearnTraining = Learn(LearnTrainingState)


@router.message(Command("learn_words"))
async def get_started_and_choosing_term_type(message: Message, state: FSMContext):
    """
        get from db all user's words depends on learning type=repeat group by types and sending them to user
    """
    text = "У вас на изучении следующее количество слов:\n"
    await LearnTraining.get_started_and_choosing_term_type(text, message, state, 'learning')


@router.message(LearnTrainingState.chosen_type_object, F.text.in_(LearnTraining.available_term_types))
async def choosing_count_words(message: Message, state: FSMContext):
    text = "Выберите, сколько слов будем учить:"
    await LearnTraining.choosing_count_words(text, message, state)


@router.message(LearnTrainingState.get_words_state, F.text.in_(LearnTraining.number_of_words))
async def get_words(message: Message, state: FSMContext):
    """
    get words from db and check if user has enough words to repeat.
    """

    await LearnTraining.get_words(message, state, 'learning')


@router.message(LearnTrainingState.pre_learn_part, F.text.in_('Повтор для себя'))
async def pre_learn_part(message: Message, state: FSMContext):
    await LearnTraining.pre_learn_part(message, state)


@router.message(LearnTrainingState.check_answer)
async def check_answer(message: Message, state: FSMContext):
    await LearnTraining.check_answer_state(message, state)


@router.message(LearnTrainingState.first_step, F.text.in_('Начать'))
async def first_step(message: Message, state: FSMContext):
    await LearnTraining.first_step_state(message, state)


@router.message(LearnTrainingState.second_step, F.text.in_("перейти на следующий этап"))
async def second_step(message: Message, state: FSMContext):
    await LearnTraining.second_step_state(message, state)


@router.message(LearnTrainingState.third_step, F.text.in_("перейти на следующий этап"))
async def third_step(message: Message, state: FSMContext):
    await LearnTraining.third_step_state(message, state)


@router.message(LearnTrainingState.finish, F.text.in_("перейти на следующий этап"))
async def finish(message: Message, state: FSMContext):
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    learn_terms = list(terms.keys())
    answer = await LearnTraining.db.change_learn_type(telegram_id=str(message.from_user.id), words=learn_terms)

    await message.answer(
        text=f"а на этом повторение слов оконченно {answer}",
        reply_markup=make_row_keyboard(start_buttons),
    )
    await state.clear()
