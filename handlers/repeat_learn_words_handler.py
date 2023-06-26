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


class RepeatLeranedWordsState(StatesGroup):
    chosen_type_object = State()
    get_words_state = State()
    first_step = State()
    check_answer = State()
    second_step = State()  # here no htird_state
    finish = State()


class RepeatLearnedWords(BaseTrainings):
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
            logger.debug(f' {correct_answer} {term_key}')
        incorrect_terms = user_data.get('incorrect_terms', set())
        logger.debug(f'{incorrect_terms} {chosen_term}')
        incorrect_terms.add(chosen_term)
        await state.update_data(incorrect_terms=incorrect_terms)
        await message.answer(text="Неправильно! Попробуй еще раз.")


RepeatLearnedWordsTraining = RepeatLearnedWords(RepeatLeranedWordsState)


@router.message(Command("repeat_learn_terms"))
async def get_started_and_choosing_term_type(message: Message, state: FSMContext):
    """
    get from db all users words depends on learning type=repeat group by types and sending them to user
    """

    text = "У вас на повторении следующее количество слов:\n"
    await RepeatLearnedWordsTraining.get_started_and_choosing_term_type(text, message, state, 'learned')


@router.message(RepeatLeranedWordsState.chosen_type_object, F.text.in_(RepeatLearnedWordsTraining.available_term_types))
async def choosing_count_words(message: Message, state: FSMContext):
    """
    get from db all users words and number of repetetions depends on chosen_type. User should choose number of words to repeat
    """
    text = "Сколько изученных слов будем повторять?\n"
    await RepeatLearnedWordsTraining.choosing_count_words(text, message, state)


@router.message(RepeatLeranedWordsState.get_words_state, F.text.in_(RepeatLearnedWordsTraining.number_of_words))
async def get_words(message: Message, state: FSMContext):
    """
    get words from db and check if user has enough words to repeat.
    """

    await RepeatLearnedWordsTraining.get_words(message, state, 'learned')


@router.message(RepeatLeranedWordsState.check_answer)
async def check_answer(message: Message, state: FSMContext):
    await RepeatLearnedWordsTraining.check_answer_state(message, state)


@router.message(RepeatLeranedWordsState.first_step, F.text.in_('Начать'))
async def first_step(message: Message, state: FSMContext):
    await RepeatLearnedWordsTraining.first_step_state(message, state)


@router.message(RepeatLeranedWordsState.second_step, F.text.in_("перейти на следующий этап"))
async def second_step(message: Message, state: FSMContext):
    text = 'Сейчас я буду тебе присылать определение, а ты выбирай правильное слово'
    next_state = RepeatLeranedWordsState.finish
    key_type = "definitions"
    current_step = 'second_step'
    await RepeatLearnedWordsTraining.step_logic(message, state, text, next_state, current_step, key_type)


@router.message(RepeatLeranedWordsState.finish, F.text.in_("перейти на следующий этап"))
async def finish(message: Message, state: FSMContext):
    user_data = await state.get_data()
    incorrect_terms = (user_data.get('incorrect_terms', set()))
    if incorrect_terms:
        answer = await RepeatLearnedWordsTraining.db.repeat_learned_words(telegram_id=str(message.from_user.id),
                                                                          terms=incorrect_terms)

    await message.answer(
        text=f"а этом изучение всех слов оконченно {answer}",
        reply_markup=make_row_keyboard(['/learn_words', '/add_terms', 'repeat_terms'])
    )
    await state.clear()
