## Fishbot telegram bot

Бот занимается продажей товаров, которые были созданы в CMS.

Пользователь может просматривать товары, добавлять и удалять их из корзины

[DEMO](https://t.me/fishsalesbot)
### Как установить

Заполнить файл .env
```
REDIS_HOST=localhost
TG_TOKEN=Токен от бота
CMS_TOKEN=токен от Страпи
```

Установить venv
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Установить редис
```
docker run -d -p 6379:6379 redis 
```
Установить Страпи - см на их [сайте](https://docs.strapi.io/dev-docs/quick-start)

### Запустить

```
python bot.py
```