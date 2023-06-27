from enum import Enum
from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message

from models.models import RepeatTraining
from state.states import RepeatState

router = Router()

RepeatTraining = RepeatTraining(RepeatState)


@router.message(Command("repeat_terms"))
async def get_started_and_choosing_term_type(message: Message, state: FSMContext):
    """
    get from db all users words depends on learning type=repeat group by types and sending them to user
    """

    text = "У вас на повторении следующее количество слов:\n"
    await RepeatTraining.get_started_and_choosing_term_type(text, message, state, 'repeat')


@router.message(RepeatState.chosen_type_object, F.text.in_(RepeatTraining.available_term_types))
async def choosing_count_words(message: Message, state: FSMContext):
    """
    get from db all users words and number of repetetions depends on chosen_type. User should choose number of words to repeat
    """
    text = "Вы столько раз повторяли слова:\n"
    await RepeatTraining.choosing_count_words(text, message, state)


@router.message(RepeatState.get_words_state, F.text.in_(RepeatTraining.number_of_words))
async def get_words(message: Message, state: FSMContext):
    """
    get words from db and check if user has enough words to repeat.
    """

    await RepeatTraining.get_words(message, state, 'repeat')


@router.message(RepeatState.check_answer)
async def check_answer(message: Message, state: FSMContext):
    await RepeatTraining.check_answer_state(message, state)


@router.message(RepeatState.first_step, F.text.in_('Начать'))
async def first_step(message: Message, state: FSMContext):
    await RepeatTraining.first_step_state(message, state)


@router.message(RepeatState.second_step, F.text.in_("перейти на следующий этап"))
async def second_step(message: Message, state: FSMContext):
    await message.answer(
        text="Сейчас я буду тебе присылать определение, а ты выбирай слово"
    )
    await RepeatTraining.shuffle_and_update_state(
        state, "definitions", RepeatState.third_step, "second_step"
    )
    await RepeatTraining.send_term_and_definitions(message, state, "definitions")
    await state.set_state(RepeatState.check_answer)


@router.message(RepeatState.third_step, F.text.in_("перейти на следующий этап"))
async def third_step(message: Message, state: FSMContext):
    await message.answer(
        text="Сейчас я буду тебе присылать определение, а ты вводи правильное слово"
    )
    await RepeatTraining.shuffle_and_update_state(
        state, "definitions", RepeatState.finish, "third_step"
    )
    await RepeatTraining.send_term_and_definitions(message, state, "definitions")
    await state.set_state(RepeatState.check_answer)


@router.message(RepeatState.finish, F.text.in_("перейти на следующий этап"))
async def finish(message: Message, state: FSMContext):
    await RepeatTraining.finish(message, state)
