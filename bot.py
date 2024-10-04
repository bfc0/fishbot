from copy import copy
from decimal import Decimal
import logging
import re
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputFile
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiohttp
import redis.asyncio as redis
import asyncio
import argparse
from environs import Env
from strapi import Cart, Strapi

router = Router()


class UserStates(StatesGroup):
    idle = State()
    handling_menu = State()
    handling_description = State()
    in_cart = State()
    waiting_email = State()


@router.callback_query(F.data == "start")
async def return_to_start(callback: CallbackQuery, state: FSMContext, context: dict):
    await callback.answer("")
    await start(callback.message, state, context)
    await callback.message.delete()


@router.callback_query(F.data == "view_cart")
async def show_cart(callback: CallbackQuery, state: FSMContext, context: dict, bot: Bot):
    logging.debug("show cart")
    try:
        cart = await context["strapi"].get_create_cart_by_id(userid=str(callback.from_user.id))
    except aiohttp.ClientError:
        await show_error(callback, "Failed to get cart", "view_cart")
        return

    await callback.answer("hello")
    logging.debug(f"message= {callback.message}")

    builder = InlineKeyboardBuilder()
    for item in cart.cart_items:
        builder.button(text=f"Remove {item.name}:  {item.amount}",
                       callback_data=f"remove_{item.id}")

    (builder
     .button(text="Menu", callback_data="start")
     .button(text="Checkout", callback_data="ask_email")
     .adjust(1))
    await callback.message.answer(f"Total:  {cart.get_total_price()} roobels", reply_markup=builder.as_markup())
    await callback.message.delete()
    await state.set_state(UserStates.in_cart)


@router.callback_query(F.data == "ask_email")
async def ask_email(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    await callback.message.answer("Please enter your email")
    await state.set_state(UserStates.waiting_email)


@router.message(UserStates.waiting_email)
async def handle_email(message: types.Message, state: FSMContext, context: dict):
    email = message.text
    if not validate_email(email):
        await message.answer("Invalid email")
        await message.answer("Please enter your email")
        return

    if await context["strapi"].set_email(userid=str(message.from_user.id), email=email):
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(
                text="Menu", callback_data="start")]]
        )
        await message.answer("Thank you", reply_markup=markup)
        await state.set_state(UserStates.handling_menu)
        return
    await message.answer("Failed to set email")


@router.callback_query(F.data.startswith("remove_"))
async def delete_from_cart(callback: CallbackQuery, state: FSMContext, context: dict, bot: Bot):
    item_id = callback.data.replace("remove_", "")
    try:
        await context["strapi"].delete_from_cart(cart_item_id=item_id)
    except aiohttp.ClientError:
        await show_error(callback, "Failed to delete from cart", "view_cart", button_text="Back to cart")
        return

    await callback.answer()
    await show_cart(callback, state, context, bot)


@router.callback_query(UserStates.handling_description)
async def add_product_to_cart(callback: CallbackQuery, state: FSMContext, context: dict, bot: Bot):
    logging.debug("Adding product to cart")
    fish_id, amount = copy(callback.data).split(":")

    await callback.answer("Added to cart")
    userid = str(callback.from_user.id)
    strapi: Strapi = context["strapi"]
    try:
        cart: Cart = await strapi.get_create_cart_by_id(userid=userid)
        logging.debug(f"{cart=}")
        result = await strapi.add_to_cart(cart=cart, product_id=fish_id, amount=Decimal(amount))
    except aiohttp.ClientError:
        await show_error(callback, "Failed to add to cart", "view_cart", button_text="Back to cart")
        return

    logging.debug(f"{result=}")
    await show_cart(callback, state, context, bot)


@router.callback_query(F.data.startswith("fish_"))
async def show_product(callback: CallbackQuery, state: FSMContext, context: dict):
    fish_id = copy(callback.data).replace("fish_", "")
    strapi: Strapi = context["strapi"]
    try:
        fish_data = await strapi.get_product_by_id(fish_id)
    except aiohttp.ClientError:
        await show_error(callback, "Failed to get fish", callback.data)
        return

    logging.debug(f"message (in menu_cb) {callback.message}")
    builder = (InlineKeyboardBuilder()
               .button(text="1", callback_data=f"{fish_id}:1")
               .button(text="5", callback_data=f"{fish_id}:5")
               .button(text="10", callback_data=f"{fish_id}:10")
               .row(InlineKeyboardButton(text="To Cart", callback_data="view_cart"))
               .row(InlineKeyboardButton(text="Back", callback_data="start")))

    await callback.answer("")
    await callback.message.answer_photo(
        photo=types.BufferedInputFile(
            fish_data["picture"], filename="fish.png"),
        reply_markup=builder.as_markup(), caption=fish_data["description"])
    await callback.message.delete()
    await state.set_state(UserStates.handling_description)


@router.message(CommandStart())
async def start(message: types.Message, state: FSMContext, context: dict) -> None:
    keyboard = InlineKeyboardBuilder().button(
        text="Retry", callback_data="start").as_markup()
    try:
        response = await context["strapi"].get_products()
    except aiohttp.ClientError:
        await message.answer("Failed to get fish", reply_markup=keyboard)
        return
    if "data" not in response:
        await message.answer("Out of fish :(", reply_markup=keyboard)
        return

    fish_data = response["data"]
    logging.debug(f"{fish_data=}")

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=fish["title"],
                                  callback_data=f"fish_{fish['documentId']}")] for fish in fish_data
        ]
    )

    await message.answer("Welcome to the shop!", reply_markup=markup)
    await state.set_state(UserStates.handling_menu)


async def show_error(callback: CallbackQuery, error_message: str, callback_data: str, button_text="Retry"):
    logging.error(f"Error occurred: {error_message}")
    keyboard = InlineKeyboardBuilder().button(
        text=button_text, callback_data=callback_data).as_markup()
    await callback.answer(error_message)
    await callback.message.answer(error_message, reply_markup=keyboard)
    await callback.message.delete()


def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


async def main():
    env = Env()
    env.read_env()
    redis_host = env.str("REDIS_HOST")
    tg_token = env.str("TG_TOKEN")
    cms_token = env.str("CMS_TOKEN")
    cms_url = env.str("CMS_URL", "http://localhost:1337")
    parser = argparse.ArgumentParser()
    parser.add_argument("--loglevel", default="INFO", help="log level")
    args = parser.parse_args()

    context = {
        "cms_token": cms_token,
        "strapi": Strapi(token=cms_token, base_url=cms_url),
    }

    client = redis.Redis.from_url(f"redis://{redis_host}")
    storage = RedisStorage(client)

    bot = Bot(token=tg_token)
    dp = Dispatcher(storage=storage, context=context)
    dp.include_router(router)
    logging.basicConfig(level=args.loglevel.upper())
    logging.debug("Starting bot")

    try:
        await dp.start_polling(bot)
    finally:
        await context["strapi"].close()


if __name__ == "__main__":
    asyncio.run(main())
