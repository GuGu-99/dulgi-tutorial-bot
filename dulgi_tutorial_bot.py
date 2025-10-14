# -*- coding: utf-8 -*-
# dulgi-tutorial-bot : 그림친구 1팀 튜토리얼 봇 (Persistent View / Python 3.13 호환)

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
TARGET_ROLE_ID = 1426578319410728980  # 온보딩 후 역할 ID

# ===== Flask Keep-Alive =====
app = Flask(__name__)
@app.route("/")
def home(): return "dulgi-tutorial-bot is alive!"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
def keep_alive(): Thread(target=run_flask, daemon=True).start()

# ===== 튜토리얼 단계 =====
TUTORIAL_STEPS = {
    1: {"title":"🏢 Step 1 : 출근 체험","desc":"`!출근` 명령어로 출근해요 (4점 적립) 💪"},
    2: {"title":"🎨 Step 2 : 일일-그림보고","desc":"'일일-그림보고' 채널에 오늘의 그림을 올려보세요 ✏️"},
    3: {"title":"📊 Step 3 : 보고서 보기","desc":"`!보고서` 로 이번 주 점수 확인 🌱"},
    4: {"title":"🗂️ Step 4 : 주간-그림보고",
        "desc":"‘주간-그림보고’ 채널에서 본인 닉네임 포럼을 만들어요!\n예: [둘기] 10월 2주차 피드백 ✨/💧 3가지씩 적기"}
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

# ===== 단계 DM 발송 =====
async def send_tutorial_step(user: discord.User, step: int):
    info = TUTORIAL_STEPS[step]
    embed = discord.Embed(title=info["title"], description=info["desc"], color=0x00C9A7)
    embed.set_footer(text=f"그림친구 1팀 튜토리얼 • Step {step}/4")
    await user.send(embed=embed, view=StepView(step))

# ===== View 정의 =====
class StartView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="시작하기", style=discord.ButtonStyle.green, custom_id="dulgi:start")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_dm = interaction.guild is None
        await interaction.response.defer(ephemeral=not is_dm)
        user_tutorial_progress[interaction.user.id] = 1
        await send_tutorial_step(interaction.user, 1)
        msg = "📩 DM으로 Step 1을 보냈어요!"
        try:
            await interaction.followup.send(msg, ephemeral=not is_dm)
        except: pass

class StepView(discord.ui.View):
    def __init__(self, step:int): super().__init__(timeout=None); self.step=step
    @discord.ui.button(label="다음 단계", style=discord.ButtonStyle.primary, custom_id="dulgi:next")
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_dm = interaction.guild is None
        await interaction.response.defer(ephemeral=not is_dm)
        uid = interaction.user.id; cur=user_tutorial_progress.get(uid,1); nxt=cur+1
        if nxt==5:
            thread=await create_weekly_forum(interaction.user)
            msg="🎉 튜토리얼 완료! 이제 매주 피드백을 남겨보세요."
            if thread: msg+=f"\n🗂️ 포럼이 생성되었어요! {thread.mention}"
            try: await interaction.followup.send(msg, ephemeral=not is_dm)
            except: pass
            user_tutorial_progress[uid]="done"; return
        user_tutorial_progress[uid]=nxt
        await send_tutorial_step(interaction.user,nxt)
        try: await interaction.followup.send(f"📩 DM으로 Step {nxt}을 보냈어요!", ephemeral=not is_dm)
        except: pass

# ===== 명령어 =====
@bot.command(name="튜토리얼")
async def start_tutorial(ctx):
    embed = discord.Embed(
        title="🎓 그림친구 1팀 입사 오리엔테이션",
        description="둘비서가 안내해드릴게요!\n**시작하기** 버튼으로 시작 💼",
        color=0x00B2FF)
    try:
        await ctx.author.send(embed=embed, view=StartView())
        await ctx.reply("📩 DM을 확인해주세요! 둘비서가 안내를 시작했어요.")
    except discord.Forbidden:
        await ctx.reply("⚠️ DM 수신 허용을 확인해주세요!")

# ===== 역할 부여 후 DM 트리거 =====
@bot.event
async def on_member_update(before, after):
    new_roles=[r for r in after.roles if r not in before.roles]
    if any(r.id==TARGET_ROLE_ID for r in new_roles):
        embed = discord.Embed(
            title=f"👋 {after.display_name}님, 그림친구 1팀에 오신 걸 환영합니다!",
            description="이제 모든 준비가 완료되었어요 🎨\n둘비서가 오리엔테이션을 도와드릴게요 💼",
            color=0x00B2FF)
        try:
            await after.send(embed=embed, view=StartView())
            print(f"✅ 튜토리얼 DM 전송 → {after.display_name}")
        except discord.Forbidden:
            print(f"⚠️ DM 전송 실패 → {after.display_name}")

@bot.event
async def on_ready():
    keep_alive()
    # ✅ persistent view 등록
    bot.add_view(StartView())
    print(f"✅ 로그인 완료: {bot.user} (dulgi-tutorial-bot)")

if __name__=="__main__":
    TOKEN=os.environ.get("DISCORD_BOT_TOKEN")
    if TOKEN: bot.run(TOKEN)
    else: print("⚠️ DISCORD_BOT_TOKEN 미설정")
