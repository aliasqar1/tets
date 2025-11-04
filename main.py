# -*- coding: utf-8 -*-
import discord
import asyncio
import os
import json
import random
import string
from datetime import datetime, timezone
from datetime import datetime, timedelta, timezone
from discord.ext import commands
from discord import app_commands, Interaction, TextChannel
from discord.ui import View, Button, Modal, TextInput
from dotenv import load_dotenv

# -------------------------
# تنظیمات و بارگذاری توکن
# -------------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "data.json"
STREAM_FILE = "stream.json"
file_lock = asyncio.Lock()
stream_lock = asyncio.Lock()

# -------------------------
# بارگذاری و ذخیره داده‌ها (async-safe)
# -------------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
    
def load_json(file_path):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_invite_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# داده‌ها
data = load_json(DATA_FILE)  # موجودی و پول استریمرها
stream_data = load_json(STREAM_FILE)  # اطلاعات استریمرها

# بررسی استریمر بودن
def is_streamer(member: discord.Member):
    return any(role.name in ("استریمر", "استریمر پلاسما") for role in member.roles)

# ذخیره امن داده‌ها
async def update_data():
    async with file_lock:
        save_json(DATA_FILE, data)

async def update_stream():
    async with stream_lock:
        save_json(STREAM_FILE, stream_data)

# پاک کردن اطلاعات استریمر هنگام خروج
@bot.event
async def on_member_remove(member: discord.Member):
    uid = str(member.id)
    data.get("wallet", {}).pop(uid, None)
    stream_data.pop(uid, None)
    await update_data()
    await update_stream()

# -------------------------
# نمایش پروفایل استریمر
# -------------------------
@bot.tree.command(name="pstream", description="نمایش پروفایل استریمر")
async def pstream(interaction: Interaction, member: discord.Member = None):
    user = member or interaction.user
    if not is_streamer(user):
        await interaction.response.send_message("❌ شما استریمر نیستید.", ephemeral=True)
        return
    uid = str(user.id)
    streamer = stream_data.get(uid)
    if not streamer:
        await interaction.response.send_message("❌ اطلاعات استریمر یافت نشد.", ephemeral=True)
        return

    start_date = datetime.fromisoformat(streamer.get("start_date"))
    days_since = (datetime.now(timezone.utc) - start_date).days

    embed = discord.Embed(title=f"📋 پروفایل استریمر {user.name}", color=discord.Color.purple())
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_image(url=streamer.get("banner_url"))
    embed.add_field(name="تعداد استریم‌ها", value=str(streamer.get("streams_count", 0)))
    embed.add_field(name="تعداد تخلف‌ها", value=str(streamer.get("violations", 0)))
    embed.add_field(name="لینک دعوت", value=streamer.get("invite_link"))
    embed.add_field(name="میزان پول", value=f"{data.get('wallet', {}).get(uid, 0)} سکه")
    embed.add_field(name="روز از استریمر شدن", value=f"{days_since} روز")
    embed.add_field(name="لینک استریم", value=streamer.get("stream_link"))
    embed.add_field(name="تعداد دعوتی شما", value=str(streamer.get("invite_count", 0)))

    await interaction.response.send_message(embed=embed, ephemeral=True)

# -------------------------
# نمایش لینک دعوت استریمر
# -------------------------
@bot.tree.command(name="link", description="نمایش لینک دعوت استریمر")
async def link(interaction: Interaction):
    uid = str(interaction.user.id)
    if not is_streamer(interaction.user):
        await interaction.response.send_message("❌ شما استریمر نیستید.", ephemeral=True)
        return
    streamer = stream_data.get(uid)
    if not streamer:
        await interaction.response.send_message("❌ اطلاعات استریمر یافت نشد.", ephemeral=True)
        return
    await interaction.response.send_message(f"🌐 لینک دعوت شما: {streamer.get('invite_link')}", ephemeral=True)

# -------------------------
# اضافه کردن استریمر توسط ادمین
# -------------------------
class AddStreamerModal(Modal):
    def __init__(self):
        super().__init__(title="ثبت استریمر")
        self.banner = TextInput(label="لینک بنر استریمر")
        self.user = TextInput(label="ID یا @username استریمر")
        self.invite_link = TextInput(label="لینک دعوت استریمر")
        self.stream_link = TextInput(label="لینک استریم شما")
        self.add_item(self.banner)
        self.add_item(self.user)
        self.add_item(self.invite_link)
        self.add_item(self.stream_link)

    async def on_submit(self, interaction: Interaction):
        uid = str(interaction.user.id)
        # برای simplicity، فرض می‌کنیم user فیلد ID را وارد می‌کند
        streamer_id = self.user.value.strip()
        try:
            int(streamer_id)
        except:
            await interaction.response.send_message("❌ ID استریمر معتبر نیست.", ephemeral=True)
            return

        stream_data[streamer_id] = {
            "banner_url": self.banner.value.strip(),
            "invite_link": self.invite_link.value.strip(),
            "stream_link": self.stream_link.value.strip(),
            "streams_count": 0,
            "violations": 0,
            "money": 0,
            "invite_count": 0,
            "start_date": datetime.now(timezone.utc).isoformat()
        }
        await update_stream()
        await interaction.response.send_message(f"✅ استریمر {streamer_id} ثبت شد.", ephemeral=True)

@bot.tree.command(name="addstreamer", description="اضافه کردن استریمر (ادمین فقط)")
async def addstreamer(interaction: Interaction):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message("❌ فقط ادمین‌ها می‌توانند این فرمان را اجرا کنند.", ephemeral=True)
        return
    await interaction.response.send_modal(AddStreamerModal())

# -------------------------
# استارت استریم و افزایش پول و تعداد
# -------------------------
class StartStreamView(View):
    def __init__(self, streamer_id, news_channel: TextChannel):
        super().__init__()
        self.streamer_id = streamer_id
        self.news_channel = news_channel

    @discord.ui.button(label="استارت استریم", style=discord.ButtonStyle.green)
    async def start_cb(self, interaction: Interaction, button: Button):
        streamer = stream_data.get(self.streamer_id)
        if not streamer:
            await interaction.response.send_message("❌ اطلاعات استریمر یافت نشد.", ephemeral=True)
            return
        uid = self.streamer_id
        # افزایش تعداد استریم
        streamer["streams_count"] = streamer.get("streams_count", 0) + 1
        # افزایش پول
        data.setdefault("wallet", {})[uid] = data.get("wallet", {}).get(uid, 0) + 1000
        await update_data()
        await update_stream()
        # ارسال پیام در چنل اخبار
        embed = discord.Embed(title="استارت استریم",
                              description=f"استریمر <@{uid}> شروع به استریم کرده است!",
                              color=discord.Color.green())
        embed.set_image(url=streamer.get("banner_url"))
        embed.add_field(name="لینک استریم", value=streamer.get("stream_link"))
        await self.news_channel.send(embed=embed)
        await interaction.response.send_message("✅ استریم شروع شد و پول اضافه شد.", ephemeral=True)
        self.stop()

data = load_data()

user_wallet = data.get("wallet", {})
user_subscription = data.get("subscription", {})
user_warns = data.get("warns", {})
user_badges = data.get("badges", {})
contests = data.get("contests", {})
server_settings = data.get("server_settings", {})

# runtime objects
active_timers = {}  # user_id -> message
active_contest_tasks = {}  # contest_id -> task


async def save_data_async():
    async with file_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


async def update_data():
    data["wallet"] = user_wallet
    data["subscription"] = user_subscription
    data["warns"] = user_warns
    data["badges"] = user_badges
    data["contests"] = contests
    data["server_settings"] = server_settings
    await save_data_async()


# -------------------------
# کمکی‌ها
# -------------------------
def is_admin_member(member: discord.Member) -> bool:
    """چک می‌کنه آیا عضو رول 'ادمین' یا 'Admin' داره"""
    if not member:
        return False
    for role in member.roles:
        if role.name in ("ادمین", "Admin", "admin"):
            return True
    return False


def generate_unique_badge():
    existing = set(user_badges.values())
    while True:
        number = random.randint(2000, 9999)
        if number not in existing:
            return number


def mask_code(code: str):
    if not code:
        return "******"
    return "*" * len(code)


# -------------------------
# ویرایش اطلاعات استریمر
# -------------------------

class EditStreamerModal(Modal):
    def __init__(self, streamer_id, field_name):
        super().__init__(title=f"ویرایش {field_name}")
        self.streamer_id = streamer_id
        self.field_name = field_name
        self.input_field = TextInput(label=f"مقدار جدید برای {field_name}")
        self.add_item(self.input_field)

    async def on_submit(self, interaction: Interaction):
        streamer = stream_data.get(self.streamer_id)
        if not streamer:
            await interaction.response.send_message("❌ استریمر یافت نشد.", ephemeral=True)
            return

        value = self.input_field.value.strip()
        if self.field_name in ["streams_count", "violations", "invite_count"]:
            try:
                value = int(value)
            except:
                await interaction.response.send_message("❌ مقدار عددی معتبر نیست.", ephemeral=True)
                return
        streamer[self.field_name] = value
        await update_stream()
        await interaction.response.send_message(f"✅ {self.field_name} بروزرسانی شد.", ephemeral=True)





@bot.tree.command(name="vstream", description="لیست استریمرها و ویرایش اطلاعات (ادمین فقط)")
async def vstream(interaction: Interaction):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message("❌ فقط ادمین‌ها می‌توانند این فرمان را اجرا کنند.", ephemeral=True)
        return

    view = View()
    for uid, streamer in stream_data.items():
        user = bot.get_user(int(uid))
        label = user.name if user else uid
        btn = Button(label=label, style=discord.ButtonStyle.blurple)
        async def button_callback(btn_interaction, streamer_id=uid):
            fields = ["banner_url", "invite_link", "stream_link", "streams_count", "violations", "invite_count"]
            field_view = View()
            for field in fields:
                fbtn = Button(label=field, style=discord.ButtonStyle.gray)
                async def fbtn_cb(i, field_name=field, sid=streamer_id):
                    await i.response.send_modal(EditStreamerModal(sid, field_name))
                fbtn.callback = fbtn_cb
                field_view.add_item(fbtn)
            await btn_interaction.response.send_message(f"📋 ویرایش اطلاعات {streamer.get('banner_url')}", view=field_view, ephemeral=True)
        btn.callback = button_callback
        view.add_item(btn)

    await interaction.response.send_message("لیست استریمرها:", view=view, ephemeral=True)

# -------------------------
# تنظیم کانال استریم
# -------------------------

@bot.tree.command(name="sets", description="ارسال پیام استارت استریم با دکمه برای استریمرها")
async def sets(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message("❌ فقط ادمین‌ها می‌توانند این فرمان را اجرا کنند.", ephemeral=True)
        return

    embed = discord.Embed(
        title="استارت استریم",
        description="من استریمر هستم و قوانین را قبول دارم.\nبرای شروع استریم روی دکمه زیر کلیک کنید.",
        color=discord.Color.green()
    )

    view = StartStreamView()
    msg = await channel.send(embed=embed, view=view)

    # ذخیره message_id پیام استارت در stream.json
    guild_id = str(interaction.guild.id)
    if guild_id in stream_data.get("start_stream_messages", {}):
        stream_data["start_stream_messages"][guild_id]["message_id"] = msg.id
    else:
        # اگر قبلا setstart اجرا نشده بود
        stream_data.setdefault("start_stream_messages", {})[guild_id] = {
            "channel_id": None,
            "message_id": msg.id
        }

    await update_stream()
    await interaction.response.send_message(f"✅ پیام استارت استریم ارسال شد در {channel.mention}", ephemeral=True)


# -------------------------
# دکمه استارت استریم
# -------------------------

class StartStreamView(View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view

    @discord.ui.button(label="استارت استریم", style=discord.ButtonStyle.green, custom_id="start_stream_button")
    async def start_stream(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        uid = str(user.id)

        # چک کردن رول استریمر
        if not is_streamer(user):
            await interaction.response.send_message("❌ شما استریمر نیستید.", ephemeral=True)
            return

        # گرفتن اطلاعات استریمر
        streamer = stream_data.get(uid)
        if not streamer:
            await interaction.response.send_message("❌ اطلاعات استریمر یافت نشد.", ephemeral=True)
            return

        # افزایش تعداد استریم و پول
        streamer["streams_count"] = streamer.get("streams_count", 0) + 1
        data.setdefault("wallet", {})[uid] = data.get("wallet", {}).get(uid, 0) + 1000
        await update_data()
        await update_stream()

        # دریافت کانال اخبار استارت از stream.json
        guild_id = str(interaction.guild.id)
        guild_info = stream_data.get("start_stream_messages", {}).get(guild_id)
        if not guild_info or not guild_info.get("channel_id"):
            await interaction.response.send_message("❌ کانال اخبار استارت استریم ثبت نشده.", ephemeral=True)
            return

        news_channel = bot.get_channel(guild_info["channel_id"])
        if not news_channel:
            await interaction.response.send_message("❌ کانال اخبار یافت نشد.", ephemeral=True)
            return

        # ارسال پیام اطلاع‌رسانی در کانال اخبار
        embed = discord.Embed(
            title="استریم شروع شد!",
            description=f"استریمر {user.mention} شروع به استریم کرده است!\nتو هنوز نشستی و بیکاری؟ بیا تو استریم یکم حال کنیم!",
            color=discord.Color.blurple()
        )
        embed.set_image(url=streamer.get("banner_url"))
        embed.add_field(name="لینک استریم", value=streamer.get("stream_link"), inline=False)
        embed.add_field(name="پیام پایانی", value="منتظرت تو استریم هستم!", inline=False)

        view = View()
        enter_button = Button(label="ورود به استریمر", style=discord.ButtonStyle.link, url=streamer.get("stream_link"))
        view.add_item(enter_button)

        await news_channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ استریم شما شروع شد و پیام اطلاع‌رسانی ارسال شد.", ephemeral=True)


# -------------------------
# تنظیم پیام
# -------------------------

# وقتی می‌خوای پیام استارت را بفرستی
@bot.tree.command(name="start_msg", description="ارسال پیام استارت استریم")
async def start_msg(interaction: Interaction):
    gid = str(interaction.guild.id)
    news_channel_id = server_settings.get(gid, {}).get("stream_news_channel_id")
    news_channel = bot.get_channel(news_channel_id)
    if not news_channel:
        await interaction.response.send_message("❌ کانال اخبار استارت استریم تنظیم نشده است.", ephemeral=True)
        return

    embed = discord.Embed(
        title="استارت استریم",
        description="من استریمر هستم و قوانین را قبول دارم.\nبرای استارت استریم روی دکمه زیر کلیک کنید.",
        color=discord.Color.green()
    )
    view = StartStreamView(news_channel)
    await interaction.response.send_message(embed=embed, view=view)


# -------------------------
# تنظیم کانال استارت استریم
# -------------------------

@bot.tree.command(name="setstart", description="تنظیم کانال اخبار استارت استریم (ادمین فقط)")
async def setstart(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message("❌ فقط ادمین‌ها می‌توانند این فرمان را اجرا کنند.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)

    # جایگزین کردن کانال قبلی اگر وجود دارد
    stream_data.setdefault("start_stream_messages", {})
    stream_data["start_stream_messages"][guild_id] = {
        "channel_id": channel.id,
        "message_id": None  # بعداً هنگام ارسال پیام /sets آپدیت می‌شود
    }
    await update_stream()

    await interaction.response.send_message(f"✅ کانال اخبار استارت استریم تنظیم شد: {channel.mention}", ephemeral=True)

# -------------------------
# سیستم ارسال استریم
# -------------------------

async def send_start_stream_message(user: discord.Member):
    uid = str(user.id)
    if not is_streamer(user):
        return
    gid = str(user.guild.id)
    news_channel_id = server_settings.get(gid, {}).get("stream_news_channel_id")
    start_channel_id = server_settings.get(gid, {}).get("stream_start_channel_id")
    news_channel = bot.get_channel(news_channel_id)
    start_channel = bot.get_channel(start_channel_id)
    if not start_channel:
        return

    streamer = stream_data.get(uid)
    view = StartStreamView(uid, news_channel)

    embed = discord.Embed(
        title="استارت استریم",
        description="من استریمر هستم و قوانین را قبول دارم.\nبرای شروع استریم روی دکمه زیر کلیک کنید.",
        color=discord.Color.green()
    )
    embed.set_image(url=streamer.get("banner_url"))
    await start_channel.send(embed=embed, view=view)

# -------------------------
# تخلفات استریمر
# -------------------------

@bot.tree.command(name="ws", description="مدیریت تخلفات استریمر (ادمین فقط)")
@app_commands.describe(member="استریمر", number="تعداد", action="add/rev")
async def ws(interaction: Interaction, member: discord.Member, number: int, action: str):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message("❌ فقط ادمین‌ها می‌توانند این فرمان را اجرا کنند.", ephemeral=True)
        return
    uid = str(member.id)
    if uid not in stream_data:
        await interaction.response.send_message("❌ این کاربر استریمر نیست.", ephemeral=True)
        return

    streamer = stream_data[uid]
    if action.lower() == "add":
        streamer["violations"] = min(3, streamer.get("violations", 0) + number)
    elif action.lower() == "rev":
        streamer["violations"] = max(0, streamer.get("violations", 0) - number)
    else:
        await interaction.response.send_message("❌ action باید add یا rev باشد.", ephemeral=True)
        return

    await update_stream()
    await interaction.response.send_message(f"✅ تعداد تخلفات بروزرسانی شد: {streamer['violations']}", ephemeral=True)

# -------------------------
# دعوت لینک
# -------------------------

class AddStreamerModal(Modal):
    def __init__(self):
        super().__init__(title="ثبت استریمر")
        # ورودی‌ها
        self.user_id_input = TextInput(label="ID استریمر")  # این می‌شود streamer_id
        self.banner = TextInput(label="لینک بنر استریمر")
        self.invite_link = TextInput(label="لینک دعوت استریمر")
        self.stream_link = TextInput(label="لینک استریم شما")
        # اضافه کردن به modal
        self.add_item(self.user_id_input)
        self.add_item(self.banner)
        self.add_item(self.invite_link)
        self.add_item(self.stream_link)

    async def on_submit(self, interaction: Interaction):
        # مقدار streamer_id را از input کاربر می‌گیریم
        streamer_id = self.user_id_input.value.strip()
        if not streamer_id.isdigit():
            await interaction.response.send_message("❌ ID معتبر نیست.", ephemeral=True)
            return

        # ثبت اطلاعات در stream_data
        stream_data[streamer_id] = {
            "banner_url": self.banner.value.strip(),
            "invite_link": self.invite_link.value.strip(),
            "stream_link": self.stream_link.value.strip(),
            "streams_count": 0,
            "violations": 0,
            "money": 0,
            "invite_count": 0,
            "start_date": datetime.now(timezone.utc).isoformat(),
            "invite_code": generate_invite_code()
        }

        await update_stream()
        await interaction.response.send_message(f"✅ استریمر {streamer_id} ثبت شد.", ephemeral=True)


async def save_user_data():
    await update_data()

# -------------------------
# مدیریت ورود کاربران
# -------------------------

@bot.event
async def on_member_join(member: discord.Member):
    uid = str(member.id)

    # 1️⃣ ایجاد بج جدید در صورت نبود
    if uid not in user_badges:
        user_badges[uid] = generate_unique_badge()

    # 2️⃣ بررسی کد دعوت
    # فرض می‌کنیم که member.guild یا member.pending اطلاعات کد دعوت را در اختیار دارد
    # (در حالت واقعی باید از invite tracking استفاده شود)
    try:
        # بررسی کانال دعوت (کد دعوت)
        invites = await member.guild.invites()
        used_invite = None
        for inv in invites:
            if inv.uses > 0:  # دعوت استفاده شده
                used_invite = inv
                break
        if used_invite:
            for sid, streamer in stream_data.items():
                if used_invite.code == streamer.get("invite_code"):
                    # افزایش پول و تعداد دعوتی
                    data.setdefault("wallet", {})[sid] = data.get("wallet", {}).get(sid, 0) + 1000
                    streamer["invite_count"] = streamer.get("invite_count", 0) + 1
                    await update_data()
                    await update_stream()
                    break
    except Exception:
        pass

    await update_data()
    await update_stream()


# -------------------------
# رویدادها
# -------------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (id: {bot.user.id})")
    # بارگذاری Persistent Views برای استارت استریم
    for guild_id, info in stream_data.get("start_stream_messages", {}).items():
        channel = bot.get_channel(info["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(info["message_id"])
                view = StartStreamView()
                bot.add_view(view, message_id=msg.id)  # دکمه‌ها دوباره فعال می‌شوند
            except Exception as e:
                print(f"⚠️ بارگذاری پیام استارت استریم برای سرور {guild_id} ممکن نیست: {e}")


@bot.event
async def on_member_join(member: discord.Member):
    uid = str(member.id)
    if uid not in user_badges:
        user_badges[uid] = generate_unique_badge()
        await update_data()
    # optional: try to change nickname
    try:
        await member.edit(nick=f"{user_badges[uid]} | {member.name}")
    except Exception:
        pass


@bot.event
async def on_member_remove(member: discord.Member):
    uid = str(member.id)
    user_wallet.pop(uid, None)
    user_subscription.pop(uid, None)
    user_warns.pop(uid, None)
    user_badges.pop(uid, None)
    await update_data()
    print(f"🧹 Removed data for {member} (left server)")


# -------------------------
# حلقه پاداش ویس (هر 60 ثانیه) — نگه میداره رفتار قبلی
# -------------------------
async def voice_check_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            for g in bot.guilds:
                for vc in g.voice_channels:
                    for m in vc.members:
                        if not m.bot:
                            uid = str(m.id)
                            user_wallet[uid] = user_wallet.get(uid, 0) + 2
            await update_data()
        except Exception as e:
            print("⚠️ voice_check_loop error:", e)
        await asyncio.sleep(60)


# -------------------------
# پروفایل و پول
# -------------------------
@bot.tree.command(name="pol", description="نمایش موجودی سکه شما")
async def pol(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    bal = user_wallet.get(uid, 0)
    await interaction.response.send_message(f"💰 موجودی شما: {bal} سکه",
                                            ephemeral=True)


@bot.tree.command(name="prof", description="نمایش پروفایل شما")
async def prof(interaction: discord.Interaction):
    user = interaction.user
    uid = str(user.id)
    badge = user_badges.get(uid, "ثبت نشده")
    coins = user_wallet.get(uid, 0)
    warns = user_warns.get(uid, 0)

    sub_status = "❌ ندارد"
    days_left = "—"
    if uid in user_subscription:
        start = datetime.fromisoformat(user_subscription[uid])
        end = start + timedelta(days=30)
        now = datetime.now(timezone.utc)
        remaining = end - now
        if remaining.total_seconds() > 0:
            sub_status = "✅ فعال"
            days_left = f"{remaining.days} روز"
        else:
            sub_status = "⛔ منقضی شده"

    joined = user.joined_at
    joined_text = f"{(datetime.now(timezone.utc) - joined).days} روز پیش" if joined else "نامشخص"

    embed = discord.Embed(title=f"📋 پروفایل {user.name}",
                          color=discord.Color.blue())
    embed.add_field(name="🏷 بج نامبر", value=str(badge), inline=True)
    embed.add_field(name="💰 موجودی", value=f"{coins} سکه", inline=True)
    embed.add_field(name="🎫 اشتراک", value=sub_status, inline=True)
    embed.add_field(name="⏳ باقی‌مانده اشتراک", value=days_left, inline=True)
    embed.add_field(name="⚠️ هشدارها", value=str(warns), inline=True)
    embed.add_field(name="📅 تاریخ عضویت", value=joined_text, inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text="اطلاعات پروفایل شما")

    await interaction.response.send_message(embed=embed, ephemeral=True)


# -------------------------
# فروشگاه ساده (/shop) — همون‌طور که بود
# -------------------------
@bot.tree.command(name="shop", description="خرید اشتراک شکرسیتی")
async def shop(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛍 فروشگاه شکرسیتی",
        description=
        "🎫 اشتراک 1 ماه شکرسیتی\n💰 قیمت: 75000 سکه\n📦 رول دریافتی: `sub (1)`\n⏳ اعتبار: 30 روز",
        color=discord.Color.gold())
    embed.set_footer(text="برای خرید روی دکمه زیر کلیک کنید")

    view = View()
    button = Button(label="خرید اشتراک", style=discord.ButtonStyle.green)

    async def button_callback(btn_interaction: discord.Interaction):
        uid = str(btn_interaction.user.id)
        balance = user_wallet.get(uid, 0)
        if balance < 75000:
            await btn_interaction.response.send_message("❌ موجودی کافی نیست!",
                                                        ephemeral=True)
            return
        user_wallet[uid] = balance - 75000
        user_subscription[uid] = datetime.now(timezone.utc).isoformat()
        await update_data()
        role = discord.utils.get(btn_interaction.guild.roles, name="sub (1)")
        if role:
            try:
                await btn_interaction.user.add_roles(role)
            except Exception:
                pass
            await btn_interaction.response.send_message(
                "✅ اشتراک خریداری شد! رول `sub (1)` به شما داده شد.",
                ephemeral=True)
            bot.loop.create_task(
                schedule_role_removal(btn_interaction.user, role, days=30))
        else:
            await btn_interaction.response.send_message(
                "❌ رول `sub (1)` پیدا نشد. لطفاً رول را بسازید.",
                ephemeral=True)

    button.callback = button_callback
    view.add_item(button)

    await interaction.response.send_message(embed=embed,
                                            view=view,
                                            ephemeral=True)


async def schedule_role_removal(member: discord.Member,
                                role: discord.Role,
                                days: int = 30):
    await asyncio.sleep(days * 24 * 60 * 60)
    try:
        await member.remove_roles(role)
        await member.send(
            "⏳ اشتراک شما به پایان رسید و رول `sub (1)` از شما گرفته شد.")
    except Exception:
        pass


# -------------------------
# تایمر 20 روزه: تابع اجرایی قابل فراخوانی
# -------------------------
async def start_timer_for(target_member: discord.Member,
                          channel: discord.TextChannel):
    """شروع/ریست تایمر 20 روزه برای target_member و ارسال/آپدیت پیام در channel"""
    uid = str(target_member.id)
    start_time = datetime.now(timezone.utc)
    user_subscription[uid] = start_time.isoformat()
    await update_data()

    duration = timedelta(days=20)
    end_time = start_time + duration
    warning_sent = False

    try:
        msg = await channel.send(
            f"⏳ تایمر {target_member.mention} در حال شروع است...")
        active_timers[uid] = msg
    except Exception:
        return

    while True:
        now = datetime.now(timezone.utc)
        remaining = end_time - now

        if remaining.total_seconds() <= 0:
            try:
                await msg.edit(
                    content=
                    f"⏳ تایمر {target_member.mention}: زمان به پایان رسید!")
            except Exception:
                pass
            active_timers.pop(uid, None)
            break

        days = remaining.days
        hours, rem = divmod(remaining.seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        progress = 20 - days
        if progress < 0:
            progress = 0
        if progress > 20:
            progress = 20
        bar = "🟩" * progress + "🟥" * (20 - progress)

        content = (
            f"⏳ باقی‌مانده برای {target_member.mention}: {days} روز، {hours:02}:{minutes:02}:{seconds:02}\n"
            f"{bar} ({progress}/20 روز)")
        try:
            await msg.edit(content=content)
        except Exception:
            pass

        if days == 3 and not warning_sent:
            try:
                await channel.send(
                    f"⚠️ فقط ۳ روز باقی مانده برای {target_member.mention}!")
            except Exception:
                pass
            warning_sent = True

        await asyncio.sleep(10)  # update every 5 seconds


# /timeout command (admin-only)
@bot.tree.command(name="timeout", description="شروع تایمر 20 روزه (admin فقط)")
async def timeout_cmd(interaction: discord.Interaction,
                      member: discord.Member = None):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message(
            "❌ فقط ادمین‌ها می‌تونن این فرمان رو اجرا کنن.", ephemeral=True)
        return
    target = member or interaction.user
    await interaction.response.send_message(
        f"⏳ تایمر برای {target.mention} شروع شد.", ephemeral=True)
    bot.loop.create_task(start_timer_for(target, interaction.channel))


# /rtime command (admin-only) - ریست تایمر 20 روزه برای یک کاربر
@bot.tree.command(name="rtime", description="ریست تایمر 20 روزه (admin فقط)")
async def rtime_cmd(interaction: discord.Interaction,
                    member: discord.Member = None):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message(
            "❌ فقط ادمین‌ها می‌تونن این فرمان رو اجرا کنن.", ephemeral=True)
        return
    target = member or interaction.user
    uid = str(target.id)
    # cancel existing timer message if present
    msg = active_timers.pop(uid, None)
    if msg:
        try:
            await msg.edit(
                content=
                f"⏳ تایمر برای {target.mention} ریست شد توسط {interaction.user.mention}"
            )
        except Exception:
            pass
    await interaction.response.send_message(
        f"🔁 تایمر {target.mention} ریست شد و از نو شروع می‌شود.",
        ephemeral=True)
    bot.loop.create_task(start_timer_for(target, interaction.channel))


# -------------------------
# دستورات پرداخت (/pay)
# -------------------------
@bot.tree.command(name="pay",
                  description="افزودن یا کم کردن پول از کاربر (admin فقط)")
@app_commands.describe(member="کاربر هدف",
                       amount="مقدار (عدد صحیح)",
                       action="add یا rev")
async def pay_cmd(interaction: discord.Interaction, member: discord.Member,
                  amount: int, action: str):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message(
            "❌ فقط ادمین‌ها می‌تونن این فرمان رو اجرا کنن.", ephemeral=True)
        return
    uid = str(member.id)
    user_wallet[uid] = user_wallet.get(uid, 0)
    if action.lower() == "add":
        user_wallet[uid] += amount
        await update_data()
        await interaction.response.send_message(
            f"✅ {amount} سکه به {member.mention} اضافه شد.", ephemeral=True)
    elif action.lower() == "rev":
        user_wallet[uid] = max(0, user_wallet[uid] - amount)
        await update_data()
        await interaction.response.send_message(
            f"✅ {amount} سکه از {member.mention} کسر شد.", ephemeral=True)
    else:
        await interaction.response.send_message(
            "❌ پارامتر action باید `add` یا `rev` باشد.", ephemeral=True)


# -------------------------
# وارن‌ها: /w (add/rev), /wr (reset), /wv (view)
# -------------------------
@bot.tree.command(name="w",
                  description="افزودن یا حذف وارن به کاربر (admin فقط)")
@app_commands.describe(member="کاربر هدف",
                       count="تعداد (مثال: 1)",
                       action="add یا rev")
async def w_cmd(interaction: discord.Interaction, member: discord.Member,
                count: int, action: str):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message(
            "❌ فقط ادمین‌ها می‌تونن این فرمان رو اجرا کنن.", ephemeral=True)
        return
    uid = str(member.id)
    user_warns[uid] = user_warns.get(uid, 0)
    if action.lower() == "add":
        user_warns[uid] += count
        await update_data()
        await interaction.response.send_message(
            f"⚠️ به {member.mention}، {count} وارن افزوده شد. (تعداد فعلی: {user_warns[uid]})",
            ephemeral=True)
    elif action.lower() == "rev":
        user_warns[uid] = max(0, user_warns[uid] - count)
        await update_data()
        # اگر زیر 3 شد، برداشتن تایم‌اوت
        if user_warns[uid] < 3:
            try:
                await member.edit(communication_disabled_until=None)
            except Exception:
                pass
        await interaction.response.send_message(
            f"✅ {count} وارن از {member.mention} حذف شد. (تعداد فعلی: {user_warns[uid]})",
            ephemeral=True)
    else:
        await interaction.response.send_message(
            "❌ پارامتر action باید `add` یا `rev` باشد.", ephemeral=True)

    # اعمال خودکار (بعد از update_data)
    # اگر وارن برابر یا بیشتر از 3 => 1 هفته mute (timeout)
    if user_warns.get(uid, 0) >= 3 and user_warns.get(uid, 0) < 5:
        # اگر فعلاً تایم‌اوت اعمال نشده باشه، اعمال کن
        try:
            # timeout until now + 7 days
            until = datetime.now(timezone.utc) + timedelta(days=7)
            await member.edit(communication_disabled_until=until)
            # پیام اطلاع‌رسانی در کانالی که فرمان اجرا شد
            try:
                await interaction.channel.send(
                    f"🔇 {member.mention} به‌خاطر رسیدن به {user_warns[uid]} وارن برای ۱ هفته سکوت شد."
                )
            except Exception:
                pass
        except Exception:
            pass
    # اگر وارن >=5 => ban دائم
    if user_warns.get(uid, 0) >= 5:
        try:
            await member.ban(reason="دریافت 5 وارن - بن دائم",
                             delete_message_days=0)
            try:
                await interaction.channel.send(
                    f"🔨 {member.mention} به دلیل رسیدن به 5 وارن بن شد (دائم)."
                )
            except Exception:
                pass
        except Exception:
            pass


@bot.tree.command(name="wr",
                  description="پاک کردن تمام وارن‌های کاربر (admin فقط)")
@app_commands.describe(member="کاربر هدف")
async def wr_cmd(interaction: discord.Interaction, member: discord.Member):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message(
            "❌ فقط ادمین‌ها می‌تونن این فرمان رو اجرا کنن.", ephemeral=True)
        return
    uid = str(member.id)
    user_warns[uid] = 0
    await update_data()
    # برداشتن تایم‌اوت اگر وجود داشت
    try:
        await member.edit(communication_disabled_until=None)
    except Exception:
        pass
    await interaction.response.send_message(
        f"✅ تمام وارن‌های {member.mention} پاک شد.", ephemeral=True)


@bot.tree.command(name="wv",
                  description="نمایش تعداد وارن‌های کاربر (admin فقط)")
@app_commands.describe(member="کاربر مورد نظر")
async def wv_cmd(interaction: discord.Interaction, member: discord.Member):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message(
            "❌ فقط ادمین‌ها می‌تونن این فرمان رو اجرا کنن.", ephemeral=True)
        return
    uid = str(member.id)
    count = user_warns.get(uid, 0)
    await interaction.response.send_message(
        f"⚠️ {member.mention} دارای {count} وارن است.", ephemeral=True)


# -------------------------
# سیستم مسابقات (plus, setgame, setout, participation)
# -------------------------
# setgame / setout
@bot.tree.command(name="setgame",
                  description="تنظیم کانال ارسال مسابقه (admin فقط)")
@app_commands.describe(channel="کانال مسابقات")
async def setgame_cmd(interaction: discord.Interaction,
                      channel: discord.TextChannel):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message(
            "❌ فقط ادمین‌ها می‌تونن این فرمان رو اجرا کنند.", ephemeral=True)
        return
    gid = str(interaction.guild_id)
    server_settings.setdefault(gid, {})["game_channel_id"] = channel.id
    await update_data()
    await interaction.response.send_message(
        f"✅ کانال مسابقات تنظیم شد: {channel.mention}")


@bot.tree.command(name="setout",
                  description="تنظیم کانال نتایج مسابقه (admin فقط)")
@app_commands.describe(channel="کانال نتایج")
async def setout_cmd(interaction: discord.Interaction,
                     channel: discord.TextChannel):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message(
            "❌ فقط ادمین‌ها می‌تونن این فرمان رو اجرا کنند.", ephemeral=True)
        return
    gid = str(interaction.guild_id)
    server_settings.setdefault(gid, {})["result_channel_id"] = channel.id
    await update_data()
    await interaction.response.send_message(
        f"✅ کانال نتایج تنظیم شد: {channel.mention}")


# Participation modal
class ParticipationModal(Modal):

    def __init__(self, contest_id: str):
        super().__init__(title="شرکت در مسابقه")
        self.contest_id = contest_id
        self.code = TextInput(label="کد مخفی را وارد کنید",
                              placeholder="مثال: 12345")
        self.add_item(self.code)

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        contest = contests.get(self.contest_id)
        if not contest:
            await interaction.response.send_message(
                "❌ این مسابقه دیگر معتبر نیست.", ephemeral=True)
            return
        # ثبت ارسال
        submissions = contest.setdefault("submissions", [])
        submissions.append({
            "user_id": uid,
            "code": self.code.value.strip(),
            "time": datetime.now(timezone.utc).isoformat()
        })
        await update_data()
        # پاسخ مختصر برای شرکت‌کننده
        if self.code.value.strip() == contest.get("secret_code"):
            # ثبت در winners (اگر قبلاً ثبت نشده)
            winners = contest.setdefault("winners", [])
            if not any(w.get("user_id") == uid for w in winners):
                winners.append({
                    "user_id": uid,
                    "time": datetime.now(timezone.utc).isoformat()
                })
                await update_data()
            await interaction.response.send_message(
                "✅ ممنون از شرکت شما! کد شما درست ثبت شد.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ ممنون از شرکت شما. کد وارد شده درست نیست.", ephemeral=True)


class ParticipateView(View):

    def __init__(self, contest_id: str):
        super().__init__(timeout=None)
        self.contest_id = contest_id

    @discord.ui.button(label="شرکت در مسابقه",
                       style=discord.ButtonStyle.blurple)
    async def participate(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        modal = ParticipationModal(self.contest_id)
        await interaction.response.send_modal(modal)


# /plus flow
@bot.tree.command(name="plus", description="ایجاد مسابقه جدید (admin فقط)")
async def plus_cmd(interaction: discord.Interaction):
    if not is_admin_member(interaction.user):
        await interaction.response.send_message(
            "❌ فقط ادمین‌ها می‌تونن مسابقه بسازن.", ephemeral=True)
        return

    await interaction.response.send_message(
        "📸 لطفاً عکس مسابقه را ارسال کنید (در همان کانال).", ephemeral=True)

    def check_image(m: discord.Message):
        return m.author.id == interaction.user.id and m.attachments and m.channel == interaction.channel

    try:
        image_msg = await bot.wait_for('message',
                                       check=check_image,
                                       timeout=300)
    except asyncio.TimeoutError:
        await interaction.followup.send("❌ زمان ارسال عکس به پایان رسید.",
                                        ephemeral=True)
        return

    await interaction.followup.send("🔗 لطفاً لینک مستقیم تصویر را ارسال کنید.",
                                    ephemeral=True)

    def check_text(m: discord.Message):
        return m.author.id == interaction.user.id and m.channel == interaction.channel

    try:
        link_msg = await bot.wait_for('message', check=check_text, timeout=300)
        image_link = link_msg.content.strip()
    except asyncio.TimeoutError:
        await interaction.followup.send("❌ زمان ارسال لینک به پایان رسید.",
                                        ephemeral=True)
        return

    await interaction.followup.send(
        "🔒 لطفاً کد مخفی مسابقه را ارسال کنید (این کد برای کاربران نمایش داده نخواهد شد).",
        ephemeral=True)
    try:
        secret_msg = await bot.wait_for('message',
                                        check=check_text,
                                        timeout=300)
        secret_code = secret_msg.content.strip()
    except asyncio.TimeoutError:
        await interaction.followup.send("❌ زمان ارسال کد مخفی به پایان رسید.",
                                        ephemeral=True)
        return

    await interaction.followup.send(
        "💰 لطفاً میزان پول جایزه را وارد کنید (عدد).", ephemeral=True)
    try:
        prize_msg = await bot.wait_for('message',
                                       check=check_text,
                                       timeout=300)
        prize_amount = int(prize_msg.content.strip())
    except asyncio.TimeoutError:
        await interaction.followup.send("❌ زمان ارسال مبلغ به پایان رسید.",
                                        ephemeral=True)
        return
    except ValueError:
        await interaction.followup.send("❌ مقدار غیرمعتبر. عملیات کنسل شد.",
                                        ephemeral=True)
        return

    # انتخاب ثانیه یا روز
    duration_holder = {"type": None, "value": None}
    btn_seconds = Button(label="ثانیه", style=discord.ButtonStyle.gray)
    btn_days = Button(label="روز", style=discord.ButtonStyle.gray)
    pick_view = View()

    async def seconds_cb(btn_interaction: discord.Interaction):
        if btn_interaction.user.id != interaction.user.id:
            await btn_interaction.response.send_message(
                "این دکمه برای سازنده مسابقه است.", ephemeral=True)
            return
        await btn_interaction.response.send_message(
            "⏱ لطفاً تعداد ثانیه را ارسال کنید (مثال: 120).", ephemeral=True)
        try:
            msg = await bot.wait_for('message', check=check_text, timeout=300)
            duration_holder['type'] = 'seconds'
            duration_holder['value'] = int(msg.content.strip())
            await btn_interaction.followup.send("✅ مقدار ثانیه ثبت شد.",
                                                ephemeral=True)
        except asyncio.TimeoutError:
            await btn_interaction.followup.send(
                "❌ زمان ارسال مقدار به پایان رسید.", ephemeral=True)
        except ValueError:
            await btn_interaction.followup.send("❌ مقدار نامعتبر.",
                                                ephemeral=True)

    async def days_cb(btn_interaction: discord.Interaction):
        if btn_interaction.user.id != interaction.user.id:
            await btn_interaction.response.send_message(
                "این دکمه برای سازنده مسابقه است.", ephemeral=True)
            return
        await btn_interaction.response.send_message(
            "📅 لطفاً تعداد روز را ارسال کنید (مثال: 2).", ephemeral=True)
        try:
            msg = await bot.wait_for('message', check=check_text, timeout=300)
            duration_holder['type'] = 'days'
            duration_holder['value'] = int(msg.content.strip())
            await btn_interaction.followup.send("✅ مقدار روز ثبت شد.",
                                                ephemeral=True)
        except asyncio.TimeoutError:
            await btn_interaction.followup.send(
                "❌ زمان ارسال مقدار به پایان رسید.", ephemeral=True)
        except ValueError:
            await btn_interaction.followup.send("❌ مقدار نامعتبر.",
                                                ephemeral=True)

    btn_seconds.callback = seconds_cb
    btn_days.callback = days_cb
    pick_view.add_item(btn_seconds)
    pick_view.add_item(btn_days)

    await interaction.followup.send("⏳ لطفاً نوع بازه زمانی را انتخاب کنید:",
                                    view=pick_view,
                                    ephemeral=True)

    # منتظر انتخاب نوع (تا 300 ثانیه)
    waited = 0
    while waited < 300 and duration_holder['type'] is None:
        await asyncio.sleep(1)
        waited += 1

    if duration_holder['type'] is None:
        await interaction.followup.send(
            "❌ زمان انتخاب نوع بازه به پایان رسید.", ephemeral=True)
        return

    # ساخت contest id یکتا
    contest_id = str(random.randint(1000, 9999))
    while contest_id in contests:
        contest_id = str(random.randint(1000, 9999))

    contest = {
        "contest_id":
        contest_id,
        "creator_id":
        str(interaction.user.id),
        "image_url":
        image_link,
        "attachment_url":
        image_msg.attachments[0].url if image_msg.attachments else None,
        "secret_code":
        secret_code,
        "prize":
        prize_amount,
        "duration_type":
        duration_holder['type'],
        "duration_value":
        duration_holder['value'],
        "created_at":
        datetime.now(timezone.utc).isoformat(),
        "submissions": [],
        "winners": []
    }

    # پیش‌نمایش برای ادمین
    preview = discord.Embed(title=f"📣 پیش‌نمایش مسابقه #{contest_id}",
                            color=discord.Color.green())
    preview.add_field(name="تعداد شرکت‌کنندگان", value="0", inline=True)
    preview.add_field(name="کد مخفی",
                      value=mask_code(secret_code),
                      inline=True)
    if contest['duration_type'] == 'days':
        preview.add_field(name="مدت زمان",
                          value=f"{contest['duration_value']} روز",
                          inline=True)
    else:
        preview.add_field(name="مدت زمان",
                          value=f"{contest['duration_value']} ثانیه",
                          inline=True)
    preview.add_field(name="لینک تصویر", value=image_link, inline=False)
    preview.add_field(name="جایزه (نفر اول)",
                      value=f"{prize_amount}",
                      inline=True)
    preview.add_field(name="جایزه (نفر دوم)",
                      value=f"{prize_amount//2}",
                      inline=True)
    if contest['image_url']:
        preview.set_image(url=contest['image_url'])

    pv_view = View()
    register_btn = Button(label="ثبت مسابقه", style=discord.ButtonStyle.green)
    cancel_btn = Button(label="انصراف", style=discord.ButtonStyle.red)

    async def register_cb(btn_interaction: discord.Interaction):
        if btn_interaction.user.id != interaction.user.id:
            await btn_interaction.response.send_message(
                "این دکمه برای سازنده مسابقه است.", ephemeral=True)
            return
        contests[contest_id] = contest
        await update_data()

        gid = str(interaction.guild_id)
        game_channel_id = server_settings.get(gid, {}).get("game_channel_id")
        if not game_channel_id:
            await btn_interaction.response.send_message(
                "❌ کانال مسابقات تنظیم نشده است. از /setgame استفاده کنید.",
                ephemeral=True)
            return
        game_channel = bot.get_channel(game_channel_id)
        if not game_channel:
            await btn_interaction.response.send_message(
                "❌ کانال مسابقات پیدا نشد.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🏆 مسابقه شماره {contest_id}",
            description="کد مخفی: ****** (برای شرکت کد را وارد کنید)",
            color=discord.Color.blurple())
        embed.add_field(name="تعداد شرکت‌کنندگان", value="0", inline=True)
        if contest['duration_type'] == 'days':
            embed.add_field(name="مدت زمان",
                            value=f"{contest['duration_value']} روز",
                            inline=True)
        else:
            embed.add_field(name="مدت زمان",
                            value=f"{contest['duration_value']} ثانیه",
                            inline=True)
        embed.add_field(name="لینک تصویر",
                        value=contest['image_url'],
                        inline=False)
        embed.add_field(name="جایزه (نفر اول)",
                        value=f"{contest['prize']}",
                        inline=True)
        embed.add_field(name="جایزه (نفر دوم)",
                        value=f"{contest['prize']//2}",
                        inline=True)
        if contest['image_url']:
            embed.set_image(url=contest['image_url'])
        try:
            msg = await game_channel.send(embed=embed,
                                          view=ParticipateView(contest_id))
            contest['message_id'] = msg.id
            contest['channel_id'] = game_channel.id
            await update_data()
            # start manage lifecycle task
            task = bot.loop.create_task(manage_contest_lifecycle(contest_id))
            active_contest_tasks[contest_id] = task
            await btn_interaction.response.send_message(
                "✅ مسابقه ثبت و ارسال شد.", ephemeral=True)
        except Exception as e:
            await btn_interaction.response.send_message(
                "❌ ارسال مسابقه موفق نبود: " + str(e), ephemeral=True)

    async def cancel_cb(btn_interaction: discord.Interaction):
        if btn_interaction.user.id != interaction.user.id:
            await btn_interaction.response.send_message(
                "این دکمه برای سازنده مسابقه است.", ephemeral=True)
            return
        await btn_interaction.response.send_message("❌ عملیات کنسل شد.",
                                                    ephemeral=True)

    register_btn.callback = register_cb
    cancel_btn.callback = cancel_cb
    pv_view.add_item(register_btn)
    pv_view.add_item(cancel_btn)

    await interaction.followup.send(embed=preview,
                                    view=pv_view,
                                    ephemeral=True)


# lifecycle manager
async def manage_contest_lifecycle(contest_id: str):
    contest = contests.get(contest_id)
    if not contest:
        return
    channel = bot.get_channel(contest.get("channel_id"))
    message = None
    try:
        if channel and contest.get("message_id"):
            message = await channel.fetch_message(contest["message_id"])
    except Exception:
        message = None

    created = datetime.fromisoformat(contest["created_at"])
    if contest["duration_type"] == "days":
        end_time = created + timedelta(days=contest["duration_value"])
    else:
        end_time = created + timedelta(seconds=contest["duration_value"])

    while True:
        now = datetime.now(timezone.utc)
        if now >= end_time:
            break
        # update participant count every 10 seconds
        submissions = contest.get("submissions", [])
        count = len(submissions)
        if message:
            try:
                embed = message.embeds[0]
                new_embed = embed.copy()
                # try find the participant field
                found = False
                for i, f in enumerate(new_embed.fields):
                    if "تعداد شرکت" in f.name:
                        new_embed.set_field_at(i,
                                               name=f.name,
                                               value=str(count),
                                               inline=f.inline)
                        found = True
                        break
                if not found:
                    new_embed.add_field(name="تعداد شرکت‌کنندگان",
                                        value=str(count),
                                        inline=True)
                await message.edit(embed=new_embed)
            except Exception:
                pass
        await asyncio.sleep(10)

    # contest ended -> determine winners
    submissions = contest.get("submissions", [])
    correct = [
        s for s in submissions if s.get("code") == contest.get("secret_code")
    ]
    first = correct[0] if len(correct) >= 1 else None
    second = correct[1] if len(correct) >= 2 else None

    # pay out
    if first:
        uid = first["user_id"]
        user_wallet[uid] = user_wallet.get(uid, 0) + contest["prize"]
    if second:
        uid2 = second["user_id"]
        user_wallet[uid2] = user_wallet.get(uid2, 0) + (contest["prize"] // 2)
    await update_data()

    # send result
    gid = str(channel.guild.id) if channel and channel.guild else None
    result_channel_id = server_settings.get(gid, {}).get("result_channel_id")
    result_channel = bot.get_channel(
        result_channel_id) if result_channel_id else channel

    res_embed = discord.Embed(title="🏁 نتیجه مسابقه",
                              color=discord.Color.gold())
    res_embed.add_field(name="کد مسابقه", value=f"#{contest_id}", inline=False)
    res_embed.add_field(name="کد مخفی مسابقه",
                        value=contest.get("secret_code"),
                        inline=False)
    res_embed.add_field(name="تعداد شرکت کنندگان",
                        value=str(len(submissions)),
                        inline=False)

    winners_text = ""
    if first:
        u = bot.get_user(int(first["user_id"]))
        winners_text += f"نفر اول: {u.mention if u else first['user_id']}\n"
    else:
        winners_text += "نفر اول: —\n"
    if second:
        u2 = bot.get_user(int(second["user_id"]))
        winners_text += f"نفر دوم: {u2.mention if u2 else second['user_id']}\n"
    else:
        winners_text += "نفر دوم: —\n"

    res_embed.add_field(name="برندگان", value=winners_text, inline=False)
    res_embed.add_field(
        name="میزان جایزه",
        value=f"نفر اول: {contest['prize']}\nنفر دوم: {contest['prize']//2}",
        inline=False)
    res_embed.set_footer(text="ممنون از شرکت در مسابقه")

    try:
        if result_channel:
            await result_channel.send(embed=res_embed)
        else:
            # fallback
            if channel:
                await channel.send(embed=res_embed)
    except Exception:
        pass

    # mark message as finished
    if message:
        try:
            embed = message.embeds[0]
            new_embed = embed.copy()
            new_embed.add_field(name="وضعیت",
                                value="پایان یافته",
                                inline=False)
            await message.edit(embed=new_embed, view=None)
        except Exception:
            pass

    active_contest_tasks.pop(contest_id, None)


# -------------------------
# بخش جدید
# -------------------------


# پاداش هر پیام: 1 سکه
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    uid = str(message.author.id)
    user_wallet[uid] = user_wallet.get(uid, 0) + 1
    await update_data()

    await bot.process_commands(message)  # اجازه اجرای دستورات دیگر


# بررسی و پاداش ری‌اکشن روی عکس/ویدیو
async def reward_reaction(message: discord.Message):
    if not message.attachments:
        return

    # فقط تصاویر یا ویدیوها
    if not any(
            a.content_type and a.content_type.startswith(("image/", "video/"))
            for a in message.attachments):
        return

    uid = str(message.author.id)
    # تعداد کل ری‌اکشن روی پیام
    total_reacts = sum(r.count for r in message.reactions)
    # تعداد دفعاتی که قبلاً پول داده شده
    last_rewarded = getattr(message, "rewarded_reacts", 0)
    # هر 10 ری‌اکشن = 1000 سکه
    new_rewards = (total_reacts // 10) - last_rewarded

    if new_rewards > 0:
        user_wallet[uid] = user_wallet.get(uid, 0) + (1000 * new_rewards)
        setattr(message, "rewarded_reacts", last_rewarded + new_rewards)
        await update_data()


# رویداد اضافه شدن ری‌اکشن
@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    if user.bot:
        return
    await reward_reaction(reaction.message)


# رویداد حذف ری‌اکشن
@bot.event
async def on_reaction_remove(reaction: discord.Reaction, user: discord.User):
    if user.bot:
        return
    await reward_reaction(reaction.message)


# -------------------------
# 2بخش جدید
# -------------------------


async def auto_ban_after_warn(uid: str, member: discord.Member):
    """
    بررسی تعداد وارن کاربر و بن خودکار بعد از رسیدن به 3 وارن.
    uid: str شناسه کاربر
    member: discord.Member شیء کاربر
    """
    warns_count = user_warns.get(uid, 0)

    if warns_count >= 3:
        try:
            await member.ban(reason="رسیدن به ۳ وارن - بن خودکار",
                             delete_message_days=0)
            try:
                # اطلاع‌رسانی مستقیم به کاربر
                await member.send(
                    "❌ شما به دلیل رسیدن به ۳ وارن از سرور بن شدید.")
            except Exception:
                pass
            print(f"🔨 کاربر {member} به دلیل ۳ وارن بن شد.")
        except Exception as e:
            print(f"⚠️ خطا در بن کردن {member}: {e}")

# -------------------------
# اجرای بات
# -------------------------
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except Exception as e:
        print("🔴 Bot failed to start:", e)
