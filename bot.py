import os, math, logging
import logging.config
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import SESSION, API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL, PORT
from utils import temp
from typing import Union, Optional, AsyncGenerator
from pyrogram import types
from datetime import datetime
from pytz import timezone
from pyrogram.errors import BadRequest, Unauthorized, FloodWait
from plugins.__init__ import web_server
from aiohttp import web
import asyncio

# Get logging configurations
logging.config.fileConfig("logging.conf")
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("cinemagoer").setLevel(logging.ERROR)
LOGGER = logging.getLogger(__name__)
TIMEZONE = (os.environ.get("TIMEZONE", "Asia/Kolkata"))

class Bot(Client):

    def __init__(self):
        super().__init__(
            name=SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=300,
            plugins={"root": "plugins"},
            sleep_threshold=10,
        )

    async def start(self):
        try:
            b_users, b_chats = await db.get_banned()
            temp.BANNED_USERS = b_users
            temp.BANNED_CHATS = b_chats        

            await super().start()

        except FloodWait as e:
            logging.warning(f"FloodWait detected! Sleeping for {e.value} seconds...")
            await asyncio.sleep(e.value)
            return await self.start()

        await Media.ensure_indexes()
        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        temp.B_LINK = me.mention
        self.username = '@' + me.username

        curr = datetime.now(timezone(TIMEZONE))
        date = curr.strftime('%d %B, %Y')
        time = curr.strftime('%I:%M:%S %p')

        # Web server
        app = web.AppRunner(await web_server())
        await app.setup()
        bind_address = "0.0.0.0"
        await web.TCPSite(app, bind_address, PORT).start()

        logging.info(f"{me.first_name} started Pyrogram v{__version__} (Layer {layer}) on @{me.username}")

        if LOG_CHANNEL:
            try:
                await self.send_message(
                    LOG_CHANNEL,
                    text=(
                        f"<b>{me.mention} is Restarted !!\n\n"
                        f"📅 Date : <code>{date}</code>\n"
                        f"⏰ Time : <code>{time}</code>\n"
                        f"🌐 Timezone : <code>{TIMEZONE}</code>\n\n"
                        f"🉐 Version : <code>v{__version__} (Layer {layer})</code></b>"
                    )
                )
            except Unauthorized:
                LOGGER.warning("Bot isn't able to send message to LOG_CHANNEL")
            except BadRequest as e:
                LOGGER.error(e)

    async def stop(self, *args):
        await super().stop()
        me = await self.get_me()
        logging.info(f"{me.first_name} ♻️Restarting...")

    async def iter_messages(self, chat_id: Union[int, str], limit: int, offset: int = 0) -> Optional[AsyncGenerator["types.Message", None]]:
        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return
            messages = await self.get_messages(chat_id, list(range(current, current + new_diff + 1)))
            for message in messages:
                yield message
                current += 1


app = Bot()

# Safe run with FloodWait handling
while True:
    try:
        app.run()
    except FloodWait as e:
        logging.warning(f"Global FloodWait! Sleeping {e.value} seconds.")
        asyncio.sleep(e.value)
        continue
