import re
from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove
from keyboards.simple_row import make_row_keyboard
from db.db import db
from loguru import logger

from state.states import UserProgress

router = Router()

AVAILABLE_TERM_TYPES = ["term", "english_word"]
LEARNING_PROGRESS = ['learned', 'repeat', 'learning']


@router.message(Command("check_progress"))
async def cmd_check_progress(message: Message, state: FSMContext):
    progress = await db.get_terms_progress(telegram_id=str(message.from_user.id))
    await message.answer(
        text=f"Вы изучили столько слов: {progress['learned']}\n"
             f"у вас в стадии повторении столько слов: {progress['repeat']}\n"
             f"у вас неизучено слов: {progress['learning']} \n",
    )
    await message.answer(
        text="Выберите тип изучаемого объекта чтобы посмотреть слова",
        reply_markup=make_row_keyboard(AVAILABLE_TERM_TYPES)
    )
    await state.set_state(UserProgress.type_chosen)


async def send_types_and_cound_words(message: Message, types_and_counts: dict):
    text = "У вас на изучении следующее количество слов:\n"
    for type_of_learning, count_words in types_and_counts.items():
        text += f"этап {type_of_learning}: {count_words}\n"
    await message.answer(text=text)


@router.message(UserProgress.type_chosen, F.text.in_(AVAILABLE_TERM_TYPES))
async def term_type_chosen(message: Message, state: FSMContext):
    chosen_type = message.text.lower()
    await state.update_data(chosen_type=chosen_type)
    types_and_counts = await db.get_count_user_words_by_type(
        telegram_id=str(message.from_user.id), term_type=chosen_type
    )
    if types_and_counts:
        await send_types_and_cound_words(message, types_and_counts)
        await message.answer(
            text="Окей, выбери теперь какие слова ты хочешь посмотреть",
            reply_markup=make_row_keyboard(LEARNING_PROGRESS)
        )
    else:
        await message.answer(
            text=f"Ты еще не добавил слова типа {chosen_type}, добавь их ",
            reply_markup=make_row_keyboard(['learned', 'repeat', 'learning'])
        )


def get_chunks(terms_and_definitions_list_with_tuples: list, number_of_chunk: int):
    """Yield successive n-sized chunks from lst."""
    for begin_slice in range(0, len(terms_and_definitions_list_with_tuples), number_of_chunk):
        yield terms_and_definitions_list_with_tuples[begin_slice:begin_slice + number_of_chunk]


async def send_terms_and_definitions_in_chunks(terms_and_definitions_dict: dict, message: Message):
    """ send user words and  definitions in 10 limit per message. Also add numerate to them  """
    terms_and_definitions_list_with_tuples = list(terms_and_definitions_dict.items())
    list_of_terms_and_definitions_chunks = list(get_chunks(terms_and_definitions_list_with_tuples, 10))
    for idx, chunk in enumerate(list_of_terms_and_definitions_chunks):
        terms_and_definitions_text = "\n".join(
            [f"{number + 1 + idx * 10}. {term}: {definition}" for number, (term, definition) in enumerate(chunk)])
        await message.answer(
            text=f"{terms_and_definitions_text}",
        )


@router.message(UserProgress.type_chosen, F.text.in_(LEARNING_PROGRESS))
async def send_terms_and_definitions_based_on_type_and_progress(message: Message, state: FSMContext):
    user_data = await state.get_data()
    term_type = user_data['chosen_type']
    progress = message.text.lower()
    telegram_id = str(message.from_user.id)
    terms_and_definitions = await db.get_user_terms_and_definitions(telegram_id=telegram_id, term_type=term_type,
                                                                    progress=progress)
    if terms_and_definitions:
        await send_terms_and_definitions_in_chunks(terms_and_definitions, message)
    else:
        await message.answer(
            text=f"У вас нет слов типа {term_type}, которые находятся на стадии {progress}",
        )
