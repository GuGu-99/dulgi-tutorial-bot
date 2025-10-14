# -*- coding: utf-8 -*-
# dulgi-tutorial-bot : 서버 내 비공개 튜토리얼 버전

import sys, types
sys.modules["audioop"] = types.ModuleType("audioop")  # Python 3.13 대응

import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

# ===== 기본 설정 =====
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

user_tutorial_progress = {}
FORUM_CHANNEL_ID = 1423360385225851011
TARGET_ROLE_ID = 1426578319410728980  # 온보딩 완료 역할
TUTORIAL_CATEGORY_ID = None  # 🔧 원하면 “튜토리얼용 카테고리” ID 넣기 (없으면 루트에 생성)

# ===== Keep Alive =====
app = Flask(__name__)
@app.route("/")
def home(): return "dulgi-tutorial-bot running"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
def keep_alive(): Thread(target=run_flask, daemon=True).start()

# ===== 튜토리얼 단계 =====
TUTORIAL_STEPS = {
    1: {"title": "🏢 Step 1 : 출근 체험", "desc": "`!출근` 명령어로 출근해요 (4점 적립) 💪"},
    2: {"title": "🎨 Step 2 : 일일-그림보고", "desc": "'일일-그림보고' 채널에 오늘의 그림을 올려보세요 ✏️"},
    3: {"title": "📊 Step 3 : 보고서 보기", "desc": "`!보고서` 로 이번 주 점수 확인 🌱"},
    4: {"title": "🗂️ Step 4 : 주간-그림보고",
         "desc": "‘주간-그림보고’ 채널에서 본인 닉네임 포럼을 만들어요!\n예: [둘기] 10월 2주차 피드백 ✨/💧 3가지씩 적기"}
}

# ===== 포럼 자동 생성 =====
async def create_weekly_forum(member: discord.Member):
    try:
        forum_channel = bot.get_channel(FORUM_CHANNEL_ID)
        if isinstance(forum_channel, discord.ForumChannel):
            path = os.path.join(os.path.dirname(__file__), "Forum image.png")
            file = discord.File(path, filename="Forum image.png") if os.path.exists(path) else None
            thread = await forum_channel.create_thread(
                name=f"[{member.display_name}] 주간 피드백",
                content="이번 주 잘한 점 ✨ / 아쉬운 점 💧 3가지씩 적어보세요!",
                file=file)
            print(f"✅ 포럼 생성 완료 → {thread.name}")
            return thread
    except Exception as e:
        print("⚠️ 포럼 생성 실패:", e)
    return None

# ===== 튜토리얼 메시지 전송 =====
async def send_tutorial_step(channel: discord.TextChannel, user: discord.Member, step: int):
    info = TUTORIAL_STEPS[step]
    embed = discord.Embed(title=info["title"], description=info["desc"], color=0x00C9A7)
    embed.set_footer(text=f"그림친구 1팀 튜토리얼 • Step {step}/4")
    await channel.send(content=f"{user.mention}", embed=embed, view=StepView(step))

# ===== View 정의 =====
class StartView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="시작하기", style=discord.ButtonStyle.green, custom_id="dulgi:start")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user = interaction.user
        user_tutorial_progress[user.id] = 1
        await send_tutorial_step(interaction.channel, user, 1)


class StepView(discord.ui.View):
    def __init__(self, step:int): super().__init__(timeout=None); self.step=step

    @discord.ui.button(label="다음 단계", style=discord.ButtonStyle.primary, custom_id="dulgi:next")
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user = interaction.user
        cur = user_tutorial_progress.get(user.id, 1)
        nxt = cur + 1

        if nxt == 5:
            thread = await create_weekly_forum(user)
            msg = "🎉 튜토리얼 완료! 이제 매주 피드백을 남겨보세요."
            if thread: msg += f"\n🗂️ 포럼이 생성되었어요! {thread.mention}"
            await interaction.followup.send(msg)
            await interaction.channel.delete(reason="튜토리얼 완료됨 ✅")
            user_tutorial_progress[user.id] = "done"
            return

        user_tutorial_progress[user.id] = nxt
        await send_tutorial_step(interaction.channel, user, nxt)

# ===== 임시 채널 생성 함수 =====
async def create_private_tutorial_channel(guild: discord.Guild, member: discord.Member):
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
    return channel

# ===== 역할 부여 시 트리거 =====
sent_users = set()

@bot.event
async def on_member_update(before, after):
    new_roles = [r for r in after.roles if r not in before.roles]
    if any(r.id == TARGET_ROLE_ID for r in new_roles):
        if after.id in sent_users:
            print(f"⚠️ 이미 튜토리얼 전송됨: {after.display_name}")
            return
        sent_users.add(after.id)

        # 1️⃣ 개인 채널 생성
        channel = await create_private_tutorial_channel(after.guild, after)

        # 2️⃣ 튜토리얼 시작 메시지 전송
        embed = discord.Embed(
            title=f"👋 {after.display_name}님, 그림친구 1팀에 오신 걸 환영합니다!",
            description="이제 모든 준비가 완료되었어요 🎨\n둘비서가 오리엔테이션을 도와드릴게요 💼",
            color=0x00B2FF
        )
        await channel.send(embed=embed, view=StartView())
        print(f"✅ 튜토리얼 채널 생성 → {channel.name}")

# ===== 봇 실행 =====
@bot.event
async def on_ready():
    keep_alive()
    bot.add_view(StartView())
    print(f"✅ 로그인 완료: {bot.user} (dulgi-tutorial-bot)")

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    if TOKEN: bot.run(TOKEN)
    else: print("⚠️ DISCORD_BOT_TOKEN 미설정")
