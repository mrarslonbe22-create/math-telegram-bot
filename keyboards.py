from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    buttons = [
        [KeyboardButton(text="📚 Testni boshlash")],
        [KeyboardButton(text="📊 Shaxsiy natijalar")],
        [KeyboardButton(text="🏆 Kunlik reyting")],
        [KeyboardButton(text="✏️ Test qo'shish")],
        [KeyboardButton(text="🎯 Test to'plamlari")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def option_buttons(options):
    buttons = [[InlineKeyboardButton(text=str(opt), callback_data=f"ans_{idx}")] for idx, opt in enumerate(options)]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def custom_tests_list(collections):
    buttons = []
    for cid, name in collections:
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"start_custom_{cid}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]])
