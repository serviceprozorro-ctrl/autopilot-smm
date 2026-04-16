from aiogram.fsm.state import State, StatesGroup


class AddAccountFSM(StatesGroup):
    choose_platform = State()
    choose_auth_type = State()
    # Login + Password flow
    enter_username = State()
    enter_password = State()
    # Cookies flow
    enter_username_cookies = State()
    enter_session_data = State()
    # QR Code flow
    qr_awaiting_scan = State()
    qr_enter_username = State()
    # API key flow
    enter_username_api = State()
    enter_api_key = State()
