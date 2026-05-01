from aiogram.fsm.state import StatesGroup, State

class RegisterState(StatesGroup):
    waiting_for_first_name = State()
    waiting_for_last_name = State()

class TestState(StatesGroup):
    taking_test = State()

class AddTestState(StatesGroup):
    waiting_for_collection_name = State()
    waiting_for_question = State()
    waiting_for_options = State()
    waiting_for_correct_option = State()
    waiting_for_more = State()
