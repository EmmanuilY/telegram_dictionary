from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove

from keyboards.simple_row import make_row_keyboard

from model.db import DB
from models.models import LearningWords
from loguru import logger

import random
import re
import time
from functools import partial

db = DB()
router = Router()

available_term_types = ["word", "english_word"]
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


class LearnWords(StatesGroup):
    choosing_type_of_words = State()
    choosing_number_of_words = State()
    pre_learn_terms = State()
    first_step = State()
    check_answer = State()
    second_step = State()
    check_answer_second_step = State()
    third_step = State()
    check_answer_third_step = State()
    finish = State()


@router.message(Command("learn_words"))
async def choose_type_of_words(message: Message, state: FSMContext):
    await message.answer(
        text="Выберите, что будем учить:",
        reply_markup=make_row_keyboard(available_term_types)
    )

    await state.set_state(LearnWords.choosing_type_of_words)


@router.message(LearnWords.choosing_type_of_words, F.text.in_(available_term_types))
async def type_chosen(message: Message, state: FSMContext):
    await state.update_data(type_of_words=message.text.lower())
    await message.answer(
        text="Выберите, сколько слов будем повторять:",
        reply_markup=make_row_keyboard(repeat_count)
    )

    await state.set_state(LearnWords.choosing_number_of_words)


@router.message(LearnWords.choosing_number_of_words, F.text.in_(repeat_count))
async def type_chosen(message: Message, state: FSMContext):
    user_data = await state.get_data()
    type_of_words = user_data.get('type_of_words')
    number_of_words = int(message.text)
    user_id = str(message.from_user.id)
    learn_process = LearningWords(user_id=user_id, type_of_words=type_of_words,
                                  number_of_words=number_of_words, type_of_learning='learning')
    words = await learn_process.get_words()
    logger.info(f'{words} - {message.from_user.id} - {message.from_user.username}')

    if len(words.keys()) < number_of_words:
        await message.answer(
            text=f"у вас недостаточно слов типа {message.text.lower()}, добавьте еще",
            reply_markup=make_row_keyboard(['/start'])
        )
        logger.debug(
            f'недостаточно слов типа {message.text.lower()} у {message.from_user.id}, вот список термнов : {words}')
        await state.clear()
    else:
        learn_process.words = words
        await state.update_data(learn_process=learn_process)
        await message.answer(text="Ниже слова")
        for word, definition in words.items():
            await message.answer(text=f"{word} - {definition}")

        await message.answer(
            text="Нужен cамоповтор?",
            reply_markup=make_row_keyboard(['Повтор для себя'])
        )
        await state.set_state(LearnWords.pre_learn_terms)


@router.message(LearnWords.choosing_type_of_words)
async def type_chosen_incorrectly(message: Message):
    await message.answer(
        text="Я не знаю такого типа.\n\n"
             "Пожалуйста, выберите одно из названий из списка ниже:",
        reply_markup=make_row_keyboard(available_term_types)
    )


async def escape_special_characters(text: str) -> str:
    return re.sub(r"(-|\(|\)|`)", r"\\\1", text)


@router.message(LearnWords.pre_learn_terms, F.text.in_('Повтор для себя'))
async def pre_learn_part(message: Message, state: FSMContext):
    await message.answer(
        text="Ниже слова................................................................................................"
    )
    user_data = await state.get_data()
    learn_process = user_data.get("learn_process")
    words = learn_process.words
    logger.info(f'{words} {message.from_user.id}')
    for word, definition in words.items():
        word = await escape_special_characters(word)
        definition = await escape_special_characters(definition)
        try:
            await message.answer(
                text=f"{word}     \-      ||{definition}||", parse_mode="MarkdownV2"
            )
        except TelegramBadRequest as e:
            logger.error(f'{e}, слово {word} и определение {definition} выдали ошибку при словаре {words}')
    await message.answer(
        text="Начать?",
        reply_markup=make_row_keyboard(['Начать'])
    )
    await state.set_state(LearnWords.first_step)


@logger.catch()
async def send_term_and_options(message: Message, state: FSMContext, term_key: str, options_key: str, next_state):
    user_data = await state.get_data()
    words = user_data.get("words", {})
    term_list = user_data[term_key]
    logger.debug(f'{term_list} {term_key} {options_key}')
    if not term_list:
        await message.answer(text="Этап завершен! Вы молодец!", reply_markup=make_row_keyboard(['перейти']))
        await state.set_state(next_state)
        return
    word = term_list.pop(0)
    correct_option = words[word] if term_key == "words" else {v: k for k, v in words.items()}[word]
    other_options = [v for k, v in words.items() if k != word] if term_key == "words" else [k for k, v in words.items()
                                                                                            if v != word]
    options = random.sample([*other_options, correct_option], 4)
    random.shuffle(options)
    if next_state == LearnWords.finish:
        await message.answer(text=word)
        logger.debug(f'{next_state} {word}')
    else:
        await message.answer(text=word, reply_markup=make_row_keyboard(options))
    await state.update_data(chosen_term=word, correct_option=correct_option, **{term_key: term_list})


@logger.catch()
async def check_user_answer(message: Message, state: FSMContext, next_step_function):
    user_data = await state.get_data()
    correct_option = user_data["correct_option"]
    if len(message.text) > 10 and message.text[:-3].strip().lower() in correct_option.strip().lower():
        await message.answer(text="Правильно!")
        await next_step_function()

    elif message.text.strip().lower() == correct_option.strip().lower():
        await message.answer(text="Правильно!")
        await next_step_function()
    else:
        await message.answer(text="Неправильно! Попробуй еще раз.")


@router.message(LearnWords.first_step, F.text.in_('Начать'))
async def first_learn_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать слово, а ты выбирай определение")
    user_data = await state.get_data()
    words = user_data.get("words", {})
    user_data["words"] = list(words.keys())
    await state.update_data(user_data)
    await send_term_and_options(message, state, "words", "definitions", LearnWords.second_step)
    await state.set_state(LearnWords.check_answer)


@router.message(LearnWords.check_answer)
async def check_user_answer_first_step(message: Message, state: FSMContext):
    next_step_function = partial(send_term_and_options, message, state, "words", "definitions", LearnWords.second_step)
    await check_user_answer(message, state, next_step_function)


@router.message(LearnWords.second_step, F.text.in_('перейти'))
async def second_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать определение, а ты выбирай слово")
    user_data = await state.get_data()
    words = user_data.get("words", {})
    user_data["definitions"] = list(words.values())
    await state.update_data(user_data)
    await send_term_and_options(message, state, "definitions", "words", LearnWords.third_step)
    await state.set_state(LearnWords.check_answer_second_step)


@router.message(LearnWords.check_answer_second_step)
async def check_user_answer_second_step(message: Message, state: FSMContext):
    next_step_function = partial(send_term_and_options, message, state, "definitions", "words", LearnWords.third_step)
    await check_user_answer(message, state, next_step_function)


@router.message(LearnWords.third_step, F.text.in_('перейти'))
async def third_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать определение, а ты вводи правильное слово")
    user_data = await state.get_data()
    words = user_data.get("words", {})
    user_data["definitions"] = list(words.values())
    await state.update_data(user_data)
    await send_term_and_options(message, state, "definitions", "words", LearnWords.finish)
    await state.set_state(LearnWords.check_answer_third_step)


@router.message(LearnWords.check_answer_third_step)
async def check_user_answer_third_step(message: Message, state: FSMContext):
    next_step_function = partial(send_term_and_options, message, state, "definitions", "words", LearnWords.finish)
    await check_user_answer(message, state, next_step_function)


@router.message(LearnWords.finish, F.text.in_('перейти'))
async def finish(message: Message, state: FSMContext):
    user_data = await state.get_data()
    words = user_data.get("words", {})
    learn_terms = list(words.keys())
    answer = await db.change_learn_type(telegram_id=str(message.from_user.id), words=learn_terms)

    await message.answer(
        text=f"а этом изучение всех слов оконченно {answer}",
        reply_markup=make_row_keyboard(['/learn_words', '/add_terms'])
    )
    await state.clear()
