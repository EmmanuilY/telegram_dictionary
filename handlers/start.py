from aiogram import Router
from aiogram.filters.command import Command
from aiogram.filters.text import Text
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove, ErrorEvent
from loguru import logger

from keyboards.simple_row import make_row_keyboard, start_buttons
from db.db import db

router = Router()



@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    registration = await db.add_user(str(message.from_user.id), str(message.from_user.first_name))
    match registration:
        case 'register_user':
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

                reply_markup=make_row_keyboard(start_buttons)
            )


@router.message(Command("cancel"))
@router.message(Text(text="отмена", ignore_case=True))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        text="Действие отменено",
        reply_markup=ReplyKeyboardRemove()
    )


# @router.errors()
# async def error_handler(exception: ErrorEvent):
#     error = exception.exception
#     message = exception.update.message
#     logger.error(
#         f"{error}, user message: {message.text}  user_id: {message.from_user.id}"
#     )
#     await message.answer(
#         text="Что-то пошло не так, попробуйте снова",
#         keyboard_options=start_buttons,
#     )
