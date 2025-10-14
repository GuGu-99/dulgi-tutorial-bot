# -*- coding: utf-8 -*-
# dulgi-tutorial-bot : Step1 UX 업그레이드 버전 (트리거 감지 + 축하 메시지)

import sys, types
sys.modules["audioop"] = types.ModuleType("audioop")  # Python 3.13 대응

import asyncio, os, discord
from discord.ext import commands
from flask import Flask
from threading import Thread

# --- 기본 설정 ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 설정값 ---
FORUM_CHANNEL_ID   = 1423360385225851011
TARGET_ROLE_ID     = 1426578319410728980
LOG_CHANNEL_ID     = 1426600994522112100
TUTORIAL_CATEGORY_ID = None
DELETE_DELAY       = 300  # 5분 후 삭제

CHANNEL_CHECKIN_ID = 1423359791287242782  # 출근체크 채널 ID
CHANNEL_DAILY_ID   = 1423170386811682908  # 일일-그림보고
CHANNEL_WEEKLY_ID  = 1423360385225851011  # 주간-그림보고

user_tutorial_progress = {}
sent_users = set()
channel_owner = {}

# --- Render KeepAlive ---
app = Flask(__name__)
@app.route("/")
def home(): return "dulgi-tutorial-bot running"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
def keep_alive(): Thread(target=run_flask, daemon=True).start()

# --- 튜토리얼 단계 (UX 개선된 Step1) ---
TUTORIAL_STEPS = {
    1: {
        "title": "🏢 Step 1 : 출근하기",
        "desc": (
            "**!출근 명령어를 아래 채널에서 입력해보세요!**\n\n"
            "👉👉👉 이동: <#1423359791287242782>\n\n"
            "출근은 하루의 시작이자, 꿈을 향한 첫 걸음이에요 🌅"
        )
    },
    2: {
        "title": "🎨 Step 2 : 일일-그림보고",
        "desc": (
            "‘일일-그림보고’ 채널에 오늘의 그림을 올려보세요 ✏️\n"
            "👉 이동: <#1423170386811682908>"
        )
    },
    3: {
        "title": "📊 Step 3 : 보고서 보기",
        "desc": "`!보고서` 로 이번 주 점수를 확인해요 🌱"
    },
    4: {
        "title": "🗂️ Step 4 : 주간-그림보고",
        "desc": (
            "‘주간-그림보고’ 채널에서 본인 닉네임 포럼을 만들어보세요!\n"
            "예: [둘기] 10월 2주차 피드백 ✨/💧 3가지씩 적기\n"
            "👉 이동: <#1423360385225851011>"
        )
    }
}

# --- 포럼 생성 ---
async def create_weekly_forum(member: discord.Member):
    try:
        forum = bot.get_channel(FORUM_CHANNEL_ID)
        if isinstance(forum, discord.ForumChannel):
            img_path = os.path.join(os.path.dirname(__file__), "Forum image.png")
            file = discord.File(img_path, filename="Forum image.png") if os.path.exists(img_path) else None
            thread = await forum.create_thread(
                name=f"[{member.display_name}] 주간 피드백",
                content="이번 주 잘한 점 ✨ / 아쉬운 점 💧 3가지씩 적어보세요!",
                file=file
            )
            print(f"✅ 포럼 생성 완료 → {thread.name}")
            return thread
    except Exception as e:
        print("⚠️ 포럼 생성 실패:", e)
    return None

# --- 튜토리얼 메시지 전송 ---
async def send_tutorial_step(channel: discord.TextChannel, user: discord.Member, step: int):
    info = TUTORIAL_STEPS[step]
    embed = discord.Embed(
        title=info["title"],
        description=info["desc"],
        color=0x00C9A7
    )
    embed.set_footer(text=f"그림친구 1팀 튜토리얼 • Step {step}/4")
    await channel.send(content=f"{user.mention}", embed=embed, view=StepView(step))

# --- View 정의 ---
class StartView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="시작하기", style=discord.ButtonStyle.green, custom_id="dulgi:start")
    async def start_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        user = interaction.user
        user_tutorial_progress[user.id] = 1
        await send_tutorial_step(interaction.channel, user, 1)

class StepView(discord.ui.View):
    def __init__(self, step:int): super().__init__(timeout=None); self.step=step
    @discord.ui.button(label="다음 단계", style=discord.ButtonStyle.primary, custom_id="dulgi:next")
    async def next_button(self, button:discord.ui.Button, interaction:discord.Interaction):
        await interaction.response.defer()
        user = interaction.user
        cur = user_tutorial_progress.get(user.id, 1)
        nxt = cur + 1
        if nxt == 5:
            thread = await create_weekly_forum(user)
            msg = "🎉 튜토리얼 완료! 이제 매주 피드백을 남겨보세요."
            if thread:
                msg += f"\n🗂️ 포럼이 생성되었어요! {thread.mention}"
            await interaction.channel.send(msg)
            log_ch = bot.get_channel(LOG_CHANNEL_ID)
            if log_ch:
                await log_ch.send(f"✅ **{user.display_name}** 튜토리얼 완료 ({thread.mention if thread else '실패'})")
            await asyncio.sleep(DELETE_DELAY)
            await interaction.channel.delete(reason="튜토리얼 완료 후 자동삭제 ✅")
            user_tutorial_progress[user.id] = "done"
            return
        user_tutorial_progress[user.id] = nxt
        await send_tutorial_step(interaction.channel, user, nxt)

# --- 개인 튜토리얼 채널 생성 ---
async def create_private_tutorial_channel(guild:discord.Guild, member:discord.Member):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    category = guild.get_channel(TUTORIAL_CATEGORY_ID) if TUTORIAL_CATEGORY_ID else None
    channel = await guild.create_text_channel(
        name=f"튜토리얼-{member.display_name}",
        overwrites=overwrites,
        category=category,
        reason="튜토리얼 개인 채널 생성"
    )
    channel_owner[channel.id] = member.id

    await channel.send(
        f"{member.mention} 👋 환영합니다!\n"
        f"이곳은 둘비서와 함께 진행하는 **튜토리얼 채널**이에요 🎨\n"
        f"버튼 또는 명령어(`!시작`, `!다음`, `!완료`)로 진행할 수 있어요.",
        embed=discord.Embed(
            title="🎓 그림친구 1팀 입사 오리엔테이션",
            description="둘비서가 안내를 시작합니다 💼",
            color=0x00B2FF
        ),
        view=StartView()
    )
    return channel

# --- 역할 부여 시 튜토리얼 시작 ---
@bot.event
async def on_member_update(before, after):
    new_roles = [r for r in after.roles if r not in before.roles]
    if any(r.id == TARGET_ROLE_ID for r in new_roles):
        if after.id in sent_users:
            return
        sent_users.add(after.id)
        await create_private_tutorial_channel(after.guild, after)
        print(f"✅ 튜토리얼 채널 생성 → {after.display_name}")

# --- Step1 트리거 감지 ---
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    user = message.author
    step = user_tutorial_progress.get(user.id)

    # Step1: !출근 감지
    if step == 1 and message.content.strip().startswith("!출근") and message.channel.id == CHANNEL_CHECKIN_ID:
        # 개인 튜토리얼 채널 찾기
        tutorial_ch = next((ch for ch, uid in channel_owner.items() if uid == user.id), None)
        if tutorial_ch:
            ch = bot.get_channel(tutorial_ch)
            if ch:
                embed = discord.Embed(
                    title="🎉 출근 완료!",
                    description=(
                        f"축하해요! 방금 **!출근** 명령어를 통해 무사히 출근을 완료했어요!\n"
                        f"<#{CHANNEL_CHECKIN_ID}> 채널에 출근했다는 건 이미 멋진 꿈을 향해 한 걸음 나아갔다는 뜻이에요 🌱\n\n"
                        "앞으로도 매일 출근하며 꾸준히 성장해봐요.\n"
                        "이제 다음 단계로 넘어가볼까요?"
                    ),
                    color=0xFFD166
                )
                await ch.send(embed=embed)
                user_tutorial_progress[user.id] = 2
                await send_tutorial_step(ch, user, 2)

    await bot.process_commands(message)

# --- 실행 ---
@bot.event
async def on_ready():
    keep_alive()
    bot.add_view(StartView())
    print(f"✅ 로그인 완료: {bot.user} (dulgi-tutorial-bot)")

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("⚠️ DISCORD_BOT_TOKEN 미설정")
