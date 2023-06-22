from aiogram import Router, F
from aiogram import exceptions as aiogram_exceptions
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ErrorEvent

from keyboards.simple_row import make_row_keyboard, basic_buttons

from model.db import DB

from loguru import logger
import asyncio
import time
import random
import re
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


class RepeatWords(StatesGroup):
    choosing_type_object = State()
    choosing_repeat_option = State()
    first_step = State()
    check_answer = State()
    second_step = State()
    third_step = State()
    finish = State()


def async_timer_decorator(func):
    async def wrapper(*args, **kwargs):
        start_time = asyncio.get_event_loop().time()
        result = await func(*args, **kwargs)
        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - start_time  # время выполнения функции
        logger.info(f"Function {func.__name__} executed in {execution_time} seconds")  # логирование
        return result

    return wrapper


def timer_decorator(func):
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time  # время выполнения функции
        logger.info(f"Function {func.__name__} executed in {execution_time} seconds")  # логирование
        return result

    return wrapper


@router.errors()
async def error_handler(exception: ErrorEvent):
    error = exception.exception
    message = exception.update.message

    logger.error(f"{error}, user message: {message.text}  user_id: {message.from_user.id}")
    await send_message_with_keyboard(message, text='Что-то пошло не так, попробуйте снова',
                                     keyboard_options=basic_buttons
                                     )


async def send_message_with_keyboard(message: Message, text: str, keyboard_options: list):
    await message.answer(
        text=text,
        reply_markup=make_row_keyboard(keyboard_options)
    )


@router.message(Command("repeat_terms"))
async def choosing_words_type(message: Message, state: FSMContext):
    """
    get from db all users words depends on learning type=repeat group by types and sending them to user
    """
    types_and_counts = await db.get_count_repeat_words(telegram_id=str(message.from_user.id), learning='repeat')
    text = "У вас на повторении следующее количество слов:\n"
    for type_and_count in types_and_counts:
        text += f"{type_and_count['type']}: {type_and_count['count']}\n"
    await message.answer(text)
    await send_message_with_keyboard(message, "Выберите тип изучаемых слов:", available_term_types)
    await state.set_state(RepeatWords.choosing_type_object)


@router.message(RepeatWords.choosing_type_object, F.text.in_(available_term_types))
async def choosing_count_words(message: Message, state: FSMContext):
    """
     get from db all users words and number of repetetions depends on chosen_type. User should choose number of words to repeat
    """
    chosen_type = message.text
    await state.update_data(chosen_type=chosen_type)
    records = await db.get_count_repeat_words_types(telegram_id=str(message.from_user.id), term_type=chosen_type)
    text = f"Вот ваше количество повторений типа {chosen_type} :\n"
    for record in records:
        text += f"{answer_slovarik[record['number_of_repetitions']]} повторение  :  {record['count']} слов\n"
    await message.answer(text)
    await send_message_with_keyboard(message, "Выберите, сколько слов будем повторять:", repeat_count)
    await state.set_state(RepeatWords.choosing_repeat_option)


def escape_special_characters(text: str) -> str:
    return re.sub(r"(-|\(|\)|`)", r"\\\1", text)


async def check_len_words(message, words: dict, chosen_number: int) -> bool:
    if not words:
        await message.answer(
            text="Произошла супер непредвиденная ошибка, напишите админу"
        )
        return False

    elif len(words.keys()) < chosen_number:
        await send_message_with_keyboard(message, "у вас недостаточно слов, подучите еще",
                                         ['/learn_words', '/add_terms', '/check_progress'])
        return False

    return True


async def sending_words_with_invisible_definitions(message, words: dict) -> None:
    await message.answer(
        text="Ниже слова"
    )
    for word, definition in words.items():
        word = escape_special_characters(word)
        definition = escape_special_characters(definition)
        try:
            await message.answer(
                text=f"{word}     \-      ||{definition}||", parse_mode="MarkdownV2"
            )
        except aiogram_exceptions.TelegramBadRequest as e:
            logger.error(f'{e}, слово {word} и определение {definition} выдали ошибку при словаре {words}')


@router.message(RepeatWords.choosing_repeat_option, F.text.in_(repeat_count))
async def get_words(message: Message, state: FSMContext):
    """
    get words from db and check if user has enough words to repeat.
    """

    user_data = await state.get_data()
    chosen_type = user_data.get('chosen_type')
    words = await db.get_words(user_id=str(message.from_user.id), type_of_words=chosen_type,
                               number_of_words=int(message.text), type_of_learning='repeat')
    if await check_len_words(message, words, int(message.text)):
        await sending_words_with_invisible_definitions(message, words)
        await state.update_data(terms=words)
        await send_message_with_keyboard(message, 'Начать?', ['Начать'])
        await state.set_state(RepeatWords.first_step)
    else:
        await state.clear()


async def send_term_and_definitions(message: Message, state: FSMContext, term_key: str, next_state):
    """ term here is a name of word or definition.
        on first_step term is word, on second and third - term is definition
    """
    user_data = await state.get_data()
    terms_dict, answers_list = get_terms_dict_and_answers(user_data, term_key)
    if not answers_list:
        await message.answer(text="Этап завершен! Вы молодец!", reply_markup=make_row_keyboard(['перейти']))
        await state.set_state(next_state)
        return
    current_state = user_data.get('current_state')
    term, correct_answer, other_answers = get_term_and_answers(terms_dict, answers_list, term_key)
    random_answers = random.sample(other_answers, 3)
    answers = [correct_answer, *random_answers]
    random.shuffle(answers)
    await send_or_remove_keyboard(message, answers, term, current_state)
    await state.update_data(chosen_term=term, correct_answer=correct_answer)


def get_terms_dict_and_answers(user_data: dict, term_key: str):
    terms_dict = user_data.get("terms", {})
    answers_list = user_data[term_key]
    return terms_dict, answers_list


def get_term_and_answers(terms_dict: dict, answers_list: list, term_key: str):
    term = answers_list.pop(0)
    correct_answer, other_answers = get_words_or_definitions_based_on_term_key(terms_dict, term, term_key)
    return term, correct_answer, other_answers


def get_words_or_definitions_based_on_term_key(terms_dict: dict, term: str, term_key: str):
    if term_key == "words":
        current_definition = terms_dict[term]
        other_definitions = [definition for word, definition in terms_dict.items() if definition != current_definition]
        return current_definition, other_definitions

    else:
        current_word = {word: definition for definition, word in terms_dict.items()}[term]
        other_words = [word for word, definition in terms_dict.items() if word != current_word]
        return current_word, other_words


async def send_or_remove_keyboard(message: Message, answers: list, term: str, current_state: str):
    if current_state == 'third_step':
        await message.answer(text=term, ReplyKeyboardRemove=True)
    else:
        await send_message_with_keyboard(message, term, answers)


async def check_user_answer(message: Message, state: FSMContext, send_term_and_definitions_function):
    user_data = await state.get_data()
    correct_answer = user_data["correct_answer"].strip().lower()
    user_answer = message.text.strip().lower()
    if user_answer == correct_answer or (len(user_answer) > 10 and user_answer[:-3] in correct_answer):
        await message.answer(text="Правильно!")
        await send_term_and_definitions_function()
    else:
        await message.answer(text="Неправильно! Попробуй еще раз.")


@router.message(RepeatWords.check_answer)
async def check_answer(message: Message, state: FSMContext):
    user_data = await state.get_data()
    term_key = user_data["term_key"]
    next_state = user_data["next_state"]
    send_term_and_definitions_function = partial(send_term_and_definitions, message, state, term_key,
                                                 next_state)
    await check_user_answer(message, state, send_term_and_definitions_function)


@router.message(RepeatWords.first_step, F.text.in_('Начать'))
async def first_step(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать слово, а ты выбирай определение")
    user_data = await state.get_data()
    await state.update_data(current_state='first_step')
    terms = user_data.get("terms", {})
    words = list(terms.keys())
    definitions = list(terms.values())
    random.shuffle(words)
    random.shuffle(definitions)
    user_data["words"] = words
    user_data["definitions"] = definitions
    user_data["term_key"] = "words"
    user_data["next_state"] = RepeatWords.second_step
    user_data["current_state"] = 'first_step'
    await state.update_data(user_data)
    await send_term_and_definitions(message, state, "words", RepeatWords.second_step)
    await state.set_state(RepeatWords.check_answer)


@router.message(RepeatWords.second_step, F.text.in_('перейти'))
async def second_step(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать определение, а ты выбирай слово")
    await state.update_data(current_state='second_step')
    await state.update_data(term_key='definitions')
    await state.update_data(next_state=RepeatWords.third_step)
    await send_term_and_definitions(message, state, "definitions", RepeatWords.third_step)
    await state.set_state(RepeatWords.check_answer)


@router.message(RepeatWords.third_step, F.text.in_('перейти'))
async def third_step(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать определение, а ты вводи правильное слово")
    await state.update_data(current_state='third_step')
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    definitions = list(terms.values())
    random.shuffle(definitions)
    user_data["definitions"] = definitions
    user_data["next_state"] = RepeatWords.finish
    await state.update_data(user_data)
    await send_term_and_definitions(message, state, "definitions", RepeatWords.finish)
    await state.set_state(RepeatWords.check_answer)


@router.message(RepeatWords.finish, F.text.in_('перейти'))
async def finish(message: Message, state: FSMContext):
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    repeated_terms = list(terms.keys())
    answer = await db.change_learn_type(telegram_id=str(message.from_user.id), terms=repeated_terms)

    await message.answer(
        text=f"а на этом повторение слов оконченно {answer}",
        reply_markup=make_row_keyboard(basic_buttons)
    )
    await state.clear()
