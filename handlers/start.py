from aiogram import Router
from aiogram.filters.command import Command
from aiogram.filters.text import Text
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from loguru import logger

from keyboards.simple_row import make_row_keyboard
from model.db import DB

router = Router()
db = DB()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    logger.info(f"Мне написали : {message.from_user.id} {message.from_user.username}")
    registration = await db.add_user(str(message.from_user.id), str(message.from_user.first_name))
    match registration:
        case 'ok':
            await message.answer(
                text=f"Воу, вы только что зарегались! {message.from_user.first_name}\n"
                     "Что вы хотите делать \n?"
                     "учить слова (/learn_words), добавить слова (/add_terms)  ",

                reply_markup=make_row_keyboard(['/learn_words', '/add_terms'])
            )

        case 'exists':
                await message.answer(
                    text="Мы уже вас знаем ! \n"
                         "Что вы хотите делать? \n"
                         "учить слова или добавить слова .",

                    reply_markup=make_row_keyboard(['/learn_words', '/add_terms', '/check_progress'])
                )


@router.message(Command("cancel"))
@router.message(Text(text="отмена", ignore_case=True))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        text="Действие отменено",
        reply_markup=ReplyKeyboardRemove()
    )
