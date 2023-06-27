import random
import re
from functools import partial

from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ErrorEvent
from loguru import logger

from keyboards.simple_row import make_row_keyboard, start_buttons

from models.models import RepeatLearnedWordsTraining
from state.states import RepeatLearnedWordsState

router = Router()

RepeatLearnedWordsTraining = RepeatLearnedWordsTraining(RepeatLearnedWordsState)


@router.message(Command("repeat_learn_terms"))
async def get_started_and_choosing_term_type(message: Message, state: FSMContext):
    """
    get from db all users words depends on learning type=repeat group by types and sending them to user
    """

    text = "У вас на повторении следующее количество слов:\n"
    await RepeatLearnedWordsTraining.get_started_and_choosing_term_type(text, message, state, 'learned')


@router.message(RepeatLearnedWordsState.chosen_type_object, F.text.in_(RepeatLearnedWordsTraining.available_term_types))
async def choosing_count_words(message: Message, state: FSMContext):
    """
    get from db all users words and number of repetetions depends on chosen_type. User should choose number of words to repeat
    """
    text = "Сколько изученных слов будем повторять?\n"
    await RepeatLearnedWordsTraining.choosing_count_words(text, message, state)


@router.message(RepeatLearnedWordsState.get_words_state, F.text.in_(RepeatLearnedWordsTraining.number_of_words))
async def get_words(message: Message, state: FSMContext):
    """
    get words from db and check if user has enough words to repeat.
    """

    await RepeatLearnedWordsTraining.get_words(message, state, 'learned')


@router.message(RepeatLearnedWordsState.check_answer)
async def check_answer(message: Message, state: FSMContext):
    await RepeatLearnedWordsTraining.check_answer_state(message, state)


@router.message(RepeatLearnedWordsState.first_step, F.text.in_('Начать'))
async def first_step(message: Message, state: FSMContext):
    await RepeatLearnedWordsTraining.first_step_state(message, state)


@router.message(RepeatLearnedWordsState.second_step, F.text.in_("перейти на следующий этап"))
async def second_step(message: Message, state: FSMContext):
    text = 'Сейчас я буду тебе присылать определение, а ты выбирай правильное слово'
    next_state = RepeatLearnedWordsState.finish
    key_type = "definitions"
    current_step = 'second_step'
    await RepeatLearnedWordsTraining.step_logic(message, state, text, next_state, current_step, key_type)


@router.message(RepeatLearnedWordsState.finish, F.text.in_("перейти на следующий этап"))
async def finish(message: Message, state: FSMContext):
    await RepeatLearnedWordsTraining.finish(message, state)
