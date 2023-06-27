from aiogram.fsm.state import StatesGroup, State


class AddTerms(StatesGroup):
    term_type_chosen = State()
    add_terms = State()


class UserProgress(StatesGroup):
    choosing_term_type = State()
    type_chosen = State()


class LearnTrainingState(StatesGroup):
    chosen_type_object = State()
    get_words_state = State()
    pre_learn_part = State()  # only in learn training
    first_step = State()
    check_answer = State()
    second_step = State()
    third_step = State()
    finish = State()


class RepeatState(StatesGroup):
    chosen_type_object = State()
    get_words_state = State()
    first_step = State()
    check_answer = State()
    second_step = State()
    third_step = State()
    finish = State()


class RepeatLearnedWordsState(StatesGroup):
    chosen_type_object = State()
    get_words_state = State()
    first_step = State()
    check_answer = State()
    second_step = State()  # here no third_state
    finish = State()
