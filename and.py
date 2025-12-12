import os
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_ID = 35292658
API_HASH = "a14fdc9ed8e1456c9570381024954dOb"
BOT_TOKEN = "8354690348:AAFp1NFVp2QjTMfHvXQNLaViNeqfFpSU8Zg"

app = Client("forwarder_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

SOURCE_CHAT = -1003314001250
TARGET_CHAT = -1003337634077

START_MSG_ID = None
END_MSG_ID = None

waiting_for_source = False
waiting_for_target = False
waiting_for_start = False
waiting_for_end = False

video_storage = []
preview_videos = []  # will hold videos for preview


def extract_number(caption: str):
    if not caption:
        return None
    match = re.match(r"^\s*(\d+)\.", caption)
    if match:
        return int(match.group(1))
    return None


# ---------------- BUTTON MENU ----------------

@app.on_message(filters.command("start"))
async def start(client, message):
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 Set SOURCE Group", callback_data="set_source")],
        [InlineKeyboardButton("🔴 Set TARGET Group", callback_data="set_target")],
        [InlineKeyboardButton("🟢 Set START Point", callback_data="set_start")],
        [InlineKeyboardButton("🟠 Set END Point", callback_data="set_end")],
        [InlineKeyboardButton("👁 Preview Range", callback_data="preview_range")],
    ])
    await message.reply("Choose an option:", reply_markup=buttons)


@app.on_callback_query()
async def callback(client, cb):
    global waiting_for_source, waiting_for_target, waiting_for_start, waiting_for_end

    if cb.data == "set_source":
        waiting_for_source = True
        waiting_for_target = waiting_for_start = waiting_for_end = False
        await cb.message.reply("📥 Forward any message from SOURCE group.")

    elif cb.data == "set_target":
        waiting_for_target = True
        waiting_for_source = waiting_for_start = waiting_for_end = False
        await cb.message.reply("📤 Forward any message from TARGET group.")

    elif cb.data == "set_start":
        waiting_for_start = True
        waiting_for_source = waiting_for_target = waiting_for_end = False
        await cb.message.reply("🟢 Forward the *START video* (example: video 2).")

    elif cb.data == "set_end":
        waiting_for_end = True
        waiting_for_source = waiting_for_target = waiting_for_start = False
        await cb.message.reply("🟠 Forward the *END video* (example: video 8).")

    elif cb.data == "preview_range":
        await preview_range_handler(cb)


@app.on_message(filters.forwarded)
async def capture_forwarded(client, message):
    global SOURCE_CHAT, TARGET_CHAT, START_MSG_ID, END_MSG_ID
    global waiting_for_source, waiting_for_target, waiting_for_start, waiting_for_end

    # SOURCE
    if waiting_for_source:
        SOURCE_CHAT = message.forward_from_chat.id
        waiting_for_source = False
        await message.reply(f"✅ SOURCE set:\n`{SOURCE_CHAT}`")
        return

    # TARGET
    if waiting_for_target:
        TARGET_CHAT = message.forward_from_chat.id
        waiting_for_target = False
        await message.reply(f"✅ TARGET set:\n`{TARGET_CHAT}`")
        return

    # START MESSAGE ID
    if waiting_for_start:
        START_MSG_ID = message.forward_from_message_id
        waiting_for_start = False
        await message.reply(f"🟢 START point set at message ID: `{START_MSG_ID}`")
        return

    # END MESSAGE ID
    if waiting_for_end:
        END_MSG_ID = message.forward_from_message_id
        waiting_for_end = False
        await message.reply(f"🟠 END point set at message ID: `{END_MSG_ID}`")
        return


@app.on_message(filters.video | filters.document)
async def store_video(client, message):
    if message.chat.id == SOURCE_CHAT:
        video_storage.append(message)


@app.on_message(filters.command("forward"))
async def forward_all(client, message):
    if SOURCE_CHAT is None or TARGET_CHAT is None:
        await message.reply("❌ Set source + target first.")
        return

    await message.reply("⏳ Forwarding ALL videos...")

    sorted_videos = sorted(video_storage, key=lambda x: x.id)

    for msg in sorted_videos:
        try:
            await msg.copy(TARGET_CHAT)
        except:
            pass

    await message.reply("✅ Done.")


@app.on_message(filters.command("forward_range"))
async def forward_range(client, message):
    if None in (SOURCE_CHAT, TARGET_CHAT, START_MSG_ID, END_MSG_ID):
        await message.reply("❌ You must set START and END points first.")
        return

    await message.reply(f"⏳ Forwarding videos from `{START_MSG_ID}` to `{END_MSG_ID}`")

    sorted_videos = sorted(video_storage, key=lambda x: x.id)

    for msg in sorted_videos:
        if START_MSG_ID <= msg.id <= END_MSG_ID:
            try:
                await msg.copy(TARGET_CHAT)
            except:
                pass

    await message.reply("✅ Range forwarding DONE.")


async def preview_range_handler(cb):
    global preview_videos

    if None in (SOURCE_CHAT, TARGET_CHAT, START_MSG_ID, END_MSG_ID):
        await cb.message.reply("❌ Set source, target, start, and end first.")
        return

    sorted_videos = sorted(video_storage, key=lambda x: x.id)
    preview_videos = [msg for msg in sorted_videos if START_MSG_ID <= msg.id <= END_MSG_ID]

    if not preview_videos:
        await cb.message.reply("⚠️ No videos found in the selected range.")
        return

    # Extract numbers from captions (if any)
    video_numbers = []
    for v in preview_videos:
        num = extract_number(v.caption or "")
        if num is None:
            num = "?"
        video_numbers.append(str(num))

    video_list_text = ", ".join(video_numbers)
    total = len(preview_videos)

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Proceed", callback_data="confirm_forward")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_forward")]
    ])

    await cb.message.reply(
        f"👁 Preview of videos from `{START_MSG_ID}` to `{END_MSG_ID}`:\n"
        f"Videos included: {video_list_text}\n"
        f"Total videos: {total}\n\nProceed?",
        reply_markup=buttons
    )


@app.on_callback_query()
async def confirm_cancel_handler(client, cb):
    global preview_videos

    if cb.data == "confirm_forward":
        if not preview_videos:
            await cb.message.reply("⚠️ No videos to forward.")
            return

        await cb.message.reply("⏳ Forwarding selected range now...")

        for msg in preview_videos:
            try:
                await msg.copy(TARGET_CHAT)
            except:
                pass

        preview_videos = []
        await cb.message.reply("✅ Forwarding complete.")

    elif cb.data == "cancel_forward":
        preview_videos = []
        await cb.message.reply("❌ Forwarding cancelled.")

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
