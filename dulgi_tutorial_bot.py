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
intents.guilds = True
intents.members = True
intents.messages = True        # ← 추가
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)



# === 설정값 ===
FORUM_CHANNEL_ID     = 1423360385225851011
START_ROLE_ID        = 1427654027600203886   # 🟢 튜토리얼 시작 역할 (새로 추가)
COMPLETE_ROLE_ID     = 1426578319410728980   # 🏁 튜토리얼 완료 역할 (새로 추가)
CHANNEL_CHECKIN_ID   = 1423359791287242782
CHANNEL_DAILY_ID     = 1423170386811682908
CHANNEL_QNA_ID       = 1424270317777326250
STEP_DELAY = 10
STEP2_DELAY = 25
DELETE_DELAY = 86400 

user_ot_progress = {}
recent_threads = set()
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
            "**아래 메시지를 출근 기록채널에서 입력해보세요!**\n\n"
            "✳️ **명령어 입력 방법**\n"
            "느낌표 + `출근`\n예: `!출근`\n"
            "━━━━━━━━━━━━━━━━━━━"
        )},
    2: {"title": "🎨 **Step 2 : 일일 그림보고**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            "**오늘 하루 그림 공부&작업한 것을 올려보아요✏️**\n\n"
            "우선 선배들이 어떻게 하는지 구경하러 가볼까요? 👀\n"
            "━━━━━━━━━━━━━━━━━━━"
        )},
    3: {"title": "📊 **Step 3 : 하루 성과 확인하기**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            f"이제 {channel_mention(CHANNEL_CHECKIN_ID)} 채널로 이동 후 명령어를 입력해보세요! 🌱\n/n"
            "✳️ **명령어 입력 방법**\n"
            "느낌표 + `보고서`\n예: `!보고서`\n\n"
            "━━━━━━━━━━━━━━━━━━━"
        )},
    4: {"title": "🗂️ **Step 4 : 주간 그림보고 만들기**",
        "desc": (
            "━━━━━━━━━━━━━━━━━━━\n"
            "한 주에 한번 스스로 피드백 해보는 시간을 가져보아요!\n"
            "아래 버튼을 눌러 가이드를 확인해보세요\n"
            "━━━━━━━━━━━━━━━━━━━\n"
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
    await ch.send(f"{user.mention}")

    embed = discord.Embed(
        title="🎉 일일 그림보고 탐방완료!",
        description=(
            "앞으로 자신의 그림 성장과정을 매일 공유해보세요🎨\n"
            "🖼️ 낙서, 크로키, 모작, 그림 연구 등 모두 좋아요!\n"
            "\n\n"
            "✨**이미지와 함께 올려주셔야 하루 성과가 인정됩니다**✨"
        ),
        color=0xFFD166
    )
    await asyncio.sleep(3)
    await ch.send(embed=embed)
    embed_tip = discord.Embed(
        title="📌주의사항📌",
        description=(
            "이미지를 꼭 같이 첨부하셔야 성과로 인정됩니다!"
        ),
        color=0xFFD166
    )
    await ch.send(embed=embed_tip)

    
    await send_space(ch, 2)
    await asyncio.sleep(STEP_DELAY)
    await send_ot_step(ch, user, 3)
    user_ot_progress[user.id] = 3

# === Step4 포럼 버튼 (간략화 버전, 수정됨) ===
class Step4Button(discord.ui.Button):
    def __init__(self, user):
        super().__init__(label="📑 주간 그림보고 가이드", style=discord.ButtonStyle.success)
        self.user = user
        self.clicked = False

    async def callback(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("본인 진행용 버튼이에요 🙏", ephemeral=True)
            return
        if self.clicked:
            await interaction.response.send_message("이미 확인하셨어요 ✅", ephemeral=True)
            return

        self.clicked = True
        await interaction.response.defer()
        self.disabled = True
        await interaction.message.edit(view=self.view)

        ch_id = next((cid for cid, uid in channel_owner.items() if uid == self.user.id), None)
        if not ch_id:
            return
        ch = bot.get_channel(ch_id)
        user = self.user

        # ① Step4 안내 메시지
        embed = discord.Embed(
            title="🗂️ STEP 4 : 주간 그림보고 가이드",
            description=(
                f"{user.mention}\n"
                "```\n"
                f"# 📔 방법\n"
                f"1. {channel_mention(FORUM_CHANNEL_ID)}에서 '새 포스트' 생성 클릭!\n\n"
                "2. 자신의 닉네임을 제목으로, 원하는 프로필 이미지를 첨부해서 포스트를 만들어주세요\n\n"
                "3. 아래 양식을 바탕으로 한 주에 최소 한 번씩 작업일지 작성\n\n"
                "*프로필 이미지는 차후 변경이 어려우니 자신을 대표할만한 그림을 올려보아요! 🥰\n\n"
                "```\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "```\n"
                "# ✏️ 작성 양식 예시\n"
                "[한 주간 진행한 것들]\n\n"
                "[잘한 점] (최소 3가지 이상)\n"
                "1.\n2.\n3.\n\n"
                "[개선해야 할 점] (최소 3가지 이상)\n"
                "1.\n2.\n3.\n\n"
                "[개선 방법]\n- \n- "
                "```"
            ),
            color=0x43B581
        )
        await ch.send(embed=embed)


        # ② 20초 후: 주간 보고서 이동 버튼
        await asyncio.sleep(20)
        view_report = discord.ui.View()
        view_report.add_item(discord.ui.Button(
            label="🗂️ 나만의 주간그림보고서 만들어보기",
            style=discord.ButtonStyle.success,
            url=f"https://discord.com/channels/{ch.guild.id}/1423360385225851011"
        ))
        await ch.send(f"{user.mention} 이제 주간보고서를 만들어볼까요? ✨", view=view_report)

        # ③ 30초 후: 확인 및 가이드 재보기 버튼
        await asyncio.sleep(40)
        view_guide = discord.ui.View()
        view_guide.add_item(discord.ui.Button(
            label="📘 주간보고 가이드 보러가기",
            style=discord.ButtonStyle.primary,  # 파랑 or 눈에 띄는 색
            url=f"https://discord.com/channels/{ch.guild.id}/1426954981638013049"
        ))
        await ch.send(
            f"{user.mention} 잘 만들어 봤나요? 🎨\n"
            "혹시 아직이라면 꼭 만들어서 한 주에 한 번씩은 작성해보세요!\n"
            "가이드를 다시 보고 싶다면 아래 버튼을 눌러주세요 👇",
            view=view_guide
        )

                # ④ 5초 후: 마무리 및 OT 종료 버튼
        await asyncio.sleep(5)

     # ✅ 튜토리얼 완료 시 역할 교체 (완료 부여 + 시작 제거)
        member = ch.guild.get_member(user.id)
        if not member:
            member = await ch.guild.fetch_member(user.id)

        role_start = ch.guild.get_role(START_ROLE_ID)
        role_complete = ch.guild.get_role(COMPLETE_ROLE_ID)
        try:
            if role_complete and role_complete not in member.roles:
                await member.add_roles(role_complete, reason="튜토리얼 완료")
                print(f"🎓 {member.display_name} → 튜토리얼 완료 역할 부여")

            if role_start and role_start in member.roles:
                await member.remove_roles(role_start, reason="튜토리얼 완료 후 시작 역할 제거")
                print(f"🧹 {member.display_name} → 튜토리얼 시작 역할 제거")
        except Exception as e:
            print(f"⚠️ 역할 교체 실패: {e}")


        # 🎯 마지막 안내 임베드 + 버튼
        view_end = discord.ui.View()
        view_end.add_item(discord.ui.Button(
            label="🎯 신입 OT 끝!",
            style=discord.ButtonStyle.blurple,
            url=f"https://discord.com/channels/{ch.guild.id}/1423174036917325916"
        ))

        embed_end = discord.Embed(
            title="🏁 신입 OT 완료!",
            description=(
                "매달 **우수사원**을 선정하고 있어요! ✨\n"
                "꾸준히 참여하신다면 분명 이름이 올라갈 거예요 🏆\n\n"
                f"궁금한 점은 언제든 <#{CHANNEL_QNA_ID}> 채널로 문의해주세요 📩\n"
                "이제 모든 OT가 완료되었습니다. 수고하셨습니다 🎉"
            ),
            color=0x5865F2
        )
        embed_end.set_footer(text="그림친구 1팀 • 튜토리얼 완료")

        await ch.send(content=f"{user.mention}", embed=embed_end, view=view_end)


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
        await ch.send(f"{user.mention}")
        embed = discord.Embed(
            title="🎉 출근 완료!",
            description=(f"앞으로도 {channel_mention(CHANNEL_CHECKIN_ID)} 채널에서 매일 출근해보세요\n\n"
                         "매일 출근하면서 같이 열심히 성장해봐요!\n"),
            color=0xFFD166)
        await ch.send(embed=embed)
        await send_space(ch, 2)
        await asyncio.sleep(5)
        await send_ot_step(ch, user, 2)
        user_ot_progress[user.id] = 2

    elif step == 3 and msg.content.startswith("!보고서") and msg.channel.id == CHANNEL_CHECKIN_ID:
        ch = bot.get_channel(next((cid for cid, uid in channel_owner.items() if uid == user.id), None))
        if not ch: return
        await asyncio.sleep(10)
        await ch.send(f"{user.mention}")
        embed = discord.Embed(
            title="📊 보고서 확인 완료!",
            description=(f"{channel_mention(CHANNEL_CHECKIN_ID)} 채널에서 하루의 성과를 확인할 수 있어요!\n\n"
                         "🌱초록색칸이 채워지는 만큼 여러분의 실력도 성장할거에요!🌱"),
            color=0xFFD166)
        await ch.send(embed=embed)
        await send_space(ch, 2)
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
                          description="안녕하세요! 인사팀입니다 💼\n\n지금부터 차근차근 어떻게 활동하는지 체험해보는 시간을 가져봐요!😍",
                          color=0x00B2FF)
    await ch.send(f"{member.mention} 👋 반가워요!\n이곳은 커뮤니티 튜토리얼 공간입니다!")
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

        await send_space(itx.channel, 2)

        await send_ot_step(itx.channel, user, 1)


# === 역할 부여 감지 (튜토리얼 시작용) ===
@bot.event
async def on_member_update(before, after):
    # 이미 튜토리얼 완료 역할이 있다면 아무 것도 안 함
    if any(r.id == COMPLETE_ROLE_ID for r in after.roles):
        return

    # 새로 붙은 역할만 계산
    new_roles = [r for r in after.roles if r not in before.roles]

    # 🟢 시작 역할이 '새로' 붙었을 때만 OT 생성
    if any(r.id == START_ROLE_ID for r in new_roles):
        if after.id in sent_users:
            return
        sent_users.add(after.id)
        await create_private_ot_channel(after.guild, after)
        print(f"✅ OT 채널 생성 → {after.display_name} (시작 역할 감지)")





# === 실행 ===
@bot.event
async def on_ready():
    keep_alive()
    bot.add_view(StartView())
    print(f"✅ 로그인 완료: {bot.user} (인사팀 OT 봇)")

if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    bot.run(TOKEN)


# === 포럼 게시글(스레드) 생성 감지 ===
@bot.event
async def on_thread_create(thread: discord.Thread):
    try:
        # 중복 생성 방지
        if thread.id in recent_threads:
            return
        recent_threads.add(thread.id)

        # 1️⃣ 대상 포럼만 감지
        if thread.parent_id != FORUM_CHANNEL_ID:
            return

        # 2️⃣ 생성자 찾기
        creator = None

        # 빠른 경로 (디스코드에서 owner가 바로 제공될 경우)
        if getattr(thread, "owner", None):
            creator = thread.owner

        # owner가 없으면 owner_id 기반으로 탐색
        if not creator and getattr(thread, "owner_id", None):
            creator = thread.guild.get_member(thread.owner_id)
            if not creator:
                try:
                    creator = await thread.guild.fetch_member(thread.owner_id)
                except Exception:
                    pass

        # 그래도 없으면 첫 메시지 작성자로 대체
        if not creator:
            try:
                await asyncio.sleep(1.0)
                starter_msg = await thread.fetch_message(thread.id)
                creator = starter_msg.author
            except Exception:
                pass

        if not creator:
            return  # 생성자 못 찾으면 종료

        # 3️⃣ Step4 진행자만 트리거
        if user_ot_progress.get(creator.id) != 4:
            return

        # 4️⃣ 개인 OT 채널 찾기
        ch_id = next((cid for cid, uid in channel_owner.items() if uid == creator.id), None)
        if not ch_id:
            return
        ch = bot.get_channel(ch_id)
        if not ch:
            return

        # 5️⃣ 5초 후 메시지 전송
        await asyncio.sleep(5)

        embed = discord.Embed(
            title="🎉 주간 그림보고 생성 완료!",
            description=(
                f"{creator.mention}, 정말 잘 하셨어요! 🥳\n\n"
                "이제 당신의 주간 피드백 공간이 만들어졌어요.\n"
                "매주 한 번씩 성장의 발자취를 남겨보세요 🌱"
            ),
            color=0x43B581
        )
        await ch.send(embed=embed)

        # 이후 추가 멘트 (예: OT 종료)
        await asyncio.sleep(5)
        embed_done = discord.Embed(
            title="🏁 신입 OT 완료!",
            description=(
                "이제 당신은 모든 준비를 마쳤어요! 🎨\n\n"
                f"궁금한 점은 언제든 {channel_mention(CHANNEL_QNA_ID)} 채널로 문의해주세요 📩\n\n"
                "이 채널은 **24시간 후 자동 삭제**됩니다 🕓"
            ),
            color=0x43B581
        )
        await ch.send(embed=embed_done)

        # 역할 교체 (완료 역할 부여 + 시작 역할 제거)
        role_start = ch.guild.get_role(START_ROLE_ID)
        role_complete = ch.guild.get_role(COMPLETE_ROLE_ID)
        try:
            if role_complete:
                await creator.add_roles(role_complete, reason="튜토리얼 완료 (포럼 생성 감지)")
                print(f"🎓 {creator.display_name} → 튜토리얼 완료 역할 부여")
            if role_start:
                await creator.remove_roles(role_start, reason="튜토리얼 시작 역할 제거")
                print(f"🧹 {creator.display_name} → 튜토리얼 시작 역할 제거")
        except Exception as e:
            print(f"⚠️ 역할 교체 실패: {e}")

    except Exception as e:
        print(f"⚠️ on_thread_create 처리 중 오류: {e}")
















