import asyncio
import aiohttp
import typing as t
CMS_URL = "http://localhost:1337/api/products"
SITE_PREFIX = "http://localhost:1337"


async def get_data(token: str) -> dict[str, t.Any]:
    headers = {
        'Authorization': f'Bearer {token}'
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(CMS_URL, headers=headers) as response:
            data = await response.json()
            # pprint.pprint(data)
            return data


async def get_fish_by_id(id: str, token: str) -> dict[str, t.Any]:
    headers = {
        'Authorization': f'Bearer {token}'
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://localhost:1337/api/products/{id}?populate=picture", headers=headers) as response:
            data = await response.json()
            print(data)

            fish_data = {
                "id": data["data"]["id"],
                "title": data["data"]["attributes"]["title"],
                "description": data["data"]["attributes"]["description"],
                "price": data["data"]["attributes"]["price"],
                "picture": data["data"]["attributes"]["picture"]["data"][0]["attributes"]["url"]
            }
            pic_url = SITE_PREFIX+fish_data["picture"]
            print(f"{pic_url=}")
            fish_data["picture"] = await get_picture(pic_url, session)
            return fish_data


async def get_picture(url: str, session: aiohttp.ClientSession) -> bytes:
    async with session.get(url) as response:
        return await response.read()

if __name__ == "__main__":
    asyncio.run(get_data())
