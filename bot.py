import sys
import glob
import importlib
import asyncio
import time
from pathlib import Path
from datetime import datetime, date
import pytz
from aiohttp import web

from pyrogram import Client, __version__, idle
from pyrogram.raw.all import layer
from pyrogram.errors import FloodWait

from database.ia_filterdb import Media, Media2
from database.users_chats_db import db
from utils import temp
from info import *
from Script import script

# Logging setup
import logging
import logging.config
logging.config.fileConfig("logging.conf")
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("pymongo").setLevel(logging.WARNING)

# Import web server & tasks
from plugins import web_server, keep_alive, check_expired_premium

# PIL Limit Fix
from PIL import Image
Image.MAX_IMAGE_PIXELS = 500_000_000

# Path for plugins
files = glob.glob("plugins/*.py")

class Bot(Client):
    def __init__(self):
        super().__init__(
            name=SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=300,
            sleep_threshold=10,
            plugins=None  # We load manually
        )

bot = Bot()


async def start_bot():
    print("\n\nInitializing Bot...")
    await bot.start()

    # Load plugins manually (DreamxBotz style)
    for file in files:
        plugin_name = Path(file).stem
        spec = importlib.util.spec_from_file_location(
            f"plugins.{plugin_name}",
            Path(f"plugins/{plugin_name}.py")
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[f"plugins.{plugin_name}"] = module
        print("Imported Plugin =>", plugin_name)

    # Load banned users & chats
    b_users, b_chats = await db.get_banned()
    temp.BANNED_USERS = b_users
    temp.BANNED_CHATS = b_chats

    # Ensure indexes
    await Media.ensure_indexes()
    if MULTIPLE_DB:
        await Media2.ensure_indexes()
        print("Multiple DB Mode Enabled")
    else:
        print("Single DB Mode Enabled")

    # Bot information
    me = await bot.get_me()
    temp.ME = me.id
    temp.U_NAME = me.username
    temp.B_NAME = me.first_name
    temp.B_LINK = me.mention

    logging.info(f"{me.first_name} started with Pyrogram v{__version__} (Layer {layer})")
    logging.info(script.LOGO)

    # Restart log message
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    date_today = date.today()
    time_now = now.strftime("%I:%M:%S %p")

    try:
        await bot.send_message(LOG_CHANNEL, script.RESTART_TXT.format(temp.B_LINK, date_today, time_now))
    except Exception as e:
        logging.warning(f"Cannot send log message: {e}")

    # Web Server
    runner = web.AppRunner(await web_server())
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()

    # Background Tasks
    bot.loop.create_task(keep_alive())
    bot.loop.create_task(check_expired_premium(bot))

    await idle()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    while True:
        try:
            loop.run_until_complete(start_bot())
            break

        except FloodWait as e:
            print(f"FloodWait! Sleeping for {e.value} seconds...")
            time.sleep(e.value)

        except KeyboardInterrupt:
            print("Bot Stopped.")
            break
