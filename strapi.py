import logging
import aiohttp
import typing as t
DEFAULT_URL = "http://localhost:1337"


class Strapi:
    def __init__(self, token: str, base_url: str = DEFAULT_URL):
        self.token = token
        self.base_url = base_url
        self._session = aiohttp.ClientSession()

    async def add_to_cart(self, cart_id: str, product_id: str) -> dict[str, t.Any]:
        headers = self.generate_headers()
        url = self.base_url + f"/api/cart-items"
        params = {
            "data": {
                # "cart": cart_id,
                "product": product_id,
                "amount": 1,
                "connect": [cart_id]
            }
        }
        async with self.session.post(url, json=params, headers=headers) as response:
            print(response)
            payload = await response.json()
            print(payload)
            return payload

    async def get_create_cart_by_id(self, userid: str) -> dict[str, t.Any]:
        headers = self.generate_headers()
        url = self.base_url + "/api/carts/?populate=*"
        params = {
            "filters[userid][$eq]": userid
        }
        async with self.session.get(url, json=params, headers=headers) as response:
            payload = await response.json()
            print(f"{payload=}")
            if not payload.get("data"):
                logging.debug("Cart not found, creating one")
                cart = await self.create_cart_for(userid)
                return cart

            return payload

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
            return payload

    async def get_products(self) -> dict[str, t.Any]:
        headers = self.generate_headers()
        url = self.base_url + "/api/products"

        async with self.session.get(url, headers=headers) as response:
            data = await response.json()
            return data

    async def get_fish_by_id(self, id: str) -> dict[str, t.Any]:
        headers = self.generate_headers()
        url = self.base_url + f"/api/products/{id}?populate=image"

        async with self.session.get(url, headers=headers) as response:
            data = await response.json()
            print(f"fish {data=}")

            fish_data = {
                "id": data["data"]["id"],
                "title": data["data"]["title"],
                "description": data["data"]["description"],
                "price": data["data"]["price"],
                "image": data["data"]["image"]["data"][0]["attributes"]["url"]
            }
            fish_data["picture"] = await self.get_picture(self.base_url + fish_data["image"])

            return fish_data

    async def get_picture(self, url: str) -> bytes:
        async with self.session.get(url) as response:
            return await response.read()

    @property
    def session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        return self._session

    def generate_headers(self, **kwargs) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        for key, value in kwargs.items():
            headers[key] = str(value)

        return headers
