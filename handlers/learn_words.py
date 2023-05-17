from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove

from keyboards.simple_row import make_row_keyboard

from model.db import DB
from handlers.classes import LearningSession

from loguru import logger

import random
import re
import time
from functools import partial

db = DB()
router = Router()

available_term_types = ["term", "english_word"]


class LearnTerms(StatesGroup):
    choosing_type_object = State()
    pre_learn_terms = State()
    first_step = State()
    check_answer = State()
    second_step = State()
    check_answer_second_step = State()
    third_step = State()
    check_answer_third_step = State()
    finish = State()


@router.message(Command("learn_words"))
async def learn_terms(message: Message, state: FSMContext):
    await message.answer(
        text="Выберите, что будем учить:",
        reply_markup=make_row_keyboard(available_term_types)
    )
    # Устанавливаем пользователю состояние "выбирает тип"
    user = LearningSession(telegram_id=message.from_user.id)
    await state.update_data(user=user)
    await state.set_state(LearnTerms.choosing_type_object)


@router.message(LearnTerms.choosing_type_object, F.text.in_(available_term_types))
async def type_chosen(message: Message, state: FSMContext):
    user_data = await state.get_data()
    # user = user_data.get("user")
    terms = await db.get_term(telegram_id=str(message.from_user.id), term_type=message.text.lower())
    logger.info(f'{terms} - {message.from_user.id} - {message.from_user.username}')
    if len(terms.keys()) < 4:
        await message.answer(
            text=f"у вас недостаточно слов типа {message.text.lower()}, добавьте еще",
            reply_markup=make_row_keyboard(['/start'])
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
            await message.answer(
                text=f"{word} - {definition}"
            )

        await message.answer(
            text="Нужен cамоповтор?",
            reply_markup=make_row_keyboard(['Повтор для себя'])
        )
        await state.set_state(LearnTerms.pre_learn_terms)


@router.message(LearnTerms.choosing_type_object)
async def type_chosen_incorrectly(message: Message):
    await message.answer(
        text="Я не знаю такого типа.\n\n"
             "Пожалуйста, выберите одно из названий из списка ниже:",
        reply_markup=make_row_keyboard(available_term_types)
    )


async def escape_special_characters(text: str) -> str:
    return re.sub(r"(-|\(|\)|`)", r"\\\1", text)


@router.message(LearnTerms.pre_learn_terms, F.text.in_('Повтор для себя'))
async def pre_learn_part(message: Message, state: FSMContext):
    await message.answer(
        text="Ниже слова................................................................................................"
    )
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    logger.info(f'{terms} {message.from_user.id}')
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
    await state.set_state(LearnTerms.first_step)


@logger.catch()
async def send_term_and_options(message: Message, state: FSMContext, term_key: str, options_key: str, next_state):
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    term_list = user_data[term_key]
    logger.debug(f'{term_list} {term_key} {options_key}')
    if not term_list:
        await message.answer(text="Этап завершен! Вы молодец!", reply_markup=make_row_keyboard(['перейти']))
        await state.set_state(next_state)
        return
    term = term_list.pop(0)
    correct_option = terms[term] if term_key == "words" else {v: k for k, v in terms.items()}[term]
    other_options = [v for k, v in terms.items() if k != term] if term_key == "words" else [k for k, v in terms.items()
                                                                                            if v != term]
    options = random.sample([*other_options, correct_option], 4)
    random.shuffle(options)
    if next_state == LearnTerms.finish:
        await message.answer(text=term)
        logger.debug(f'{next_state} {term}')
    else:
        await message.answer(text=term, reply_markup=make_row_keyboard(options))
    await state.update_data(chosen_term=term, correct_option=correct_option, **{term_key: term_list})


@logger.catch()
async def check_user_answer(message: Message, state: FSMContext, next_step_function):
    user_data = await state.get_data()
    correct_option = user_data["correct_option"]

    if message.text == correct_option:
        await message.answer(text="Правильно!")
        await next_step_function()
    else:
        await message.answer(text="Неправильно! Попробуй еще раз.")


@router.message(LearnTerms.first_step, F.text.in_('Начать'))
async def first_learn_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать слово, а ты выбирай определение")
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    user_data["words"] = list(terms.keys())
    await state.update_data(user_data)
    await send_term_and_options(message, state, "words", "definitions", LearnTerms.second_step)
    await state.set_state(LearnTerms.check_answer)


@router.message(LearnTerms.check_answer)
async def check_user_answer_first_step(message: Message, state: FSMContext):
    next_step_function = partial(send_term_and_options, message, state, "words", "definitions", LearnTerms.second_step)
    await check_user_answer(message, state, next_step_function)


@router.message(LearnTerms.second_step, F.text.in_('перейти'))
async def second_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать определение, а ты выбирай слово")
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    user_data["definitions"] = list(terms.values())
    await state.update_data(user_data)
    await send_term_and_options(message, state, "definitions", "words", LearnTerms.third_step)
    await state.set_state(LearnTerms.check_answer_second_step)


@router.message(LearnTerms.check_answer_second_step)
async def check_user_answer_second_step(message: Message, state: FSMContext):
    next_step_function = partial(send_term_and_options, message, state, "definitions", "words", LearnTerms.third_step)
    await check_user_answer(message, state, next_step_function)


@router.message(LearnTerms.third_step, F.text.in_('перейти'))
async def third_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать определение, а ты вводи правильное слово")
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    user_data["definitions"] = list(terms.values())
    await state.update_data(user_data)
    await send_term_and_options(message, state, "definitions", "words", LearnTerms.finish)
    await state.set_state(LearnTerms.check_answer_third_step)


@router.message(LearnTerms.check_answer_third_step)
async def check_user_answer_third_step(message: Message, state: FSMContext):
    next_step_function = partial(send_term_and_options, message, state, "definitions", "words",  LearnTerms.finish)
    await check_user_answer(message, state, next_step_function)


@router.message(LearnTerms.finish, F.text.in_('перейти'))
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
