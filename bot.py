import logging
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
from strapi import Cart, Strapi

router = Router()


class UserStates(StatesGroup):
    idle = State()
    handling_menu = State()
    handling_description = State()


@router.callback_query(F.data == "start")
async def back_to_start(callback: CallbackQuery, state: FSMContext, context: dict):
    await callback.answer("")
    await start(callback.message, state, context)


@router.callback_query(UserStates.handling_description)
async def add_product_to_cart(callback: CallbackQuery, state: FSMContext, context: dict):
    logging.debug("Adding product to cart")
    fish_id, amount = callback.data.split(":")
    await callback.answer("Added to cart")
    await callback.message.answer(f"{fish_id}:  {amount}")
    userid = str(callback.from_user.id)
    strapi = context["strapi"]
    cart: Cart = await strapi.get_create_cart_by_id(userid=userid)
    logging.debug(f"{cart=}")
    result = await strapi.add_to_cart(cart=cart, product_id=fish_id, amount=amount)
    logging.debug(f"{result=}")


@router.callback_query(F.data.startswith("fish_"))
async def menu_cb(callback: CallbackQuery, state: FSMContext, context: dict):
    fish_id = callback.data.replace("fish_", "")
    strapi: Strapi = context["strapi"]
    fish_data = await strapi.get_fish_by_id(fish_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data=f"{fish_id}:1"),
                InlineKeyboardButton(text="5", callback_data=f"{fish_id}:5"),
                InlineKeyboardButton(text="10", callback_data=f"{fish_id}:10"),
            ],
            [InlineKeyboardButton(text="To Cart", callback_data="view_cart")],
            [InlineKeyboardButton(text="Back", callback_data="start")],
        ]
    )

    await callback.message.edit_text(fish_data["description"])
    await callback.message.answer_photo(photo=types.BufferedInputFile(fish_data["picture"], filename="fish.png"), reply_markup=kb)
    await callback.answer("")
    await state.set_state(UserStates.handling_description)


@router.message(CommandStart())
async def start(message: types.Message, state: FSMContext, context: dict) -> None:

    response = await context["strapi"].get_products()
    if "data" not in response:
        await message.reply("Рыба закончилась :(")
        return

    fish_data = response["data"]
    print(f"{fish_data=}")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=fish["title"],
                                  callback_data=f"fish_{fish['documentId']}")] for fish in fish_data
        ]
    )

    await message.answer("Welcome to the shop!", reply_markup=kb)
    await state.set_state(UserStates.handling_menu)


async def main():
    env = Env()
    env.read_env()
    redis_host = env.str("REDIS_HOST")
    tg_token = env.str("TG_TOKEN")
    cms_token = env.str("CMS_TOKEN")
    context = {
        "cms_token": cms_token,
        "strapi": Strapi(token=cms_token),

    }

    client = redis.Redis.from_url(f"redis://{redis_host}")
    storage = RedisStorage(client)

    bot = Bot(token=tg_token)
    dp = Dispatcher(storage=storage, context=context)
    dp.include_router(router)
    logging.basicConfig(level=logging.DEBUG)
    logging.debug("Starting bot")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
