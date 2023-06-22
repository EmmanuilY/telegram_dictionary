from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove

from keyboards.simple_row import make_row_keyboard

from model.db import DB

from loguru import logger

import random
import re
import time
from functools import partial

db = DB()
router = Router()

available_term_types = ["term", "english_word"]
repeat_count = ["4", "6", "8", "10"]
answer_slovarik = {
    1: 'одно',
    2: 'два',
    3: 'три',
    4: 'четыре',
    5: 'пять',
    6: 'шесть',
    7: 'семь'
}


class RepeatTerms(StatesGroup):
    choosing_type_object = State()
    choosing_repeat_option = State()
    first_step = State()
    check_answer = State()
    second_step = State()
    check_answer_second_step = State()
    third_step = State()
    check_answer_third_step = State()
    finish = State()


@router.message(Command("repeat_terms"))
async def repeat_terms(message: Message, state: FSMContext):
    records = await db.get_count_repeat_terms(telegram_id=str(message.from_user.id), learning='repeat')
    text = "У вас на повторении следующее количество слов:\n"
    for record in records:
        text += f"{record['type']}: {record['count']}\n"
    await message.answer(text)
    await message.answer(
        text="Выберите, что будем повторять:",
        reply_markup=make_row_keyboard(available_term_types)
    )
    # Устанавливаем пользователю состояние "выбирает тип"
    await state.set_state(RepeatTerms.choosing_type_object)


@router.message(RepeatTerms.choosing_type_object, F.text.in_(available_term_types))
async def repeat_terms(message: Message, state: FSMContext):
    term_type = message.text
    await state.update_data(term_type=term_type)
    records = await db.get_count_repeat_terms_types(telegram_id=str(message.from_user.id), term_type=term_type)
    text = f"Вот ваше количество повторений каждого типа {term_type} :\n"
    for record in records:
        text += f"{answer_slovarik[record['number_of_repetitions']]} повторение  :  {record['count']} слов\n"
    await message.answer(text)

    await message.answer(
        text="Выберите, сколько слов будем повторять:",
        reply_markup=make_row_keyboard(repeat_count)
    )
    # Устанавливаем пользователю состояние "выбирает тип"
    await state.set_state(RepeatTerms.choosing_repeat_option)


async def escape_special_characters(text: str) -> str:
    return re.sub(r"(-|\(|\)|`)", r"\\\1", text)


@router.message(RepeatTerms.choosing_repeat_option, F.text.in_(repeat_count))
async def type_chosen(message: Message, state: FSMContext):
    user_data = await state.get_data()
    await state.update_data(repeat_option=message.text)
    term_type = user_data.get('term_type')
    terms = await db.get_words(user_id=str(message.from_user.id), type_of_words=term_type,
                               number_of_words=int(message.text), type_of_learning='repeat')
    logger.info(f'{terms} - {message.from_user.id} - {message.from_user.username}')
    if len(terms.keys()) < int(message.text):
        await message.answer(
            text=f"у вас недостаточно слов типа {term_type}, их всего {message.text.lower()}, подучите еще",
            reply_markup=make_row_keyboard(['/learn_words', '/add_terms', '/check_progress', '/repeat_terms'])
        )
        logger.debug(
            f'недостаточно слов типа {message.text.lower()} у {message.from_user.id}, вот список термнов : {terms}')
        await state.clear()
    else:
        await state.update_data(terms=terms)
        await message.answer(
            text="Ниже слова"
        )
        for word, definition in terms.items():
            word = await escape_special_characters(word)
            definition = await escape_special_characters(definition)
            try:
                await message.answer(
                    text=f"{word}     \-      ||{definition}||", parse_mode="MarkdownV2"
                )
            except TelegramBadRequest as e:
                logger.error(f'{e}, слово {word} и определение {definition} выдали ошибку при словаре {terms}')
        await message.answer(
            text="Начать?",
            reply_markup=make_row_keyboard(['Начать'])
        )
        await state.set_state(RepeatTerms.first_step)


@logger.catch()
async def send_term_and_options(message: Message, state: FSMContext, term_key: str, next_state):
    user_data = await state.get_data()
    terms, term_list = get_terms_and_list(user_data, term_key)
    current_state = user_data.get('current_state')
    if not term_list:
        await message.answer(text="Этап завершен! Вы молодец!", reply_markup=make_row_keyboard(['перейти']))
        await state.set_state(next_state)
        return
    term, correct_option, other_options = get_word_and_definitions(term_list, terms, term_key)
    random_options = random.sample(other_options, 3)
    options = [correct_option, *random_options]
    random.shuffle(options)
    await send_keyboard(options, message, term, current_state)
    await state.update_data(chosen_term=term, correct_option=correct_option, **{term_key: term_list})


def get_terms_and_list(user_data: dict, term_key: str):
    terms = user_data.get("terms", {})
    term_list = user_data[term_key]
    random.shuffle(term_list)
    logger.debug(f"get_terms_and_list {user_data} {term_key}")
    return terms, term_list


def get_word_and_definitions(term_list: list, terms: dict, term_key: str):
    term = term_list.pop(0)
    correct_option, other_options = get_words_or_definitions_based_on_term_key(terms, term, term_key)
    logger.debug(f"procces term list {correct_option} {other_options}")
    return term, correct_option, other_options


def get_words_or_definitions_based_on_term_key(terms: dict, term: str, term_key: str):
    if term_key == "words":
        current_definition = terms[term]
        other_definitions = [definition for word, definition in terms.items() if definition != current_definition]
        logger.debug(f"get_words_or_definitions_based_on_term_key {terms} {term} {term_key} определение {current_definition} остальныеопределения {other_definitions}")
        return current_definition, other_definitions

    else:
        current_word = {word : definition for definition, word in terms.items()}[term]
        other_words = [word for word, definition in terms.items() if word  != current_word ]

        logger.debug(
            f"get_words_or_definitions_based_on_term_key {terms} {term} {term_key} слово {current_word} осталдьные слова {other_words}")

        return current_word, other_words


async def send_keyboard(options: list, message: Message, term: str, current_state: str):
    if current_state == 'third_step':
        await message.answer(text=term, ReplyKeyboardRemove=True)
        logger.debug(f' shuffle_and_display_options {current_state} {term}')
    else:
        logger.debug(f' shuffle_and_display_options else {current_state} {term}')
        await message.answer(text=term, reply_markup=make_row_keyboard(options))


@logger.catch()
async def check_user_answer(message: Message, state: FSMContext, next_step_function):
    user_data = await state.get_data()
    correct_option = user_data["correct_option"]
    logger.debug(f'прислали {message.text}')
    logger.debug(f'а правильный {correct_option}')
    if len(message.text) > 10 and message.text[:-3].strip().lower() in correct_option.strip().lower():
        await message.answer(text="Правильно!")
        await next_step_function()

    elif message.text.strip().lower() == correct_option.strip().lower():
        await message.answer(text="Правильно!")
        await next_step_function()
    else:
        await message.answer(text="Неправильно! Попробуй еще раз.")


@router.message(RepeatTerms.first_step, F.text.in_('Начать'))
async def first_learn_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать слово, а ты выбирай определение")
    user_data = await state.get_data()
    await state.update_data(current_state='first_step')
    terms = user_data.get("terms", {})
    user_data["words"] = list(terms.keys())
    await state.update_data(user_data)
    await send_term_and_options(message, state, "words", RepeatTerms.second_step)
    await state.set_state(RepeatTerms.check_answer)


@router.message(RepeatTerms.check_answer)
async def check_user_answer_first_step(message: Message, state: FSMContext):
    next_step_function = partial(send_term_and_options, message, state, "words", RepeatTerms.second_step)
    await check_user_answer(message, state, next_step_function)


@router.message(RepeatTerms.second_step, F.text.in_('перейти'))
async def second_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать определение, а ты выбирай слово")
    await state.update_data(current_state='second_step')
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    user_data["definitions"] = list(terms.values())
    await state.update_data(user_data)
    await send_term_and_options(message, state, "definitions", RepeatTerms.third_step)
    await state.set_state(RepeatTerms.check_answer_second_step)


@router.message(RepeatTerms.check_answer_second_step)
async def check_user_answer_second_step(message: Message, state: FSMContext):
    next_step_function = partial(send_term_and_options, message, state, "definitions", RepeatTerms.third_step)
    await check_user_answer(message, state, next_step_function)


@router.message(RepeatTerms.third_step, F.text.in_('перейти'))
async def third_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать определение, а ты вводи правильное слово")
    await state.update_data(current_state='third_step')
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    user_data["definitions"] = list(terms.values())
    await state.update_data(user_data)
    await send_term_and_options(message, state, "definitions", RepeatTerms.finish)
    await state.set_state(RepeatTerms.check_answer_third_step)


@router.message(RepeatTerms.check_answer_third_step)
async def check_user_answer_third_step(message: Message, state: FSMContext):
    next_step_function = partial(send_term_and_options, message, state, "definitions", RepeatTerms.finish)
    await check_user_answer(message, state, next_step_function)


@router.message(RepeatTerms.finish, F.text.in_('перейти'))
async def finish(message: Message, state: FSMContext):
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    learn_terms = list(terms.keys())
    answer = await db.change_learn_type(telegram_id=str(message.from_user.id), terms=learn_terms)

    await message.answer(
        text=f"а этом изучение всех слов оконченно {answer}",
        reply_markup=make_row_keyboard(['/learn_words', '/add_terms'])
    )
    await state.clear()
