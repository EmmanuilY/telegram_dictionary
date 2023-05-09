from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove

from keyboards.simple_row import make_row_keyboard

from model.db import DB
import random


db = DB()
router = Router()

available_term_types =  ["term", "english_word"]



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
    await state.set_state(LearnTerms.choosing_type_object)


@router.message(LearnTerms.choosing_type_object, F.text.in_(available_term_types))
async def type_chosen(message: Message, state: FSMContext):
    await state.update_data(chosen_term_type=message.text.lower())
    await message.answer(
        text="Ниже слова"
    )
    terms = await db.get_term(telegram_id=str(message.from_user.id), term_type=message.text.lower())
    await state.update_data(terms=terms)

    for word, definition in terms.items():
        await message.answer(
            text=f"{word} - {definition}"
        )
    await message.answer(
        text="Нужен замоповтор?",
        reply_markup=make_row_keyboard(['Повтор для себя'])
    )
    await state.set_state(LearnTerms.pre_learn_terms)


@router.message(LearnTerms.choosing_type_object)
async def type_chosen_incorrectly(message: Message):
    await message.answer(
        text="Я не знаю типа.\n\n"
             "Пожалуйста, выберите одно из названий из списка ниже:",
        reply_markup=make_row_keyboard(available_term_types)
    )


@router.message(LearnTerms.pre_learn_terms, F.text.in_('Повтор для себя'))
async def pre_learn_part(message: Message, state: FSMContext):
    await message.answer(
        text="Ниже слова................................................................................................"
    )
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    for word, definition in terms.items():
        await message.answer(
            text=f"{word}     \-      ||{definition}||", parse_mode="MarkdownV2"
        )
    await message.answer(
        text="Начать?",
        reply_markup=make_row_keyboard(['Начать'])
    )
    await state.set_state(LearnTerms.first_step)


@router.message(LearnTerms.first_step, F.text.in_('Начать'))
async def first_learn_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать слово, а ты выбирай определение")
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    user_data["words"] = list(terms.keys())  # сохраняем список слов в пользовательских данных
    await state.update_data(user_data)
    await send_word_and_options(message, state)  # отправляем первое слово и определения
    await state.set_state(LearnTerms.check_answer)  # переходим к состоянию проверки ответа


async def send_word_and_options(message: Message, state: FSMContext):
    user_data = await state.get_data()
    words = user_data["words"]

    if not words:  # если слова закончились, возвращаемся к первому шагу
        await message.answer(text="перейти ко второму этапу?", reply_markup=make_row_keyboard(['перейти']))
        await state.set_state(LearnTerms.second_step)
        return

    word = words.pop(0)  # берем первое слово и удаляем его из списка
    terms = user_data.get("terms", {})
    correct_definition = terms[word]
    other_definitions = [v for k, v in terms.items() if k != word]

    options = random.sample([*other_definitions, correct_definition], 4)  # выбираем 4 определения, включая правильное
    random.shuffle(options)  # перемешиваем определения

    await message.answer(text=word, reply_markup=make_row_keyboard(options))
    await state.update_data(chosen_word=word, correct_definition=correct_definition, words=words)


@router.message(LearnTerms.check_answer)
async def check_user_answer(message: Message, state: FSMContext):
    user_data = await state.get_data()
    correct_definition = user_data["correct_definition"]

    if message.text == correct_definition:  # если ответ пользователя правильный
        await message.answer(text="Правильно!")
        await send_word_and_options(message, state)  # отправляем следующее слово и определения
    else:
        await message.answer(text="Неправильно! Попробуй еще раз.")  # пользователь может попробовать еще раз


@router.message(LearnTerms.second_step, F.text.in_('перейти'))
async def second_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать определение, а ты выбирай слово")
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    user_data["definitions"] = list(terms.values())  # сохраняем список определений в пользовательских данных
    await state.update_data(user_data)
    await send_definition_and_options(message, state)  # отправляем первое определение и слова
    await state.set_state(LearnTerms.check_answer_second_step)  # переходим к состоянию проверки ответа на втором этапе


async def send_definition_and_options(message: Message, state: FSMContext):
    user_data = await state.get_data()
    definitions = user_data["definitions"]

    if not definitions:  # если определения закончились, завершаем второй этап
        await message.answer(text="Второй этап завершен! Вы молодец!", reply_markup=make_row_keyboard(['перейти']))
        await state.set_state(LearnTerms.third_step)
        return
    terms = user_data.get("terms", {})
    definition = definitions.pop(0)  # берем первое определение и удаляем его из списка
    correct_word = [k for k, v in terms.items() if v == definition][0]
    other_words = [k for k, v in terms.items() if k != correct_word]

    options = random.sample([*other_words, correct_word], 4)  # выбираем 4 слова, включая правильное
    random.shuffle(options)  # перемешиваем слова

    await message.answer(text=definition, reply_markup=make_row_keyboard(options))
    await state.update_data(chosen_definition=definition, correct_word=correct_word, definitions=definitions)


@router.message(LearnTerms.check_answer_second_step)
async def check_user_answer_second_step(message: Message, state: FSMContext):
    user_data = await state.get_data()
    correct_word = user_data["correct_word"]

    if message.text == correct_word:  # если ответ пользователя правильный
        await message.answer(text="Правильно!")
        await send_definition_and_options(message, state)  # отправляем следующее определение и слова
    else:
        await message.answer(text="Неправильно! Попробуй еще раз.")  # пользователь может попробовать еще раз


@router.message(LearnTerms.third_step,
                F.text.in_('перейти'))  # измените текст, который пользователь отправляет для начала третьего этапа
async def third_part(message: Message, state: FSMContext):
    await message.answer(text="Сейчас я буду тебе присылать определение, а ты вводи правильное слово")
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    user_data["definitions"] = list(terms.values())  # сохраняем список определений в пользовательских данных
    await state.update_data(user_data)
    await send_definition(message, state)  # отправляем первое определение
    await state.set_state(LearnTerms.check_answer_third_step)  # переходим к состоянию проверки ответа на третьем этапе


async def send_definition(message: Message, state: FSMContext):
    user_data = await state.get_data()
    definitions = user_data["definitions"]

    if not definitions:  # если определения закончились, завершаем третий этап
        await message.answer(text="Третий этап завершен! Вы молодец!", reply_markup=make_row_keyboard(['я молодец!']))
        await state.set_state(LearnTerms.finish)
        return
    terms = user_data.get("terms", {})
    definition = definitions.pop(0)  # берем первое определение и удаляем его из списка
    correct_word = [k for k, v in terms.items() if v == definition][0]

    await message.answer(text=definition)
    await state.update_data(chosen_definition=definition, correct_word=correct_word, definitions=definitions)


@router.message(LearnTerms.check_answer_third_step)
async def check_user_answer_third_step(message: Message, state: FSMContext):
    user_data = await state.get_data()
    correct_word = user_data["correct_word"]

    if message.text.lower() == correct_word.lower():  # если ответ пользователя правильный
        await message.answer(text="Правильно!")
        await send_definition(message, state)  # отправляем следующее определение
    else:
        await message.answer(text="Неправильно! Попробуй еще раз.")  # пользователь может попробовать еще раз


@router.message(LearnTerms.finish, F.text.in_('я молодец!'))
async def finish(message: Message, state: FSMContext):
    user_data = await state.get_data()
    terms = user_data.get("terms", {})
    learn_terms = list(terms.keys())
    answer = await db.change_learn_type(telegram_id=str(message.from_user.id), terms=learn_terms)

    await message.answer(
        text=  f"а этом изучение всех слов оконченно {answer}", reply_markup=make_row_keyboard(['/learn_words', '/add_terms'])
    )
    await state.clear()
