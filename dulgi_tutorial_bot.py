# -*- coding: utf-8 -*-
# dulgi-tutorial-bot : 그림친구 1팀 튜토리얼 전용봇 (Render Python 3.13 호환 완성버전)

# --- Python 3.13 호환용 audioop 더미 패치 ---
import sys, types
sys.modules["audioop"] = types.ModuleType("audioop")
# ------------------------------------------------

import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

# ===== 기본 설정 =====
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

user_tutorial_progress = {}
FORUM_CHANNEL_ID = 1423360385225851011  # ✅ '주간-그림보고' 포럼 채널 ID

# ===== Flask Keep-Alive =====
app = Flask(__name__)

@app.route("/")
def home():
    return "dulgi-tutorial-bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()

# ===== 튜토리얼 단계 =====
TUTORIAL_STEPS = {
    1: {
        "title": "🏢 Step 1: 출근 체험",
        "desc": "회사에서 하루를 시작하려면 `!출근`을 입력해요!\n출근 시 하루 4점이 적립돼요 💪",
    },
    2: {
        "title": "🎨 Step 2: 일일-그림보고",
        "desc": "'일일-그림보고' 채널에 오늘의 그림을 올려보세요!\n낙서든 크로키든, 오늘의 기록이 중요합니다 ✏️",
    },
    3: {
        "title": "📊 Step 3: 보고서 보기",
        "desc": "`!보고서`를 입력하면 이번 주의 출근횟수와 점수를 확인할 수 있어요 🌱",
    },
    4: {
        "title": "🗂️ Step 4: 주간-그림보고",
        "desc": (
            "'주간-그림보고' 채널에서 **본인 닉네임이 들어간 포럼**을 만들어보세요!\n\n"
            "예: `[둘기] 10월 2주차 피드백`\n"
            "잘한 점 ✨ / 아쉬운 점 💧 3가지씩 적으면 완벽해요!"
        ),
    },
}

# ===== 포럼 자동 생성 =====
async def create_weekly_forum(member: discord.Member):
    """주간-그림보고 포럼 자동 생성 + 이미지 첨부"""
    try:
        forum_channel = bot.get_channel(FORUM_CHANNEL_ID)
        if isinstance(forum_channel, discord.ForumChannel):
            img_path = os.path.join(os.path.dirname(__file__), "Forum image.png")
            file = None
            if os.path.exists(img_path):
                file = discord.File(img_path, filename="Forum image.png")

            thread = await forum_channel.create_thread(
                name=f"[{member.display_name}] 주간 피드백",
                content=(
                    "이번 주 잘한 점 ✨ / 아쉬운 점 💧 을 3가지씩 적어보세요!\n\n"
                    "예시:\n✨ 색감이 좋아졌어요\n✨ 라인 정리가 깔끔해졌어요\n💧 구도 다양성이 부족했어요"
                ),
                file=file
            )
            print(f"✅ 포럼 생성 완료: {thread.name}")
            return thread
        else:
            print("⚠️ 지정된 채널이 포럼 채널이 아닙니다.")
    except Exception as e:
        print(f"⚠️ 포럼 생성 실패: {e}")
    return None

# ===== 튜토리얼 단계 DM 발송 =====
async def send_tutorial_step(user: discord.User, step: int):
    info = TUTORIAL_STEPS[step]
    embed = discord.Embed(
        title=info["title"],
        description=info["desc"],
        color=0x00C9A7
    )
    embed.set_footer(text=f"그림친구 1팀 튜토리얼 • Step {step}/4")
    view = discord.ui.View()
    if step < 4:
        view.add_item(discord.ui.Button(label="다음 단계로", style=discord.ButtonStyle.primary, custom_id="next_step_dm"))
    else:
        view.add_item(discord.ui.Button(label="튜토리얼 완료 🎉", style=discord.ButtonStyle.success, custom_id="finish_dm"))
    await user.send(embed=embed, view=view)

# ===== 버튼 View 정의 =====
class TutorialView(discord.ui.View):
    def __init__(self, step: int = 0):
        super().__init__(timeout=None)
        self.step = step

    @discord.ui.button(label="시작하기", style=discord.ButtonStyle.green, custom_id="start_tutorial")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_tutorial_progress[interaction.user.id] = 1
        await send_tutorial_step(interaction.user, 1)
        await interaction.response.defer()

    @discord.ui.button(label="다음 단계", style=discord.ButtonStyle.primary, custom_id="next_step")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        cur = user_tutorial_progress.get(uid, 1)
        nxt = cur + 1

        if nxt == 5:
            thread = await create_weekly_forum(interaction.user)
            msg = "🎉 튜토리얼 완료! 이제 매주 피드백을 남겨보세요."
            if thread:
                msg += f"\n🗂️ 자동으로 포럼이 생성되었어요! {thread.mention}"
            await interaction.response.send_message(msg, ephemeral=True)
            user_tutorial_progress[uid] = "done"
            return

        user_tutorial_progress[uid] = nxt
        await send_tutorial_step(interaction.user, nxt)
        await interaction.response.defer()

# ===== 명령어 =====
@bot.command(name="튜토리얼")
async def start_tutorial(ctx):
    try:
        embed = discord.Embed(
            title="🎓 그림친구 1팀 입사 오리엔테이션",
            description="둘비서가 안내해드릴게요!\n아래 **시작하기** 버튼을 눌러 튜토리얼을 시작하세요 💼",
            color=0x00B2FF
        )
        await ctx.author.send(embed=embed, view=TutorialView(step=0))
        await ctx.reply("📩 DM을 확인해주세요! 둘비서가 안내를 시작했어요.")
    except discord.Forbidden:
        await ctx.reply("⚠️ DM이 차단되어 있어요! 개인 메시지 수신을 허용해주세요.")

# ===== 신규 입장자 자동 DM =====
@bot.event
async def on_member_join(member: discord.Member):
    try:
        embed = discord.Embed(
            title=f"👋 {member.display_name}님, 그림친구 1팀에 오신 걸 환영합니다!",
            description=(
                "이곳은 매일 그림 그리고 함께 성장하는 **그림 회사**예요 🎨\n\n"
                "둘비서가 입사 오리엔테이션을 도와드릴게요!\n"
                "아래 버튼을 눌러 튜토리얼을 시작해보세요 💼"
            ),
            color=0x00B2FF
        )
        await member.send(embed=embed, view=TutorialView(step=0))
        print(f"✅ 신규 입사자 DM 전송 완료: {member.display_name}")
    except discord.Forbidden:
        print(f"⚠️ {member.display_name} 님에게 DM 전송 실패 (DM 차단됨)")

@bot.event
async def on_ready():
    keep_alive()
    print(f"✅ 로그인 완료: {bot.user} (dulgi-tutorial-bot)")

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    if not TOKEN:
        print("⚠️ DISCORD_BOT_TOKEN이 설정되지 않았습니다.")
    else:
        bot.run(TOKEN)
