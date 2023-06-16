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



class RepeatLearningTerms(StatesGroup):
    choosing_type_object = State()
    choosing_repeat_option = State()
    first_step = State()
    check_answer = State()
    second_step = State()
    check_answer_second_step = State()
    third_step = State()
    check_answer_third_step = State()
    finish = State()


@router.message(Command("repeat_learn_terms"))
async def repeat_terms(message: Message, state: FSMContext):

    records = await db.get_count_repeat_terms(telegram_id=str(message.from_user.id), learning='learned')
    text = "вы выучили столько слов слов:\n"
    for record in records:
        text += f"{record['type']}: {record['count']}\n"
    await message.answer(text)
    await message.answer(
        text="Выберите, что будем повторять:",
        reply_markup=make_row_keyboard(available_term_types)
    )
    # Устанавливаем пользователю состояние "выбирает тип"
    await state.set_state(RepeatLearningTerms.choosing_type_object)

@router.message(RepeatLearningTerms.choosing_type_object, F.text.in_(available_term_types))
async def repeat_terms(message: Message, state: FSMContext):
    term_type = message.text
    await state.update_data(term_type=term_type)
    await message.answer(
        text="Выберите, сколько слов будем повторять:",
        reply_markup=make_row_keyboard(repeat_count)
    )
    # Устанавливаем пользователю состояние "выбирает тип"
    await state.set_state(RepeatLearningTerms.choosing_repeat_option)

async def escape_special_characters(text: str) -> str:
    return re.sub(r"(-|\(|\)|`)", r"\\\1", text)

@router.message(RepeatLearningTerms.choosing_repeat_option, F.text.in_(repeat_count))
async def type_chosen(message: Message, state: FSMContext):
    user_data = await state.get_data()
    await state.update_data(repeat_option=message.text)
    term_type = user_data.get('term_type')
    terms = await db.get_repeat_terms(telegram_id=str(message.from_user.id), term_type=term_type, count = int(message.text), learning='learned')
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
        await state.set_state(RepeatLearningTerms.first_step)







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
    random_options = random.sample(other_options, 3)
    options = [correct_option, *random_options]
    logger.debug(f'{correct_option} правильный ответ, {options}')
    random.shuffle(options)
    if next_state == RepeatLearningTerms.finish:
        await message.answer(text=term)
        logger.debug(f'{next_state} {term}')
    else:
        await message.answer(text=term, reply_markup=make_row_keyboard(options))
    await state.update_data(chosen_term=term, correct_option=correct_option, **{term_key: term_list})


@logger.catch()
async def check_user_answer(message: Message, state: FSMContext, next_step_function):
    user_data = await state.get_data()
    correct_option = user_data["correct_option"]

    if len(message.text) > 10 and message.text[:-3].strip().lower() in correct_option.strip().lower():
        await message.answer(text="Правильно!")
        await next_step_function()

    if message.text.strip().lower() == correct_option.strip().lower():
        await message.answer(text="Правильно!")
        await next_step_function()
    else:
        incorrect_terms = user_data.get('incorrect_terms', [])
        incorrect_terms.append(user_data['chosen_term'])
        await state.update_data(incorrect_terms=incorrect_terms)
        await message.answer(text="Неправильно! Попробуй еще раз.")


@router.message(RepeatLearningTerms.first_step, F.text.in_('Начать'))
async def first_learn_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать слово, а ты выбирай определение")
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    user_data["words"] = list(terms.keys())
    await state.update_data(user_data)
    await send_term_and_options(message, state, "words", "definitions", RepeatLearningTerms.second_step)
    await state.set_state(RepeatLearningTerms.check_answer)


@router.message(RepeatLearningTerms.check_answer)
async def check_user_answer_first_step(message: Message, state: FSMContext):
    next_step_function = partial(send_term_and_options, message, state, "words", "definitions", RepeatLearningTerms.second_step)
    await check_user_answer(message, state, next_step_function)


@router.message(RepeatLearningTerms.second_step, F.text.in_('перейти'))
async def second_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать определение, а ты выбирай слово")
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    user_data["definitions"] = list(terms.values())
    await state.update_data(user_data)
    await send_term_and_options(message, state, "definitions", "words", RepeatLearningTerms.third_step)
    await state.set_state(RepeatLearningTerms.check_answer_second_step)


@router.message(RepeatLearningTerms.check_answer_second_step)
async def check_user_answer_second_step(message: Message, state: FSMContext):
    next_step_function = partial(send_term_and_options, message, state, "definitions", "words", RepeatLearningTerms.finish)
    await check_user_answer(message, state, next_step_function)




@router.message(RepeatLearningTerms.finish, F.text.in_('перейти'))
async def finish(message: Message, state: FSMContext):
    user_data = await state.get_data()
    incorrect_terms = set(user_data.get('incorrect_terms', []))
    answer = await db.repeat_learned_words(telegram_id=str(message.from_user.id), terms=incorrect_terms)
    logger.debug(f'{incorrect_terms}')

    await message.answer(
        text=f"а этом изучение всех слов оконченно {answer}",
        reply_markup=make_row_keyboard(['/learn_words', '/add_terms', 'repeat_terms'])
    )
    await state.clear()
