from aiogram.fsm.state import State, StatesGroup


class AddAccountFSM(StatesGroup):
    choose_platform = State()
    choose_auth_type = State()
    enter_username = State()
    enter_session_data = State()
