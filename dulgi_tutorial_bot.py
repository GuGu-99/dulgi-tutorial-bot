# -*- coding: utf-8 -*-
# dulgi-tutorial-bot : Step 4 자동포럼 + 24시간 후 삭제 + 채널명 변경

import sys, types
sys.modules["audioop"] = types.ModuleType("audioop")  # Python 3.13 대응

import asyncio, os, discord
from discord.ext import commands
from flask import Flask
from threading import Thread

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 설정 ---
FORUM_CHANNEL_ID   = 1423360385225851011
TARGET_ROLE_ID     = 1426578319410728980
LOG_CHANNEL_ID     = 1426600994522112100
CHANNEL_CHECKIN_ID = 1423359791287242782
CHANNEL_DAILY_ID   = 1423170386811682908
CHANNEL_WEEKLY_ID  = 1423360385225851011
TUTORIAL_CATEGORY_ID = None

STEP_DELAY = 10         # 단계 간 텀
DELETE_DELAY = 86400     # 24시간 (튜토리얼 채널 삭제 대기)

user_tutorial_progress = {}
sent_users = set()
channel_owner = {}

# --- KeepAlive ---
app = Flask(__name__)
@app.route("/")
def home(): return "dulgi-tutorial-bot running"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
def keep_alive(): Thread(target=run_flask, daemon=True).start()

# --- 튜토리얼 단계 설명 ---
TUTORIAL_STEPS = {
    1: {
        "title": "🏢 **Step 1 : 출근하기**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            "**!출근 명령어를 아래 채널에서 입력해보세요!**\n\n"
            "✳️ **명령어 입력 방법**\n"
            "느낌표 + `출근`\n예: `!출근`\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "> 출근은 하루의 시작이자, 꿈을 향한 첫 걸음이에요 🌅"
        )
    },
    2: {
        "title": "🎨 **Step 2 : 일일 그림보고**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            "**오늘 하루 그림 공부를 어떤 형태로든 올려보세요! ✏️**\n\n"
            "지금은 부담 갖지 말고, 우선 선배들이 어떻게 올리고 있는지 구경하러 가볼까요? 👀\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "> 아래 버튼을 눌러 ‘#일일-그림보고’ 채널로 이동해보세요!"
        )
    },
    3: {
        "title": "📊 **Step 3 : 보고서 보기**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            "`!보고서` 명령어를 입력해 이번 주 점수를 확인해보세요 🌱\n"
            "━━━━━━━━━━━━━━━━━━━"
        )
    },
    4: {
        "title": "🗂️ **Step 4 : 주간 그림보고**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            "**이제 한 주를 정리해볼 시간이에요 📅**\n\n"
            "‘#주간-그림보고’ 채널에서 본인 닉네임으로 포럼을 만들어보세요!\n"
            "예: `[둘기] 10월 2주차 피드백 ✨`\n\n"
            "잘한 점 3가지 / 아쉬운 점 3가지를 적고 이번 주를 돌아보세요.\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "> 완벽하지 않아도 괜찮아요, 기록이 곧 성장이에요 🌱"
        )
    }
}

# --- 단계별 메시지 전송 ---
async def send_tutorial_step(channel: discord.TextChannel, user: discord.Member, step: int):
    info = TUTORIAL_STEPS[step]
    guild = channel.guild
    embed = discord.Embed(title=info["title"], description=info["desc"], color=0x00C9A7)
    embed.set_footer(text=f"그림친구 1팀 튜토리얼 • Step {step}/4")

    view = discord.ui.View()
    url = None

    if step == 1:
        url = f"https://discord.com/channels/{guild.id}/{CHANNEL_CHECKIN_ID}"
        view.add_item(discord.ui.Button(label="🫡 출근기록으로 이동", url=url))

    elif step == 2:
        url = f"https://discord.com/channels/{guild.id}/{CHANNEL_DAILY_ID}"
        view.add_item(discord.ui.Button(label="🎨 그림보고 구경하러 가기", url=url))
        async def delayed_trigger():
            await asyncio.sleep(30)
            tutorial_ch = next((ch for ch, uid in channel_owner.items() if uid == user.id), None)
            if tutorial_ch:
                ch = bot.get_channel(tutorial_ch)
                if ch:
                    embed2 = discord.Embed(
                        title="🎉 잘 다녀오셨어요!",
                        description=(
                            "다른 사람들의 그림을 구경하는 것만으로도 큰 공부예요 🎨\n"
                            "이제 당신도 직접 올려볼 차례예요!\n\n"
                            "🖼️ 낙서, 크로키, 모작, 연습 드로잉, 그림 연구 등 모두 좋아요!\n"
                            "완성작이 아니어도 충분히 의미 있는 기록이에요. ✨\n\n"
                            "그럼 다음 단계로 넘어가볼까요?"
                        ),
                        color=0xFFD166
                    )
                    await ch.send(embed=embed2)
                    await asyncio.sleep(STEP_DELAY)
                    user_tutorial_progress[user.id] = 3
                    await send_tutorial_step(ch, user, 3)
        asyncio.create_task(delayed_trigger())

    elif step == 3:
        view.add_item(StepNextButton(step))

    elif step == 4:
        url = f"https://discord.com/channels/{guild.id}/{CHANNEL_WEEKLY_ID}"
        view.add_item(discord.ui.Button(label="📑 주간 포럼으로 이동", url=url))

    await channel.send(content=f"{user.mention}", embed=embed, view=view)

# --- Step3 → Step4용 버튼 ---
class StepNextButton(discord.ui.Button):
    def __init__(self, step):
        super().__init__(label="다음 단계", style=discord.ButtonStyle.primary)
        self.step = step
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user = interaction.user
        nxt = self.step + 1
        user_tutorial_progress[user.id] = nxt
        await asyncio.sleep(STEP_DELAY)
        await send_tutorial_step(interaction.channel, user, nxt)

# --- 튜토리얼 시작 ---
class StartView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="시작하기", style=discord.ButtonStyle.green)
    async def start_button(self, button, interaction):
        await interaction.response.defer()
        user = interaction.user
        user_tutorial_progress[user.id] = 1
        await send_tutorial_step(interaction.channel, user, 1)

# --- 개인 채널 생성 ---
async def create_private_tutorial_channel(guild:discord.Guild, member:discord.Member):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    category = guild.get_channel(TUTORIAL_CATEGORY_ID) if TUTORIAL_CATEGORY_ID else None
    channel = await guild.create_text_channel(
        name=f"{member.display_name}-입사도우미",
        overwrites=overwrites,
        category=category,
        reason="튜토리얼 개인 채널 생성"
    )
    channel_owner[channel.id] = member.id
    embed = discord.Embed(
        title="🎓 그림친구 1팀 입사 오리엔테이션",
        description="둘비서가 안내를 시작합니다 💼",
        color=0x00B2FF
    )
    await channel.send(
        f"{member.mention} 👋 환영합니다!\n"
        f"이곳은 둘비서와 함께 진행하는 **튜토리얼 공간**이에요 🎨",
        embed=embed,
        view=StartView()
    )
    return channel

# --- 포럼 자동 생성 함수 ---
async def create_weekly_forum(member: discord.Member):
    try:
        forum_channel = bot.get_channel(FORUM_CHANNEL_ID)
        if isinstance(forum_channel, discord.ForumChannel):
            img_path = os.path.join(os.path.dirname(__file__), "Forum image.png")
            file = discord.File(img_path, filename="Forum image.png") if os.path.exists(img_path) else None
            thread = await forum_channel.create_thread(
                name=f"[{member.display_name}] 주간 피드백",
                content="이번 주 잘한 점 ✨ / 아쉬운 점 💧 3가지씩 적어보세요!",
                file=file
            )
            print(f"✅ 포럼 생성 완료 → {thread.name}")
            return thread
    except Exception as e:
        print("⚠️ 포럼 생성 실패:", e)
    return None

# --- 역할 부여 시 트리거 ---
@bot.event
async def on_member_update(before, after):
    new_roles = [r for r in after.roles if r not in before.roles]
    if any(r.id == TARGET_ROLE_ID for r in new_roles):
        if after.id in sent_users: return
        sent_users.add(after.id)
        await create_private_tutorial_channel(after.guild, after)
        print(f"✅ 튜토리얼 채널 생성 → {after.display_name}")

# --- 메시지 트리거 ---
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return
    user = message.author
    step = user_tutorial_progress.get(user.id)

    # Step1 : 출근 감지
    if step == 1 and message.content.strip().startswith("!출근") and message.channel.id == CHANNEL_CHECKIN_ID:
        tutorial_ch = next((ch for ch, uid in channel_owner.items() if uid == user.id), None)
        if tutorial_ch:
            ch = bot.get_channel(tutorial_ch)
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
            await asyncio.sleep(STEP_DELAY)
            user_tutorial_progress[user.id] = 2
            await send_tutorial_step(ch, user, 2)

    await bot.process_commands(message)

# --- Step4 완료 시 포럼 자동 생성 + 삭제 예약 ---
@bot.event
async def on_thread_create(thread):
    user = thread.owner
    if not user or user.bot: return
    step = user_tutorial_progress.get(user.id)
    if step == 4 and thread.parent_id == CHANNEL_WEEKLY_ID:
        tutorial_ch = next((ch for ch, uid in channel_owner.items() if uid == user.id), None)
        if tutorial_ch:
            ch = bot.get_channel(tutorial_ch)
            embed = discord.Embed(
                title="🎉 튜토리얼 완료!",
                description=(
                    f"잘하셨어요 {user.mention}! 당신은 이제 스스로 성장하는 아티스트예요 🔥\n\n"
                    "매주 포럼에 기록하며 꾸준히 발전해보세요 📈\n\n"
                    "이 채널은 **24시간 후 자동 삭제**됩니다 🕓"
                ),
                color=0x43B581
            )
            await ch.send(embed=embed)

            log_ch = bot.get_channel(LOG_CHANNEL_ID)
            if log_ch:
                await log_ch.send(f"✅ **{user.display_name}** 튜토리얼 완료 🎉")

            # ✅ 24시간 후 자동 삭제 예약
            async def delayed_delete():
                await asyncio.sleep(DELETE_DELAY)
                try:
                    await ch.delete(reason="튜토리얼 완료 후 24시간 경과 자동삭제")
                    print(f"🧹 {ch.name} 채널 삭제 완료 (24h passed)")
                except:
                    pass
            asyncio.create_task(delayed_delete())

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
