# -*- coding: utf-8 -*-
# 신입 OT (인사팀 안내 버전, 멘션 체크 제거)
# Step 1~4 전체 포함 / 자동포럼 / 24시간 후 삭제 / 문의 채널 안내

import sys, types
sys.modules["audioop"] = types.ModuleType("audioop")

import asyncio, os, discord
from discord.ext import commands
from flask import Flask
from threading import Thread

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 기본 설정 ---
FORUM_CHANNEL_ID   = 1423360385225851011
TARGET_ROLE_ID     = 1426578319410728980
LOG_CHANNEL_ID     = 1426600994522112100
CHANNEL_CHECKIN_ID = 1423359791287242782
CHANNEL_DAILY_ID   = 1423170386811682908
CHANNEL_WEEKLY_ID  = 1423360385225851011
CHANNEL_QNA_ID     = 1424270317777326250  # 문의 채널
TUTORIAL_CATEGORY_ID = None

STEP_DELAY = 10
DELETE_DELAY = 86400  # 24시간 후 삭제

user_ot_progress = {}
sent_users = set()
channel_owner = {}

# --- KeepAlive ---
app = Flask(__name__)
@app.route("/")
def home(): return "신입OT 인사팀 봇 작동 중"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
def keep_alive(): Thread(target=run_flask, daemon=True).start()

# --- 단계별 메시지 ---
OT_STEPS = {
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
        "title": "📊 **Step 3 : 보고서 확인하기**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            "**오늘 하루의 성과를 확인해볼까요?**\n\n"
            "✳️ **명령어 입력 방법**\n"
            "느낌표 + `보고서`\n예: `!보고서`\n\n"
            "아래 버튼을 눌러 `#출근기록` 채널로 이동 후 명령어를 입력해보세요! 🌱\n"
            "━━━━━━━━━━━━━━━━━━━"
        )
    },
    4: {
        "title": "🗂️ **Step 4 : 주간 그림보고 (포럼 작성)**",
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

# --- 안내 메시지 전송 ---
async def send_ot_step(channel: discord.TextChannel, user: discord.Member, step: int):
    info = OT_STEPS[step]
    guild = channel.guild
    embed = discord.Embed(title=info["title"], description=info["desc"], color=0x00C9A7)
    embed.set_footer(text=f"그림친구 1팀 신입 OT • Step {step}/4")
    view = discord.ui.View()
    url = None

    if step == 1:
        url = f"https://discord.com/channels/{guild.id}/{CHANNEL_CHECKIN_ID}"
        view.add_item(discord.ui.Button(label="🫡 출근기록으로 이동", url=url))
    elif step == 2:
        url = f"https://discord.com/channels/{guild.id}/{CHANNEL_DAILY_ID}"
        view.add_item(discord.ui.Button(label="🎨 그림보고 구경하러 가기", url=url))
    elif step == 3:
        url = f"https://discord.com/channels/{guild.id}/{CHANNEL_CHECKIN_ID}"
        view.add_item(discord.ui.Button(label="📊 출근기록으로 이동", url=url))
    elif step == 4:
        url = f"https://discord.com/channels/{guild.id}/{CHANNEL_WEEKLY_ID}"
        view.add_item(discord.ui.Button(label="📑 주간 포럼으로 이동", url=url))

    await channel.send(embed=embed, view=view)

# --- Step 전환 ---
async def advance_step(user, current_step):
    ot_ch = next((ch for ch, uid in channel_owner.items() if uid == user.id), None)
    if not ot_ch: return
    ch = bot.get_channel(ot_ch)
    nxt = current_step + 1
    user_ot_progress[user.id] = nxt
    await asyncio.sleep(STEP_DELAY)
    await send_ot_step(ch, user, nxt)

# --- 개인 OT 채널 생성 ---
async def create_private_ot_channel(guild, member):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    category = guild.get_channel(TUTORIAL_CATEGORY_ID) if TUTORIAL_CATEGORY_ID else None
    channel = await guild.create_text_channel(
        name=f"{member.display_name}-입사도우미",
        overwrites=overwrites,
        category=category
    )
    channel_owner[channel.id] = member.id

    embed = discord.Embed(
        title="🎓 그림친구 1팀 신입 OT 안내",
        description="안녕하세요! 인사팀입니다 💼\n\n지금부터 천천히 입사 OT를 진행하겠습니다.",
        color=0x00B2FF
    )
    await channel.send(
        f"{member.mention} 👋 반가워요!\n"
        f"이곳은 **인사팀과 함께 진행하는 신입 OT 공간**이에요 🎨",
        embed=embed,
        view=StartView()
    )
    return channel

# --- 시작 버튼 ---
class StartView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="OT 시작하기", style=discord.ButtonStyle.green)
    async def start_button(self, button, interaction):
        await interaction.response.defer()
        user = interaction.user
        user_ot_progress[user.id] = 1
        await send_ot_step(interaction.channel, user, 1)

# --- 역할 부여 시 자동 생성 ---
@bot.event
async def on_member_update(before, after):
    new_roles = [r for r in after.roles if r not in before.roles]
    if any(r.id == TARGET_ROLE_ID for r in new_roles):
        if after.id in sent_users: return
        sent_users.add(after.id)
        await create_private_ot_channel(after.guild, after)
        print(f"✅ OT 채널 생성 → {after.display_name}")

# --- 메시지 트리거 ---
@bot.event
async def on_message(message):
    if message.author.bot: return
    user = message.author
    step = user_ot_progress.get(user.id)
    if not step: return

    # STEP 1 : 출근
    if step == 1 and message.content.strip().startswith("!출근") and message.channel.id == CHANNEL_CHECKIN_ID:
        ot_ch = next((ch for ch, uid in channel_owner.items() if uid == user.id), None)
        if ot_ch:
            ch = bot.get_channel(ot_ch)
            embed = discord.Embed(
                title="🎉 출근 완료!",
                description=(f"좋아요 {user.mention}!\n\n"
                             f"<#{CHANNEL_CHECKIN_ID}> 채널에서 출근을 완료했어요 🌅\n"
                             "매일의 출근이 곧 당신의 루틴이 될 거예요.\n\n"
                             "이제 다음 단계로 넘어가볼까요?"),
                color=0xFFD166
            )
            await ch.send(embed=embed)
            await advance_step(user, 1)

    # STEP 3 : !보고서
    elif step == 3 and message.content.strip().startswith("!보고서") and message.channel.id == CHANNEL_CHECKIN_ID:
        ot_ch = next((ch for ch, uid in channel_owner.items() if uid == user.id), None)
        if ot_ch:
            ch = bot.get_channel(ot_ch)
            embed = discord.Embed(
                title="📊 보고서 확인 완료!",
                description=(f"잘했어요 {user.mention}! 🎉\n\n"
                             f"<#{CHANNEL_CHECKIN_ID}> 채널에서 보고서를 확인했네요.\n"
                             "앞으로도 이곳에서 하루의 성과를 꾸준히 체크해봐요 🌱\n\n"
                             "이제 마지막 단계로 넘어가볼까요?"),
                color=0x43B581
            )
            await ch.send(embed=embed)
            await advance_step(user, 3)

    await bot.process_commands(message)

# --- Step4 : 자동 포럼 + 24시간 후 삭제 + 문의 안내 ---
@bot.event
async def on_thread_create(thread):
    user = thread.owner
    if not user or user.bot: return
    step = user_ot_progress.get(user.id)
    if step == 4 and thread.parent_id == CHANNEL_WEEKLY_ID:
        ot_ch = next((ch for ch, uid in channel_owner.items() if uid == user.id), None)
        if ot_ch:
            ch = bot.get_channel(ot_ch)
            embed = discord.Embed(
                title="🎉 신입 OT 완료!",
                description=(f"이제 당신은 모든 준비를 마쳤어요! 🎨\n\n"
                             "매주 포럼에 기록을 남기며 멋진 루틴을 만들어봐요 🌱\n\n"
                             f"혹시 진행 중 궁금한 점이나 오류가 있었다면 <#{CHANNEL_QNA_ID}> 채널로 문의해주세요 📨\n\n"
                             "이 채널은 **24시간 후 자동 삭제**됩니다 🕓"),
                color=0x43B581
            )
            await ch.send(embed=embed)

            async def delayed_delete():
                await asyncio.sleep(DELETE_DELAY)
                try:
                    await ch.delete(reason="신입 OT 완료 후 24시간 경과 자동삭제")
                    print(f"🧹 {ch.name} 삭제 완료 (24h)")
                except:
                    pass
            asyncio.create_task(delayed_delete())

# --- 실행 ---
@bot.event
async def on_ready():
    keep_alive()
    bot.add_view(StartView())
    print(f"✅ 로그인 완료: {bot.user} (인사팀 OT 봇)")

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("⚠️ DISCORD_BOT_TOKEN 미설정")
