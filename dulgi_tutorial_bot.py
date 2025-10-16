# -*- coding: utf-8 -*-
# 신입 OT (인사팀 안내 버전 · vFinal+spacing)
# - Step2: 안내 후 25초 자동 트리거 + 멘션 전 10초 텀
# - Step 간 10초 텀
# - 이동 버튼: 초록색(클릭 시 채널 링크 안내)
# - Step4: 포럼 이미지 제거 / 1회만 생성(버튼 비활성) / 안내글 7일 후 삭제 / 20초 뒤 개인 채널 멘션
# - 모든 멘션/임베드 사이 여백 메시지(Zero-width space)

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

# --- 고정 설정값 ---
FORUM_CHANNEL_ID     = 1423360385225851011
TARGET_ROLE_ID       = 1426578319410728980
LOG_CHANNEL_ID       = 1426600994522112100
CHANNEL_CHECKIN_ID   = 1423359791287242782  # 출근기록(=보고서 명령도 여기서)
CHANNEL_DAILY_ID     = 1423170386811682908  # 일일-그림보고
CHANNEL_WEEKLY_ID    = 1423360385225851011  # 주간-그림보고 (포럼 채널)
CHANNEL_QNA_ID       = 1424270317777326250  # 문의 채널
TUTORIAL_CATEGORY_ID = None

STEP_DELAY  = 10        # Step 간 텀
STEP2_DELAY = 25        # Step2 자동 트리거 대기
DELETE_DELAY = 86400    # 24시간 후 개인 채널 삭제 (이미 적용되어 있다면 유지)

user_ot_progress: dict[int, int] = {}     # user_id -> current_step
sent_users: set[int] = set()              # 이미 OT 채널 생성된 유저
channel_owner: dict[int, int] = {}        # channel_id -> user_id (개인 OT 채널 매핑)

# --- KeepAlive (Render 등에서 필요) ---
app = Flask(__name__)
@app.route("/")
def home(): return "신입OT 인사팀 봇 작동 중"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
def keep_alive(): Thread(target=run_flask, daemon=True).start()

# --- 공용 유틸 ---
async def send_space(channel: discord.abc.Messageable, delay: float = 0.5):
    """메시지 사이 시각적 여백을 위한 빈 메시지 전송"""
    await asyncio.sleep(delay)
    await channel.send("\u200b")

def channel_mention(cid: int) -> str:
    return f"<#{cid}>"

# --- 단계별 텍스트 ---
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
            "━━━━━━━━━━━━━━━━━━━"
        )
    },
    3: {
        "title": "📊 **Step 3 : 보고서 확인하기**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            "**오늘 하루의 성과를 확인해볼까요?**\n\n"
            "✳️ **명령어 입력 방법**\n"
            "느낌표 + `보고서`\n예: `!보고서`\n\n"
            f"{channel_mention(CHANNEL_CHECKIN_ID)} 채널로 이동 후 명령어를 입력해보세요! 🌱\n"
            "━━━━━━━━━━━━━━━━━━━"
        )
    },
    4: {
        "title": "🗂️ **Step 4 : 주간 그림보고 (포럼 작성)**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            "**이제 한 주를 정리해볼 시간이에요 📅**\n\n"
            "‘#주간-그림보고’ 채널에 **본인 닉네임**으로 포럼을 만들어드릴게요!\n"
            "시작버튼을 누르고 잠시 기다려주세요!"
            "━━━━━━━━━━━━━━━━━━━\n"
        )
    }
}

# --- Step2: 안내 후 25초 자동 트리거 ---
async def trigger_step2_after_delay(user: discord.Member):
    await asyncio.sleep(STEP2_DELAY)  # Step2 안내 후 25초
    # 개인 OT 채널
    ch_id = next((cid for cid, uid in channel_owner.items() if uid == user.id), None)
    if not ch_id: return
    ch = bot.get_channel(ch_id)
    if not ch: return

    # 멘션 전 10초 텀
    await asyncio.sleep(10)
    await ch.send(f"{user.mention} ✅ 잘 다녀오셨나요?")
    await send_space(ch)

    embed = discord.Embed(
        title="🎉 그림보고 탐방 완료!",
        description=(
            "다른 사람들의 그림을 구경하는 것만으로도 큰 공부예요 🎨\n"
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

# --- 버튼: 초록색 '이동' (URL 버튼은 색 지정 불가 → 클릭 시 안내로 대체) ---
class GreenJumpButton(discord.ui.Button):
    """초록 버튼 클릭 시 대상 채널을 안내(멘션/URL 유도)."""
    def __init__(self, label: str, target_channel_id: int, user: discord.Member):
        super().__init__(label=label, style=discord.ButtonStyle.success, custom_id=f"jump_{target_channel_id}")
        self.target_channel_id = target_channel_id
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        # 본인만 누를 수 있게 가드(선택)
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("본인 진행용 버튼이에요 🙏", ephemeral=True)
            return
        await interaction.response.send_message(
            f"{channel_mention(self.target_channel_id)} 채널로 이동해서 진행해주세요!", ephemeral=True
        )

# --- Step4: 포럼 생성 버튼 ---
class Step4Button(discord.ui.Button):
    def __init__(self, user: discord.Member):
        super().__init__(label="📑 주간 포럼 체험시작!", style=discord.ButtonStyle.success, custom_id="weekly_forum")
        self.user = user
        self.clicked = False  # 중복 생성 방지

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("본인 진행용 버튼이에요 🙏", ephemeral=True)
            return

        if self.clicked:
            await interaction.response.send_message("이미 포럼이 생성되었어요 ✅", ephemeral=True)
            return

        self.clicked = True
        await interaction.response.defer()

        # 버튼 비활성화 갱신
        self.disabled = True
        await interaction.message.edit(view=self.view)

        # 클릭 후 10초 텀
        await asyncio.sleep(10)

        forum_channel = bot.get_channel(FORUM_CHANNEL_ID)
        if not isinstance(forum_channel, discord.ForumChannel):
            await interaction.followup.send("⚠️ 포럼 채널을 찾을 수 없어요.", ephemeral=True)
            return

        # ✅ 포럼 생성 (이미지 완전 제거)
        thread = await forum_channel.create_thread(
            name=f"[{self.user.display_name}] 주간 피드백",
            content=f"{self.user.mention}님을 위한 주간 피드백 공간이에요 🎨"
        )
        print(f"✅ 포럼 생성 완료: {thread.name}")

        # ✅ 포럼 안내 글 전송 (+7일 뒤 자동 삭제)
        feedback_text = (
            "✅ **목표**\n"
            "한주간 내가 그림 관련해서 한 것들을 정리하고 스스로 피드백을 진행한다\n\n"
            "📔 **방법**\n"
            "자신의 디스코드 닉네임으로 '새 포스트'를 만들고, 아래 양식으로 작성하세요.\n"
            "(매일 하면 더 좋아요! 자유롭게 블로그처럼 이용해도 됩니다 🥰)\n\n"
            "**⚠️ 주의사항**\n"
            "자기비하가 아닌, 제3자의 시선으로 관찰하듯 피드백해주세요!\n\n"
            "ㅡㅡㅡㅡ작성 양식ㅡㅡㅡㅡ\n\n"
            "[한 주간 진행한 것들]\n\n"
            "[잘한 점] (최소 3가지)\n1.\n2.\n3.\n\n"
            "[개선해야 할 점] (최소 3가지)\n1.\n2.\n3.\n\n"
            "[개선 방법]\n- \n- "
        )
        msg = await thread.send(f"{self.user.mention}\n{feedback_text}")

        async def delete_feedback_message():
            # 7일 뒤 삭제 (604800초)
            await asyncio.sleep(604800)
            try:
                await msg.delete()
                print(f"🗑️ 포럼 안내 메시지 자동 삭제 완료 ({self.user.display_name})")
            except:
                pass
        asyncio.create_task(delete_feedback_message())

        # ✅25초 뒤 개인 OT 채널에 멘션/안내
        async def followup_back_to_private():
            await asyncio.sleep(25)
            ch_id = next((cid for cid, uid in channel_owner.items() if uid == self.user.id), None)
            if not ch_id: return
            ch = bot.get_channel(ch_id)
            if not ch: return

            await ch.send(f"{self.user.mention} 🪶 여러분만의 **주간 그림 보고서 방**이 생성되었어요!")
            await send_space(ch)
            embed = discord.Embed(
                title="📔 주간 보고서 안내",
                description=(
                    "새로운 포럼이 열렸어요 🎨\n"
                    "썸네일 이미지는 자유롭게 꾸며도 좋고,\n"
                    "예시가 궁금하다면 아래 링크를 참고하세요.\n\n"
                    "[예시 보기](https://discord.com/channels/1310854848442269767/1426954981638013049/1426954981638013049)\n\n"
                    "매주 한 번씩은 꼭 작성해주세요!\n"
                    "작성하는 그 순간, 이미 성장하고 있는 거예요 🌱"
                ),
                color=0x43B581
            )
            await ch.send(embed=embed)
        asyncio.create_task(followup_back_to_private())

# ✅ 튜토리얼(신입 OT) 종료 메시지 추가
await send_space(ch)
embed_done = discord.Embed(
    title="🎉 신입 OT 완료!",
    description=(
        "이제 당신은 모든 준비를 마쳤어요! 🎨\n\n"
        "이곳에서의 시간 동안 기본적인 루틴을 익히셨으니,\n"
        "앞으로는 직접 성장의 여정을 이어가보세요 🌱\n\n"
        f"궁금한 점이나 오류가 있다면 <#{CHANNEL_QNA_ID}> 채널로 문의해주세요 📨\n\n"
        "이 채널은 **24시간 후 자동 삭제**됩니다 🕓"
    ),
    color=0x43B581
)
await ch.send(embed=embed_done)



# --- 단계 안내 메시지 전송 ---
async def send_ot_step(channel: discord.TextChannel, user: discord.Member, step: int):
    info = OT_STEPS[step]
    embed = discord.Embed(title=info["title"], description=info["desc"], color=0x00C9A7)
    embed.set_footer(text=f"그림친구 1팀 신입 OT • Step {step}/4")

    view = discord.ui.View()

    if step == 1:
        # 초록 버튼(클릭 시 채널 안내)
        view.add_item(GreenJumpButton("🫡 출근체험 시작!", CHANNEL_CHECKIN_ID, user))

    elif step == 2:
        view.add_item(GreenJumpButton("🎨 그림보고 체험시작!", CHANNEL_DAILY_ID, user))
        # 안내 후 25초 자동 트리거
        asyncio.create_task(trigger_step2_after_delay(user))

    elif step == 3:
        view.add_item(GreenJumpButton("📊 보고서 체험 시작!", CHANNEL_CHECKIN_ID, user))

    elif step == 4:
        view.add_item(Step4Button(user))

    await channel.send(embed=embed, view=view)

# --- Step1 & Step3 트리거 감지 ---
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    user = message.author
    step = user_ot_progress.get(user.id)
    if not step:
        return

    # Step 1: !출근 (출근기록 채널)
    if step == 1 and message.content.strip().startswith("!출근") and message.channel.id == CHANNEL_CHECKIN_ID:
        ch_id = next((cid for cid, uid in channel_owner.items() if uid == user.id), None)
        if not ch_id:
            return
        ch = bot.get_channel(ch_id)

        await asyncio.sleep(10)  # 트리거 후 10초 텀
        await ch.send(f"{user.mention} ✅ 출근 완료!")
        await send_space(ch)
        embed = discord.Embed(
            title="🎉 출근 완료!",
            description=(
                f"{channel_mention(CHANNEL_CHECKIN_ID)} 채널에서 출근을 완료했어요 🌅\n"
                "매일의 출근이 당신의 루틴이 될 거예요.\n\n"
                "이제 다음 단계로 넘어가볼까요?"
            ),
            color=0xFFD166
        )
        await ch.send(embed=embed)

        await asyncio.sleep(STEP_DELAY)
        await send_ot_step(ch, user, 2)
        user_ot_progress[user.id] = 2

    # Step 3: !보고서 (출근기록 채널)
    elif step == 3 and message.content.strip().startswith("!보고서") and message.channel.id == CHANNEL_CHECKIN_ID:
        ch_id = next((cid for cid, uid in channel_owner.items() if uid == user.id), None)
        if not ch_id:
            return
        ch = bot.get_channel(ch_id)

        await asyncio.sleep(10)  # 트리거 후 10초 텀
        await ch.send(f"{user.mention} ✅ 보고서 확인 완료!")
        await send_space(ch)
        embed = discord.Embed(
            title="📊 보고서 확인 완료!",
            description=(
                f"{channel_mention(CHANNEL_CHECKIN_ID)} 채널에서 보고서를 확인했어요!\n"
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

# --- 개인 OT 채널 생성 ---
async def create_private_ot_channel(guild: discord.Guild, member: discord.Member):
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
        description="안녕하세요! 인사팀입니다 💼\n\n지금부터 천천히 **신입 OT를 진행하겠습니다.**",
        color=0x00B2FF
    )
    await channel.send(
        f"{member.mention} 👋 반가워요!\n이곳은 **인사팀과 함께 진행하는 신입 OT 공간**이에요 🎨"
    )
    await send_space(channel)
    await channel.send(embed=embed, view=StartView())
    return channel

# --- 시작 버튼(View) ---
class StartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="OT 시작하기", style=discord.ButtonStyle.green, custom_id="start_ot")
    async def start_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        user = interaction.user
        user_ot_progress[user.id] = 1
        await send_ot_step(interaction.channel, user, 1)

# --- 역할 부여 시 자동 OT 채널 생성 ---
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    new_roles = [r for r in after.roles if r not in before.roles]
    if any(r.id == TARGET_ROLE_ID for r in new_roles):
        if after.id in sent_users:
            return
        sent_users.add(after.id)
        await create_private_ot_channel(after.guild, after)
        print(f"✅ OT 채널 생성 → {after.display_name}")

# --- 실행 ---
@bot.event
async def on_ready():
    keep_alive()
    bot.add_view(StartView())  # Persistent View
    print(f"✅ 로그인 완료: {bot.user} (인사팀 OT 봇)")

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("⚠️ DISCORD_BOT_TOKEN 미설정")


