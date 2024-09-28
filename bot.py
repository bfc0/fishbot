from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputFile
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.methods.delete_message import DeleteMessage
import redis.asyncio as redis
import asyncio
from environs import Env
from req import get_data, get_fish_by_id

router = Router()


class UserStates(StatesGroup):
    idle = State()
    handling_menu = State()
    handling_description = State()


@router.callback_query(F.data == "start")
async def back_to_start(callback: CallbackQuery, state: FSMContext, context: dict):
    await callback.answer("")
    await start(callback.message, state, context)


@router.callback_query(F.data.startswith("fish_"))
async def menu_cb(callback: CallbackQuery, state: FSMContext, context: dict):
    fish_id = callback.data.replace("fish_", "")
    fish_data = await get_fish_by_id(fish_id, context["cms_token"])

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Back", callback_data="start")],
        ]
    )

    await callback.message.edit_text(fish_data["description"], reply_markup=kb)
    await callback.answer("")
    await callback.message.answer_photo(photo=types.BufferedInputFile(fish_data["picture"], filename="fish.png"))
    await state.set_state(UserStates.handling_description)


@router.message(CommandStart())
async def start(message: types.Message, state: FSMContext, context: dict) -> None:

    store_content = await get_data(context["cms_token"])
    fishes = store_content["data"]
    print(message.chat.id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=str(fish["attributes"]["title"]),
                                  callback_data=f"fish_{fish['id']}")] for i, fish in enumerate(fishes)
        ]
    )

    await message.reply("hello ", reply_markup=kb)
    await state.set_state(UserStates.handling_menu)


async def main():
    env = Env()
    env.read_env()
    redis_host = env.str("REDIS_HOST")
    tg_token = env.str("TG_TOKEN")
    cms_token = env.str("CMS_TOKEN")
    context = {
        'cms_token': cms_token
    }

    client = redis.Redis.from_url(f"redis://{redis_host}")
    storage = RedisStorage(client)

    bot = Bot(token=tg_token)
    dp = Dispatcher(storage=storage, context=context)
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
