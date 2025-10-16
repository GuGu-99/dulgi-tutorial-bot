# -*- coding: utf-8 -*-
# 🎓 그림친구 1팀 신입 OT (인사팀 완성버전)
# ✅ Step 간 10초 텀
# ✅ Step2 자동 트리거(25초) + 여백 메시지
# ✅ Step4 포럼 이미지 제거 + 1회 생성 제한 + 안내 메시지(7일 후 삭제)
# ✅ 20초 뒤 리마인드 + 튜토리얼 종료 안내 추가
# ✅ 모든 메시지 사이 시각적 여백 포함

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

# === 설정값 ===
FORUM_CHANNEL_ID     = 1423360385225851011
TARGET_ROLE_ID       = 1426578319410728980
CHANNEL_CHECKIN_ID   = 1423359791287242782
CHANNEL_DAILY_ID     = 1423170386811682908
CHANNEL_QNA_ID       = 1424270317777326250
STEP_DELAY = 10
STEP2_DELAY = 25
DELETE_DELAY = 86400  # 24시간 후 삭제

user_ot_progress = {}
sent_users = set()
channel_owner = {}

# === KeepAlive ===
app = Flask(__name__)
@app.route("/")
def home(): return "신입 OT 인사팀 봇 작동 중"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
def keep_alive(): Thread(target=run_flask, daemon=True).start()

# === 공용 함수 ===
async def send_space(ch: discord.TextChannel, delay: float = 0.5):
    await asyncio.sleep(delay)
    await ch.send("\u200b")

def channel_mention(cid: int) -> str:
    return f"<#{cid}>"

# === Step별 안내 문구 ===
OT_STEPS = {
    1: {"title": "🏢 **Step 1 : 출근하기**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            "**!출근 명령어를 아래 채널에서 입력해보세요!**\n\n"
            "✳️ **명령어 입력 방법**\n"
            "느낌표 + `출근`\n예: `!출근`\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "> 출근은 하루의 시작이자, 꿈을 향한 첫 걸음이에요 🌅"
        )},
    2: {"title": "🎨 **Step 2 : 일일 그림보고**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            "**오늘 하루 그림 공부를 어떤 형태로든 올려보세요! ✏️**\n\n"
            "지금은 부담 갖지 말고, 우선 선배들이 어떻게 올리고 있는지 구경하러 가볼까요? 👀\n"
            "━━━━━━━━━━━━━━━━━━━"
        )},
    3: {"title": "📊 **Step 3 : 보고서 확인하기**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            "**오늘 하루의 성과를 확인해볼까요?**\n\n"
            "✳️ **명령어 입력 방법**\n"
            "느낌표 + `보고서`\n예: `!보고서`\n\n"
            f"{channel_mention(CHANNEL_CHECKIN_ID)} 채널로 이동 후 명령어를 입력해보세요! 🌱\n"
            "━━━━━━━━━━━━━━━━━━━"
        )},
    4: {"title": "🗂️ **Step 4 : 주간 그림보고 (포럼 작성)**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            "**이제 한 주를 정리해볼 시간이에요 📅**\n\n"
            "‘#주간-그림보고’ 채널에 **본인 닉네임**으로 포럼을 만들어보세요!\n"
            "예: `[둘기] 10월 2주차 피드백 ✨`\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "> 완벽하지 않아도 괜찮아요, 기록이 곧 성장이에요 🌱"
        )}
}

# === Step2 자동 트리거 ===
async def trigger_step2_after_delay(user: discord.Member):
    await asyncio.sleep(STEP2_DELAY)
    ch_id = next((cid for cid, uid in channel_owner.items() if uid == user.id), None)
    if not ch_id: return
    ch = bot.get_channel(ch_id)
    if not ch: return

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

# === Step4 포럼 버튼 ===
class Step4Button(discord.ui.Button):
    def __init__(self, user):
        super().__init__(label="📑 주간 포럼으로 이동", style=discord.ButtonStyle.success)
        self.user = user
        self.clicked = False

    async def callback(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("본인 진행용 버튼이에요 🙏", ephemeral=True)
            return
        if self.clicked:
            await interaction.response.send_message("이미 포럼이 생성되었어요 ✅", ephemeral=True)
            return

        self.clicked = True
        await interaction.response.defer()
        self.disabled = True
        await interaction.message.edit(view=self.view)
        await asyncio.sleep(10)

        forum = bot.get_channel(FORUM_CHANNEL_ID)
        if not isinstance(forum, discord.ForumChannel):
            await interaction.followup.send("⚠️ 포럼 채널을 찾을 수 없어요.", ephemeral=True)
            return

        thread = await forum.create_thread(
            name=f"[{self.user.display_name}] 주간 피드백",
            content=f"{self.user.mention}님을 위한 주간 피드백 공간이에요 🎨"
        )

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

        async def delete_later():
            await asyncio.sleep(604800)
            try: await msg.delete()
            except: pass
        asyncio.create_task(delete_later())

        # --- 20초 뒤 개인 OT 채널 안내 + 종료 멘트 ---
        async def followup_back_to_private():
            await asyncio.sleep(20)
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

            # ✅ 튜토리얼(신입 OT) 종료 멘트 추가
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

        asyncio.create_task(followup_back_to_private())

# === Step 전송 ===
async def send_ot_step(channel, user, step):
    info = OT_STEPS[step]
    embed = discord.Embed(title=info["title"], description=info["desc"], color=0x00C9A7)
    embed.set_footer(text=f"그림친구 1팀 신입 OT • Step {step}/4")
    view = discord.ui.View()

    if step == 1:
        view.add_item(discord.ui.Button(label="🫡 출근기록으로 이동", style=discord.ButtonStyle.success,
                                        url=f"https://discord.com/channels/{channel.guild.id}/{CHANNEL_CHECKIN_ID}"))
    elif step == 2:
        view.add_item(discord.ui.Button(label="🎨 그림보고 구경하러 가기", style=discord.ButtonStyle.success,
                                        url=f"https://discord.com/channels/{channel.guild.id}/{CHANNEL_DAILY_ID}"))
        asyncio.create_task(trigger_step2_after_delay(user))
    elif step == 3:
        view.add_item(discord.ui.Button(label="📊 출근기록으로 이동", style=discord.ButtonStyle.success,
                                        url=f"https://discord.com/channels/{channel.guild.id}/{CHANNEL_CHECKIN_ID}"))
    elif step == 4:
        view.add_item(Step4Button(user))
    await channel.send(embed=embed, view=view)

# === 메시지 트리거 ===
@bot.event
async def on_message(msg):
    if msg.author.bot: return
    user = msg.author
    step = user_ot_progress.get(user.id)
    if not step: return

    if step == 1 and msg.content.startswith("!출근") and msg.channel.id == CHANNEL_CHECKIN_ID:
        ch = bot.get_channel(next((cid for cid, uid in channel_owner.items() if uid == user.id), None))
        if not ch: return
        await asyncio.sleep(10)
        await ch.send(f"{user.mention} ✅ 출근 완료!")
        await send_space(ch)
        embed = discord.Embed(
            title="🎉 출근 완료!",
            description=(f"{channel_mention(CHANNEL_CHECKIN_ID)} 채널에서 출근을 완료했어요 🌅\n"
                         "매일의 출근이 당신의 루틴이 될 거예요.\n\n"
                         "이제 다음 단계로 넘어가볼까요?"),
            color=0xFFD166)
        await ch.send(embed=embed)
        await asyncio.sleep(STEP_DELAY)
        await send_ot_step(ch, user, 2)
        user_ot_progress[user.id] = 2

    elif step == 3 and msg.content.startswith("!보고서") and msg.channel.id == CHANNEL_CHECKIN_ID:
        ch = bot.get_channel(next((cid for cid, uid in channel_owner.items() if uid == user.id), None))
        if not ch: return
        await asyncio.sleep(10)
        await ch.send(f"{user.mention} ✅ 보고서 확인 완료!")
        await send_space(ch)
        embed = discord.Embed(
            title="📊 보고서 확인 완료!",
            description=(f"{channel_mention(CHANNEL_CHECKIN_ID)} 채널에서 보고서를 확인했어요!\n"
                         "앞으로도 이곳에서 하루의 성과를 꾸준히 체크해봐요 🌱\n\n"
                         "이제 마지막 단계로 넘어가볼까요?"),
            color=0x43B581)
        await ch.send(embed=embed)
        await asyncio.sleep(STEP_DELAY)
        await send_ot_step(ch, user, 4)
        user_ot_progress[user.id] = 4

    await bot.process_commands(msg)

# === 개인 OT 채널 생성 ===
async def create_private_ot_channel(guild, member):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    ch = await guild.create_text_channel(f"{member.display_name}-입사도우미", overwrites=overwrites)
    channel_owner[ch.id] = member.id

    embed = discord.Embed(title="🎓 그림친구 1팀 신입 OT 안내",
                          description="안녕하세요! 인사팀입니다 💼\n\n지금부터 천천히 **신입 OT를 진행하겠습니다.**",
                          color=0x00B2FF)
    await ch.send(f"{member.mention} 👋 반가워요!\n이곳은 **인사팀과 함께 진행하는 신입 OT 공간**이에요 🎨")
    await send_space(ch)
    await ch.send(embed=embed, view=StartView())
    return ch

# === 시작 버튼 ===
class StartView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="OT 시작하기", style=discord.ButtonStyle.green)
    async def start(self, btn, itx):
        await itx.response.defer()
        user = itx.user
        user_ot_progress[user.id] = 1
        await send_ot_step(itx.channel, user, 1)

# === 역할 부여 감지 ===
@bot.event
async def on_member_update(before, after):
    new_roles = [r for r in after.roles if r not in before.roles]
    if any(r.id == TARGET_ROLE_ID for r in new_roles):
        if after.id in sent_users: return
        sent_users.add(after.id)
        await create_private_ot_channel(after.guild, after)
        print(f"✅ OT 채널 생성 → {after.display_name}")

# === 실행 ===
@bot.event
async def on_ready():
    keep_alive()
    bot.add_view(StartView())
    print(f"✅ 로그인 완료: {bot.user} (인사팀 OT 봇)")

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    bot.run(TOKEN)
