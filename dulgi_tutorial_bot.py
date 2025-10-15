# -*- coding: utf-8 -*-
# 신입 OT (인사팀 안내 버전 vFinal)
# Step2 자동 트리거 / Step4 안정화 / 시각적 간격 확장 / 각 Step 시작 멘션 추가

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

# --- 설정 ---
FORUM_CHANNEL_ID   = 1423360385225851011
TARGET_ROLE_ID     = 1426578319410728980
LOG_CHANNEL_ID     = 1426600994522112100
CHANNEL_CHECKIN_ID = 1423359791287242782
CHANNEL_DAILY_ID   = 1423170386811682908
CHANNEL_WEEKLY_ID  = 1423360385225851011
CHANNEL_QNA_ID     = 1424270317777326250
MENTION_THREAD_ID  = 1426954981638013049  # 포럼 생성 후 멘션할 스레드
TUTORIAL_CATEGORY_ID = None

STEP_DELAY = 10
STEP2_DELAY = 20
DELETE_DELAY = 86400

user_ot_progress = {}
sent_users = set()
channel_owner = {}
step4_created = set()

# --- KeepAlive ---
app = Flask(__name__)
@app.route("/")
def home(): return "신입OT 인사팀 봇 작동 중"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
def keep_alive(): Thread(target=run_flask, daemon=True).start()

# --- OT 단계 텍스트 ---
OT_STEPS = {
    1: {
        "title": "🏢 **Step 1 : 출근하기**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "**!출근 명령어를 아래 채널에서 입력해보세요!**\n\n"
            "✳️ **명령어 입력 방법**\n"
            "느낌표 + `출근`\n예: `!출근`\n\n\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "> 출근은 하루의 시작이자, 꿈을 향한 첫 걸음이에요 🌅"
        )
    },
    2: {
        "title": "🎨 **Step 2 : 일일 그림보고**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "**오늘 하루 그림 공부를 어떤 형태로든 올려보세요! ✏️**\n\n"
            "지금은 부담 갖지 말고, 우선 선배들이 어떻게 올리고 있는지 구경하러 가볼까요? 👀\n\n\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "> 아래 버튼을 눌러 ‘#일일-그림보고’ 채널로 이동해보세요!"
        )
    },
    3: {
        "title": "📊 **Step 3 : 보고서 확인하기**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "**오늘 하루의 성과를 확인해볼까요?**\n\n"
            "✳️ **명령어 입력 방법**\n"
            "느낌표 + `보고서`\n예: `!보고서`\n\n\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "> 아래 버튼을 눌러 `#출근기록` 채널로 이동 후 명령어를 입력해보세요! 🌱"
        )
    },
    4: {
        "title": "🗂️ **Step 4 : 주간 그림보고 (포럼 작성)**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "**이제 한 주를 정리해볼 시간이에요 📅**\n\n"
            "‘#주간-그림보고’ 채널에서 본인 닉네임으로 포럼을 만들어보세요!\n"
            "예: `[둘기] 10월 2주차 피드백 ✨`\n\n\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "> 완벽하지 않아도 괜찮아요, 기록이 곧 성장이에요 🌱"
        )
    }
}

# --- Step 전송 ---
async def send_ot_step(channel, user, step):
    info = OT_STEPS[step]
    guild = channel.guild
    await channel.send(f"{user.mention} 🚀")  # Step 시작 멘션
    embed = discord.Embed(title=info["title"], description=info["desc"], color=0x00C9A7)
    embed.set_footer(text=f"그림친구 1팀 신입 OT • Step {step}/4")
    view = discord.ui.View()

    if step == 1:
        view.add_item(discord.ui.Button(label="🫡 출근기록으로 이동",
                                        style=discord.ButtonStyle.link,
                                        url=f"https://discord.com/channels/{guild.id}/{CHANNEL_CHECKIN_ID}"))

   elif step == 2:
    daily_url = f"https://discord.com/channels/{guild.id}/{CHANNEL_DAILY_ID}"
    view.add_item(discord.ui.Button(
        label="🎨 그림보고 구경하러 가기",
        style=discord.ButtonStyle.link,
        url=daily_url
    ))

    # 25초 뒤 자동 트리거 실행
    asyncio.create_task(trigger_step2_after_delay(user))


    elif step == 3:
        view.add_item(discord.ui.Button(label="📊 출근기록으로 이동",
                                        style=discord.ButtonStyle.link,
                                        url=f"https://discord.com/channels/{guild.id}/{CHANNEL_CHECKIN_ID}"))

    elif step == 4:
        view.add_item(Step4ForumButton(user, guild))

    await channel.send(embed=embed, view=view)

# --- Step2 : 일일 그림보고 (25초 뒤 자동 트리거) ---
async def trigger_step2_after_delay(user: discord.Member):
    """Step2 유도 메시지 이후 25초 후 자동 트리거"""
    await asyncio.sleep(25)  # 액션 유도 메시지 후 25초 대기
    ch_id = next((cid for cid, uid in channel_owner.items() if uid == user.id), None)
    if not ch_id:
        return
    ch = bot.get_channel(ch_id)
    if not ch:
        return

    # 10초 텀 후 축하 멘션
    await asyncio.sleep(10)
    await ch.send(f"{user.mention} ✅ 잘 다녀오셨나요?")

    embed = discord.Embed(
        title="🎉 그림보고 탐방 완료!",
        description=(
            "다른 사람들의 그림을 보 것만으로도 큰 공부예요 🎨\n"
            "이제 당신도 직접 올려볼 차례예요!\n\n"
            "🖼️ 낙서, 크로키, 모작, 연습 드로잉, 그림 연구 등 모두 좋아요!\n"
            "완성작이 아니어도 충분히 의미 있는 기록이에요. ✨\n\n"
            "이제 다음 단계로 넘어가볼까요?"
        ),
        color=0xFFD166
    )
    await ch.send(embed=embed)
    await asyncio.sleep(STEP_DELAY)
    await send_ot_step(ch, user, 3)
    user_ot_progress[user.id] = 3


# --- Step4: 포럼 생성 버튼 ---
class Step4ForumButton(discord.ui.Button):
    def __init__(self, user, guild):
        super().__init__(label="📑 주간 포럼으로 이동",
                         style=discord.ButtonStyle.success,
                         url=f"https://discord.com/channels/{guild.id}/{CHANNEL_WEEKLY_ID}")
        self.user = user
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user = self.user

        # 중복 방지
        if user.id in step4_created:
            await interaction.followup.send("이미 포럼이 생성되었습니다 ✅", ephemeral=True)
            return
        step4_created.add(user.id)

        # 생성 시작
        await asyncio.sleep(3)
        forum_channel = bot.get_channel(FORUM_CHANNEL_ID)
        if isinstance(forum_channel, discord.ForumChannel):
            thread = await forum_channel.create_thread(
                name=f"{user.display_name}",
                content="이번 주 잘한 점 ✨ / 아쉬운 점 💧 3가지씩 적어보세요!"
            )
            print(f"✅ 포럼 생성 완료: {thread.name}")

        # 개인 OT 채널
        ch_id = next((cid for cid, uid in channel_owner.items() if uid == user.id), None)
        if not ch_id: return
        ch = bot.get_channel(ch_id)
        if not ch: return

        await asyncio.sleep(10)
        await ch.send(f"{user.mention} 🎉 신입 OT 완료!")
        embed = discord.Embed(
            title="🎉 신입 OT 완료!",
            description=(
                "이제 당신은 모든 준비를 마쳤어요! 🎨\n\n"
                "매주 포럼에 기록을 남기며 멋진 루틴을 만들어봐요 🌱\n\n"
                f"궁금한 점이나 오류가 있다면 <#{CHANNEL_QNA_ID}> 채널로 문의해주세요 📨\n\n"
                "이 채널은 **24시간 후 자동 삭제**됩니다 🕓"
            ),
            color=0x43B581
        )
        await ch.send(embed=embed)

        # 5초 후 멘션 스레드로 알림
        await asyncio.sleep(5)
        mention_thread = bot.get_channel(MENTION_THREAD_ID)
        if mention_thread:
            await mention_thread.send(f"{user.mention} 🎉 주간 포럼 생성 완료!")

        # 자동 삭제 예약
        asyncio.create_task(delete_after_24h(ch))

# --- Step1 & Step3 트리거 ---
@bot.event
async def on_message(message):
    if message.author.bot: return
    user = message.author
    step = user_ot_progress.get(user.id)
    if not step: return

    # Step1
    if step == 1 and message.content.strip().startswith("!출근") and message.channel.id == CHANNEL_CHECKIN_ID:
        ch_id = next((cid for cid, uid in channel_owner.items() if uid == user.id), None)
        if not ch_id: return
        ch = bot.get_channel(ch_id)
        await asyncio.sleep(10)
        await ch.send(f"{user.mention} ✅ 출근 완료!")
        embed = discord.Embed(
            title="🎉 출근 완료!",
            description=(
                f"<#{CHANNEL_CHECKIN_ID}> 채널에서 출근을 완료했어요 🌅\n\n"
                "매일의 출근이 당신의 루틴이 될 거예요.\n\n"
                "이제 다음 단계로 넘어가볼까요?"
            ),
            color=0xFFD166
        )
        await ch.send(embed=embed)
        await asyncio.sleep(STEP_DELAY)
        await send_ot_step(ch, user, 2)
        user_ot_progress[user.id] = 2

    # Step3
    elif step == 3 and message.content.strip().startswith("!보고서") and message.channel.id == CHANNEL_CHECKIN_ID:
        ch_id = next((cid for cid, uid in channel_owner.items() if uid == user.id), None)
        if not ch_id: return
        ch = bot.get_channel(ch_id)
        await asyncio.sleep(10)
        await ch.send(f"{user.mention} ✅ 보고서 확인 완료!")
        embed = discord.Embed(
            title="📊 보고서 확인 완료!",
            description=(
                f"<#{CHANNEL_CHECKIN_ID}> 채널에서 보고서를 확인했어요!\n\n"
                "앞으로도 이곳에서 하루의 성과를 꾸준히 체크해봐요 🌱\n\n"
                "이제 마지막 단계로 넘어가볼까요?"
            ),
            color=0x43B581
        )
        await ch.send(embed=embed)
        await asyncio.sleep(STEP_DELAY)
        await send_ot_step(ch, user, 4)
        user_ot_progress[user.id] = 4

    await bot.process_commands(message)

# --- 자동 삭제 ---
async def delete_after_24h(channel):
    await asyncio.sleep(DELETE_DELAY)
    try:
        await channel.delete(reason="신입 OT 완료 후 24시간 경과 자동삭제")
        print(f"🧹 {channel.name} 삭제 완료 (24h)")
    except:
        pass

# --- 개인 OT 채널 생성 ---
async def create_private_ot_channel(guild, member):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    channel = await guild.create_text_channel(
        name=f"{member.display_name}-입사도우미",
        overwrites=overwrites
    )
    channel_owner[channel.id] = member.id

    embed = discord.Embed(
        title="🎓 그림친구 1팀 신입 OT 안내",
        description="안녕하세요! 인사팀입니다 💼\n\n지금부터 천천히 **신입 OT를 진행하겠습니다.**",
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
