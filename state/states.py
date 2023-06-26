from aiogram.fsm.state import StatesGroup, State


class BaseTrainingsStatesGroup(StatesGroup):
    choosing_type_object = State()
    choosing_repeat_option = State()
    first_step = State()
    check_answer = State()
    second_step = State()
    third_step = State()
    finish = State()

class RepeatTraining(BaseTrainingsStatesGroup):
    pass