from decimal import Decimal
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
    in_cart = State()


@router.callback_query(F.data == "start")
async def back_to_start(callback: CallbackQuery, state: FSMContext, context: dict):
    await callback.answer("")
    await start(callback.message, state, context)


@router.callback_query(F.data == "view_cart")
async def show_cart(callback: CallbackQuery, state: FSMContext, context: dict, bot: Bot):
    logging.debug("show cart")
    cart = await context["strapi"].get_create_cart_by_id(userid=str(callback.from_user.id))
    await callback.answer("hello")
    logging.debug(f"message= {callback.message}")

    await callback.message.answer("Cart:")
    await callback.message.answer(str(cart))
    await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id-1)
    await callback.message.delete()

    for item in cart.cart_items:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Remove",
                                      callback_data=f"remove_{item.id}")]
            ]
        )
        await callback.message.answer(f"{item.name}:  {item.amount}", reply_markup=kb)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Checkout", callback_data="checkout")],
            [InlineKeyboardButton(text="Products", callback_data="start")],
        ]
    )
    await callback.message.answer(f"Total:  {cart.total()}", reply_markup=kb)
    await state.set_state(UserStates.in_cart)


@router.callback_query(F.data.startswith("remove_"))
async def delete_from_cart(callback: CallbackQuery, state: FSMContext, context: dict, bot: Bot):
    item_id = callback.data.replace("remove_", "")
    await context["strapi"].delete_from_cart(cart_item_id=item_id)
    await show_cart(callback, state, context, bot)


@router.callback_query(UserStates.handling_description)
async def add_product_to_cart(callback: CallbackQuery, state: FSMContext, context: dict):
    logging.debug("Adding product to cart")
    fish_id, amount = callback.data.split(":")
    await callback.answer("Added to cart")
    await callback.message.answer(f"{fish_id}:  {amount}")
    userid = str(callback.from_user.id)
    strapi: Strapi = context["strapi"]
    cart: Cart = await strapi.get_create_cart_by_id(userid=userid)
    logging.debug(f"{cart=}")
    result = await strapi.add_to_cart(cart=cart, product_id=fish_id, amount=Decimal(amount))
    logging.debug(f"{result=}")


@router.callback_query(F.data.startswith("fish_"))
async def menu_cb(callback: CallbackQuery, state: FSMContext, context: dict):
    fish_id = callback.data.replace("fish_", "")
    strapi: Strapi = context["strapi"]
    fish_data = await strapi.get_fish_by_id(fish_id)

    logging.debug(f"message (in menu_cb) {callback.message}")
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
        await message.answer("Out of fish :(")
        return

    fish_data = response["data"]
    logging.debug(f"{fish_data=}")

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

    try:
        await dp.start_polling(bot)
    finally:
        await context["strapi"].close()


if __name__ == "__main__":
    asyncio.run(main())
