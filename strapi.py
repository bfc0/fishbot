from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
import logging
import aiohttp
import typing as t


@dataclass
class Cart:
    id: str
    userid: str
    cart_items: list[CartItem]

    def get_product_by_id(self, product_id: str) -> t.Optional[CartItem]:
        return next((item for item in self.cart_items if item.product_id == product_id), None)

    def total(self) -> Decimal:
        return sum(item.total() for item in self.cart_items)


@dataclass
class CartItem:
    id: str
    product_id: str
    amount: Decimal
    name: str
    price: Decimal

    def total(self) -> Decimal:
        return self.amount * self.price


class ApiError(Exception):
    pass


class Strapi:
    def __init__(self, token: str, base_url: str):
        self.token = token
        self.base_url = base_url
        self._session = aiohttp.ClientSession()

    async def set_email(self, userid: str, email: str) -> bool:
        cart = await self.get_create_cart_by_id(userid=userid)
        headers = self.generate_headers()
        url = self.base_url + f"/api/carts/{cart.id}"
        params = {
            "data": {
                "email": email
            }
        }
        async with self.session.put(url, json=params, headers=headers) as response:
            return response.status in (200, 204)

    async def add_to_cart(self, cart: Cart, product_id: str, amount: Decimal) -> dict[str, t.Any]:
        headers = self.generate_headers()
        url = self.base_url + f"/api/cart-items"

        logging.debug(f"inside add to cart, {cart=}")
        logging.debug(f"{product_id=}, {amount=}")
        if cart_item := cart.get_product_by_id(product_id):
            logging.debug(f"{cart_item=}")
            cart_item.amount += amount
            params = {
                "data": {
                    "product": cart_item.product_id,
                    "amount": str(cart_item.amount),
                    "cart": cart.id
                }
            }
            async with self.session.put(f"{url}/{cart_item.id}", json=params, headers=headers) as response:
                logging.debug(f"{response=}")
                return

        params = {
            "data": {
                "product": product_id,
                "amount": str(amount),
                "cart": cart.id
            }
        }
        async with self.session.post(url, json=params, headers=headers) as response:
            payload = await response.json()
            logging.debug(f"{payload=}")
            return payload

    async def delete_from_cart(self, cart_item_id: str) -> dict[str, t.Any]:
        headers = self.generate_headers()
        url = self.base_url + f"/api/cart-items/{cart_item_id}"

        async with self.session.delete(url, headers=headers) as response:
            logging.debug(f"{response=}")

    async def get_create_cart_by_id(self, userid: str) -> Cart:
        headers = self.generate_headers()
        url = self.base_url + "/api/carts/"
        params = {
            "filters[userid][$eq]": userid,
            "populate": "cart_items.product"
        }

        async with self.session.get(url, params=params, headers=headers) as response:
            payload = await response.json()
            if not payload.get("data"):
                logging.debug("Cart not found, creating one")
                cart = await self.create_cart_for(userid)
                return cart

            products = []
            if items_data := payload["data"][0].get("cart_items"):
                logging.debug(f"{items_data=}")
                products = [
                    CartItem(id=item["documentId"],
                             product_id=item["product"]["documentId"],
                             amount=Decimal(item["amount"]),
                             name=item["product"]["title"],
                             price=item["product"]["price"])
                    for item in items_data]

            return Cart(id=payload["data"][0]["documentId"], userid=userid, cart_items=products)

    async def create_cart_for(self, userid: str):
        headers = self.generate_headers()
        url = self.base_url + "/api/carts/"
        params = {
            "data": {
                "userid": str(userid)
            }
        }
        async with self.session.post(url, json=params, headers=headers) as response:
            payload = await response.json()
            if not payload.get("data"):
                raise ApiError("Failed to create cart")
            cart_data = payload["data"]
            return Cart(id=cart_data["documentId"], userid=cart_data["userid"], cart_items=[])

    async def get_products(self) -> dict[str, t.Any]:
        headers = self.generate_headers()
        url = self.base_url + "/api/products"

        async with self.session.get(url, headers=headers) as response:
            data = await response.json()
            return data

    async def get_product_by_id(self, id: str) -> dict[str, t.Any]:
        headers = self.generate_headers()
        url = self.base_url + f"/api/products/{id}?populate=image"

        async with self.session.get(url, headers=headers) as response:
            data = await response.json()

            product_data = {
                "id": data["data"]["id"],
                "documentId": data["data"]["documentId"],
                "title": data["data"]["title"],
                "description": data["data"]["description"],
                "price": data["data"]["price"],
                "image": data['data']['image']['formats']['small']['url'],
            }
            product_data["picture"] = await self.get_picture(self.base_url + product_data["image"])

            return product_data

    async def get_picture(self, url: str) -> bytes:
        async with self.session.get(url) as response:
            return await response.read()

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        return self._session

    async def close(self):
        if self._session is not None and not self._session.closed:
            await self._session.close()

    def generate_headers(self, **kwargs) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
        }
        for key, value in kwargs.items():
            headers[key] = str(value)

        return headers
