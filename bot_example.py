from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters, CallbackQueryHandler
from sqlalchemy import create_engine, Column, String, Enum, Integer, BigInteger, ForeignKey, DateTime, Boolean, Index
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, backref
from sqlalchemy.sql import func
from contextlib import contextmanager
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import random
from datetime import datetime, timedelta

# Setup the bot
bot = Bot(token='6628775621:AAEqxpdHCyA871lzElVaRh99l9ksDi4UXnY') # Test Bot
# bot = Bot(token='6524274145:AAF80QHBzEmbyC8GLVNw7N-iH383yAyBmBU') # Production
# group_chat_id = '-4076578089' # Test Group
group_chat_id = '-1001903580245' # Production

# Setup scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup with SQLAlchemy
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=True, unique=True)
    name = Column(String(255), nullable=True)
    status = Column(Enum('VIP', 'Regular'), default='Regular')
    username = Column(String(255), unique=True)
    wallet_address = Column(String(255), nullable=True)

    __table_args__ = (Index('idx_username','username'),)

class Lottery(Base):
    __tablename__ = 'lotteries'

    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime, default=func.now())
    end_time = Column(DateTime)
    is_active = Column(Boolean, default=True)
    prize = Column(String(255))
    lottery_type = Column(Enum('VIP', 'Regular'))
    total_participants = Column(Integer)
    total_winners = Column(Integer)
    scheduled_end_time = Column(DateTime)

class Wish(Base):
    __tablename__ = 'wishes'

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'))
    wish = Column(String(255))
    total_invitees = Column(Integer)
    timestamp = Column(DateTime, default=func.now())

class Participation(Base):
    __tablename__ = 'participations'

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'))  
    lottery_id = Column(Integer, ForeignKey('lotteries.id'))
    timestamp = Column(DateTime, default=func.now())

class LotteryWinner(Base):
    __tablename__ = 'lottery_winners'

    id = Column(Integer, primary_key=True)
    lottery_id = Column(Integer, ForeignKey('lotteries.id'))
    user_id = Column(BigInteger, ForeignKey('users.user_id'))

class InviteLink(Base):
    __tablename__ = 'invite_links'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)
    link = Column(String(512), nullable=False)
    generated_at = Column(DateTime, default=func.now())

    user = relationship("User", backref=backref("invite_links", cascade="all, delete-orphan"))

DATABASE_URL = "mysql+mysqlconnector://root:Welcome123!@sheep-db.cikwkllp1puj.ap-east-1.rds.amazonaws.com/vipbot"
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

# Admins list
admins = [6029674440, 5871404627]  
# admins = [5871404627] 

@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Database helper functions
def add_user_to_db(user_id=None, name=None, status="Regular", username=None):
    with session_scope() as session:
        user = None
        if user_id:
            user = session.query(User).filter_by(user_id=user_id).first()

        if user:
            user.status = status
            if name:
                user.name = name
            if user_id:
                user.user_id = user_id
        else:
            user = User(user_id=user_id, name=name, status=status, username=username)
            session.add(user)

def update_user_to_db(user_id=None, name=None, username=None):
    with session_scope() as session:
        user = None
        if username:
            user = session.query(User).filter_by(username=username).first()

        if user:
            user.name = name
            user.user_id = user_id

def get_user_status(user_id=None, username=None):
    with session_scope() as session:
        user = None
        if user_id:
            user = session.query(User).filter_by(user_id=user_id).first()
        elif username:
            user = session.query(User).filter_by(username=username).first()
        if user:
            # Convert "Regular" to "普通用戸"
            return "普通用戸" if user.status == "Regular" else user.status
        return None

def set_user_status(user_id, status):
    with session_scope() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        if user:
            user.status = status

def get_user_keyboard():
    keyboard = [
        [KeyboardButton("获取VIP"), KeyboardButton("个人中心")],
        [KeyboardButton("如何成为VIP"), KeyboardButton("抽奖")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("（仅管理员）开始抽奖", callback_data='start_lottery')],
        [InlineKeyboardButton("（仅管理员）增加VIP", callback_data='add_vip')],
        [InlineKeyboardButton("（仅管理员）移除VIP", callback_data='remove_vip')],
        [InlineKeyboardButton("（仅管理员）列出所有VIP", callback_data='lsvips')],
        [InlineKeyboardButton("（仅管理员）列出所有普通用户", callback_data='lsregular')],
        [InlineKeyboardButton("（仅管理员）列出所有用户", callback_data='lsallusers')],
    ]
    return InlineKeyboardMarkup(keyboard)

def start(update: Update, context: CallbackContext) -> None:    
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    username = update.effective_user.username

    with session_scope() as session:
        # Check if the user exists in the database
        existing_user = session.query(User).filter_by(user_id=user_id).first()
        existing_username = session.query(User).filter_by(username=username).first()
        if existing_user:
            # Update the user's details without changing their status
            add_user_to_db(user_id=user_id, name=user_name, username=username, status=existing_user.status)
        elif existing_username:
            update_user_to_db(user_id=user_id, name=user_name, username=username)
        else:
            # Add the user with the default "Regular" status
            add_user_to_db(user_id=user_id, name=user_name, username=username)

    if user_id in admins:
        admin_keyboard = get_admin_keyboard()
        user_keyboard = get_user_keyboard()
        update.message.reply_text('欢迎管理员!', reply_markup=admin_keyboard)
        update.message.reply_text('以下是用户功能', reply_markup=user_keyboard)
    else:
        keyboard = get_user_keyboard()
        update.message.reply_text('欢迎使用!', reply_markup=keyboard)

def handle_text(update: Update, context: CallbackContext) -> None:
    text = update.message.text
    if text == "获取VIP":
        claim(update, context)
        pass
    elif text == "个人中心":
        status(update, context)
    elif text == "如何成为VIP":
        become_vip(update, context)
        pass
    elif text == "抽奖":
        participate_lottery(update, context)
    else:
        update.message.reply_text('不接受调戏喔！')

def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    if query.data == 'start_lottery':
        instruction_text = "管理员: 开始一个新的抽奖. 使用方法: /startlottery <奖品> <参与人数> <中奖人数> <类型(VIP/普通)> 可选: 倒计时(如: 10s, 5m, 2h, 1d)"
        context.bot.send_message(chat_id=query.message.chat_id, text=instruction_text)
        pass
    elif query.data == 'add_vip':
        instruction_text = "管理员: 添加一个新的VIP用户. 使用方法: /addvip <@username>"
        context.bot.send_message(chat_id=query.message.chat_id, text=instruction_text)
        pass
    elif query.data == 'remove_vip':
        instruction_text = "管理员: 删除一个VIP用户. 使用方法: /rmvip <@username>"
        context.bot.send_message(chat_id=query.message.chat_id, text=instruction_text)
        pass
    elif query.data == 'lsvips':
        list_vips(update, context)
        pass
    elif query.data == 'lsregular':
        list_regulars(update, context)
        pass                       
    elif query.data == 'lsallusers':
        list_all_users(update, context)
        pass 

def generate_invite_link():
    new_link = bot.create_chat_invite_link(chat_id=group_chat_id, member_limit=1)
    return new_link.invite_link

def save_invite_link_to_db(session, user_id, invite_link):
    link_entry = InviteLink(user_id=user_id, link=invite_link)
    session.add(link_entry)

def claim(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    with session_scope() as session:
        if get_user_status(user_id) == "VIP":
            exist_invite_link = session.query(InviteLink).filter_by(user_id=user_id).first()
            if exist_invite_link:
                time = exist_invite_link.generated_at.strftime('%Y年%m月%d日') 
                message = f"""
    你已经在{time}获取过内部群门票
    如未能进入请联系人工客服再次获取 @ksdb588
                """
                context.bot.send_message(chat_id=user_id, text=message) 
            else:
                try:
                    invite_link = generate_invite_link()
                    save_invite_link_to_db(session, user_id, invite_link)
                    message = "您在本次开放的vip用户名单内，已为您升级至vip用户，开放vip权益并开放内部群门票，请加入内部群以得到vip权益的延续"
                    keyboard = [[InlineKeyboardButton("点我加入内部群", url=invite_link)]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    context.bot.send_message(chat_id=user_id, text=message, reply_markup=reply_markup)
                except Exception as e:
                    if 'Not enough rights to manage chat invite link' in str(e):
                        for admin in admins:
                            context.bot.send_message(chat_id=admin, text="VIP用户无法获取群组链结！！！\n机器人没有足够的群组权限！请先把机器人设置为群组机器人然后再使用此功能！")
                        return None
                    elif 'Chat not found' in str(e):
                        for admin in admins:
                            context.bot.send_message(chat_id=admin, text="VIP用户无法获取群组链结！！！\n机器人还没有加入群组或群组不存在！")
                    else:
                        raise e
        else:
            message = '很抱歉您不在本次开放的VIP名单内，您可以点击【如何成为VIP】查看VIP获取途径，快手担保官方也会不定时免费发放VIP名额'
            context.bot.send_message(chat_id=user_id, text=message)       

def status(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    user_name = update._effective_user.full_name
    user_status = get_user_status(user_id)
    message = f"""
用户ID： {user_id}
用户名称： {user_name}
用户等级： {user_status}
"""
    context.bot.send_message(chat_id=user_id, text=message)

def become_vip(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    message = """
成为VIP的四种途径：
1.供需机器人一次性充值200u
2.累计发布10次广告
3.上押公群
4.快手担保官方不定时评估优质老板为其发放vip
"""
    context.bot.send_message(chat_id=user_id, text=message)    

def add_vip(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id not in admins:
        update.message.reply_text('您没有权限执行此操作.')
        return

    if not context.args:
        update.message.reply_text('请提供要添加的VIP用户的用户名.')
        return

    success_usernames = []
    failed_usernames = []
    already_vip_usernames = []

    for username in context.args:
        username = username.lstrip('@')
        if get_user_status(username=username) == "VIP":
            already_vip_usernames.append(username)
            continue
        try:         
            add_user_to_db(status="VIP", username=username)
            success_usernames.append(username)
        except Exception as e:
            logger.error(e)
            failed_usernames.append(username)

    message = ""
    if success_usernames:
        message += f"以下用户已添加到VIP名单:\n{' '.join(['@' + u for u in success_usernames])}\n"
    if already_vip_usernames:
        message += f"以下用户已經是VIP:\n{' '.join(['@' + u for u in already_vip_usernames])}\n"        
    if failed_usernames:
        message += f"以下用户未能添加到VIP名单:\n{' '.join(['@' + u for u in failed_usernames])}"

    update.message.reply_text(message)

def remove_vip(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id not in admins:
        update.message.reply_text('您没有权限执行此操作.')
        return

    if not context.args:
        update.message.reply_text('请提供要删除的VIP用户的用户名.')
        return

    success_usernames = []
    failed_usernames = []
    not_vip_usernames = []

    for username in context.args:
        username = username.lstrip('@')
        status = get_user_status(username=username)
        if status == "VIP":
            add_user_to_db(status="Regular", username=username)
            success_usernames.append(username)
        elif status == "普通用戸":
            not_vip_usernames.append(username)
        else:
            failed_usernames.append(username)

    message = ""
    if success_usernames:
        message += f"以下用户已从VIP名单中删除:\n{' '.join(['@' + u for u in success_usernames])}\n"
    if not_vip_usernames:
        message += f"以下用户不是VIP:\n{' '.join(['@' + u for u in not_vip_usernames])}\n"
    if failed_usernames:
        message += f"以下用户未能从VIP名单中删除:\n{' '.join(['@' + u for u in failed_usernames])}"

    update.message.reply_text(message)

def list_vips(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    if user_id not in admins:
        message = '您没有权限执行此操作.'
        context.bot.send_message(chat_id=user_id, text=message)  
        return

    with session_scope() as session:
        vip_count = session.query(User).filter_by(status='VIP').count()
    message = f'当前VIP用户数量: {vip_count}'
    context.bot.send_message(chat_id=user_id, text=message)

def list_regulars(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    if user_id not in admins:
        message = '您没有权限执行此操作.'
        context.bot.send_message(chat_id=user_id, text=message)  
        return

    with session_scope() as session:
        regular_count = session.query(User).filter_by(status='Regular').count()
    message = f'当前普通用户数量: {regular_count}'
    context.bot.send_message(chat_id=user_id, text=message)

def list_all_users(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    if user_id not in admins:
        message = '您没有权限执行此操作.'
        context.bot.send_message(chat_id=user_id, text=message)  
        return

    with session_scope() as session:
        total_user_count = session.query(User).count()
    message = f'当前所有用户数量: {total_user_count}'
    context.bot.send_message(chat_id=user_id, text=message)

def start_lottery(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id not in admins:
        update.message.reply_text('您没有权限执行此操作.')
        return

    if len(context.args) < 4:
        update.message.reply_text('请提供所有参数: 奖品 参与人数 中奖人数 类型(VIP/普通). 可选: 倒计时(如: 10s, 5m, 2h, 1d). 例如: /startlottery iPhone 100 1 VIP 2h')
        return

    prize, total_participants, total_winners, lottery_type = context.args[:4]
    total_participants = int(total_participants)
    total_winners = int(total_winners)

    if lottery_type not in ['VIP', '普通']:
        update.message.reply_text('无效的抽奖类型. 请选择 VIP 或 普通.')
        return

    scheduled_end_time = None
    if len(context.args) > 4:
        countdown = context.args[4]
        # Convert countdown to timedelta
        last_char = countdown[-1]
        if last_char == 's':
            delta = timedelta(seconds=int(countdown[:-1]))
        elif last_char == 'm':
            delta = timedelta(minutes=int(countdown[:-1]))
        elif last_char == 'h':
            delta = timedelta(hours=int(countdown[:-1]))
        elif last_char == 'd':
            delta = timedelta(days=int(countdown[:-1]))
        else:
            update.message.reply_text('无效的倒计时格式. 请使用 s (秒), m (分钟), h (小时), or d (天).')
            return

        scheduled_end_time = datetime.now() + delta

    with session_scope() as session:
        new_lottery = Lottery(prize=prize, total_participants=total_participants, total_winners=total_winners, lottery_type=lottery_type, scheduled_end_time=scheduled_end_time)
        session.add(new_lottery)
        session.commit()

        if scheduled_end_time:
            scheduler.add_job(stop_and_announce_lottery, 'date', run_date=scheduled_end_time, args=[new_lottery, context.bot])

        if lottery_type == 'VIP':
            announcement = f"""
🎁抽奖开始
🎁奖品：{prize}

💵参与人数：{total_participants}
💵中奖人数：{total_winners}

本次抽奖为VIP抽奖，仅限VIP用户参与
VIP用户请点击【抽奖】参与
"""
        else:
            announcement = f"""
🎁抽奖开始
🎁奖品：{prize}

💵参与人数：{total_participants}
💵中奖人数：{total_winners}

本次抽奖为普通抽奖，所有用户均可参与
请点击【抽奖】参与
"""

        for user in session.query(User).all():
            context.bot.send_message(chat_id=user.user_id, text=announcement)

def participate_lottery(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id

    with session_scope() as session:
        active_lottery = session.query(Lottery).filter_by(is_active=True).order_by(Lottery.start_time.desc()).first()

        if not active_lottery:
            message = '当前没有活动的抽奖。'
            context.bot.send_message(chat_id=user_id, text=message)
            return

        # Check if the user has already participated
        existing_participation = session.query(Participation).filter_by(user_id=user_id, lottery_id=active_lottery.id).first()
        if existing_participation:
            message = '您已参与此次抽奖。'
            context.bot.send_message(chat_id=user_id, text=message)
            return

        # Check if the lottery has reached its maximum participants
        current_participants = session.query(Participation).filter_by(lottery_id=active_lottery.id).count()
        if current_participants >= active_lottery.total_participants - 1:  # -1 because we'll add the current user after this check
            participation = Participation(user_id=user_id, lottery_id=active_lottery.id)
            session.add(participation)
            session.commit()
            stop_and_announce_lottery(active_lottery, context.bot)
            return

        # Check if the lottery has reached its scheduled end time
        if active_lottery.scheduled_end_time and datetime.now() >= active_lottery.scheduled_end_time:
            active_lottery.is_active = False
            session.commit()
            message = '抱歉，此次抽奖已结束。'
            context.bot.send_message(chat_id=user_id, text=message)           
            return

        participation = Participation(user_id=user_id, lottery_id=active_lottery.id)
        session.add(participation)
        session.commit()
        message = '您已参与抽奖!'
        context.bot.send_message(chat_id=user_id, text=message)

def stop_and_announce_lottery(lottery: Lottery, bot: Bot) -> None:
    with session_scope() as session:
        # Check if the lottery is already inactive
        if not lottery.is_active:
            return

        participants = session.query(Participation).filter_by(lottery_id=lottery.id).all()
        if not participants:
            for user in session.query(User).all():
                bot.send_message(chat_id=user.user_id, text="抽奖已结束，但没有用户参与此次抽奖。")
            return

        winners = random.sample(participants, min(len(participants), lottery.total_winners))
        winner_users = [session.query(User).filter_by(user_id=winner.user_id).first() for winner in winners]

        for winner in winners:
            lottery_winner = LotteryWinner(lottery_id=lottery.id, user_id=winner.user_id)
            session.add(lottery_winner)

        # Mark the lottery as ended
        lottery.is_active = False
        lottery.end_time = datetime.now()

        winner_announcements = []
        for winner in winners:
            winner_user = bot.get_chat(winner.user_id)
            if winner_user.username:
                winner_announcement = f"{winner_user.full_name} (http://t.me/{winner_user.username})"
            else:
                # If the user doesn't have a username, use their first name or user ID
                winner_announcement = f"{winner_user.full_name} (User ID: {winner_user.id})"
            winner_announcements.append(winner_announcement)

        # Format the overall announcement
        announcement = f"""
🎁抽奖结束
🎁奖品：{lottery.prize}

💵参与人数：{len(participants)}
💵中奖人数：{len(winner_users)}

🎉中奖名单：
{''.join(winner_announcements)}

🎉恭喜以上中奖用户，奖品将在24小时内发放
🎉您未中奖，再接再厉
"""
        # Announce the results
        for user in session.query(User).all():
            if user in winner_users:
                bot.send_message(chat_id=user.user_id, text=announcement.replace("🎉您未中奖，再接再厉", ""))
            else:
                bot.send_message(chat_id=user.user_id, text=announcement)

def main() -> None:
    # Create the Updater and pass it your bot's token.
    updater = Updater(bot=bot, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Register command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("addvip", add_vip, pass_args=True))
    dp.add_handler(CommandHandler('rmvip', remove_vip, pass_args=True))
    dp.add_handler(CommandHandler("startlottery", start_lottery, pass_args=True))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command & Filters.chat_type.private, handle_text))
    # Start the Bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
