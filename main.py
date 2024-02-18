from telegram import Bot, Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler
from telegram.error import BadRequest
from sqlalchemy import create_engine, Column, String, Enum, Integer, BigInteger, ForeignKey, DateTime, Boolean, Index
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, backref
from sqlalchemy.sql import func
from contextlib import contextmanager
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import random
import string
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Setup the bot
bot = Bot(token=os.getenv('BOT_TOKEN'))
group_info = bot.getChat(chat_id=os.getenv('ADMIN_GROUP_ID'))
channel_info = bot.getChat(chat_id=os.getenv('CHANNEL_NAME'))

# Setup scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup with SQLAlchemy
Base = declarative_base()

# Models

class User(Base):
    __tablename__ = 'users'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=True, unique=True)
    name = Column(String(255), nullable=True)
    status = Column(Enum('VIP', 'Regular'), default='Regular')
    wish = Column(String(255), nullable=True)
    wish_date = Column(DateTime, nullable=True)
    wish_claimed = Column(Boolean, default=False)
    invitees_count = Column(Integer, default=0)
    username = Column(String(255), unique=True)
    wallet_address = Column(String(255), nullable=True)
    is_subscribed = Column(Boolean, default=False)
    message_id = Column(BigInteger, nullable=True)

    __table_args__ = (Index('idx_username','username'),)

class Invite(Base):
    __tablename__ = 'invites'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'))
    invitee_id = Column(BigInteger, ForeignKey('users.user_id'))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship('User', foreign_keys=[user_id], backref=backref('invites', uselist=True))
    invitee = relationship('User', foreign_keys=[invitee_id], backref=backref('invited_by', uselist=True))

DATABASE_URL = f"mysql+mysqlconnector://{os.getenv('MYSQL_USERNAME')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}/{os.getenv('MYSQL_DATABASE')}?charset=utf8mb4"
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

# Admins list
admins = [int(admin_id) for admin_id in os.getenv('ADMIN_IDS').split(',')]

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
def add_user_to_db(user_id=None, name=None, status="Regular", username=None, is_subscribed=False):
    with session_scope() as session:
        user = None
        if user_id:
            user = session.query(User).filter_by(user_id=user_id).first()

        if user:
            user.status = status
            user.is_subscribed = is_subscribed
            if name:
                user.name = name
            if user_id:
                user.user_id = user_id
        else:
            user = User(user_id=user_id, name=name, status=status, username=username, is_subscribed=is_subscribed)
            session.add(user)

def update_user_to_db(user_id=None, name=None, username=None, is_subscribed=False):
    with session_scope() as session:
        user = None
        if username:
            user = session.query(User).filter_by(username=username).first()

        if user:
            user.name = name
            user.user_id = user_id
            user.is_subscribed = is_subscribed

def get_keyboard(admin=False):
    keyboard = [
        [KeyboardButton("🏮写下愿望"), KeyboardButton("🧧绑定钱包"), KeyboardButton("🥣我的邀请")],
    ]
    if admin:
        keyboard.append([KeyboardButton("🌟实现愿望")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

def generate_unique_link(user_id: int) -> str:
    """Generate a unique link for each user based on their user_id"""
    unique_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    bot_username = bot.getMe().username
    return f'https://t.me/{bot_username}?start={user_id}_{unique_str}'

def subscribe_channel_message(start_message: bool = False):    
    message = f"请先加入👉{channel_info.title}频道👈"
    if start_message:
        message = f"📣恭喜，您的帐号创建成功！\n\n" + message
    keyboard = [
        [InlineKeyboardButton(f"{channel_info.title}", url=f"{channel_info.invite_link}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return message, reply_markup

def bind_wallet_address(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    is_subscribed = is_user_subscribed(user_id)
    if is_subscribed:
        update.message.reply_text('请写下你的钱包地址\n使用/cancel取消')
        return WALLET
    else:
        message, reply_markup = subscribe_channel_message()
        update.message.reply_text(message, reply_markup=reply_markup)
        return ConversationHandler.END

def receive_wallet_address(update: Update, context: CallbackContext) -> int:
    wallet_address = update.message.text
    user_id = update.effective_user.id

    with session_scope() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        if user:
            user.wallet_address = wallet_address
            session.commit()
            update.message.reply_text('钱包地址已绑定。谢谢!')
            
    return ConversationHandler.END

def make_wish_come_true(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id in admins:
        update.message.reply_text('请输入要实现愿望的用户ID')
    else:
        update.message.reply_text('你没有权限使用此功能')
    return WISH_COME_TRUE_READY

def receive_wish_come_true(update: Update, context: CallbackContext) -> int:
    user_id = update.message.text
    with session_scope() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        if user and user.wish:
            if user.wish_claimed:
                update.message.reply_text('愿望已实现。')
                return ConversationHandler.END
            update.message.reply_text(f'用户： {user.username}\n愿望： {user.wish}\n钱包地址： {user.wallet_address}\n最后更新时间： {datetime.now():%Y-%m-%d %H:%M}\n目前邀请人数：{user.invitees_count}')
            update.message.reply_text('留下你的备注或者使用/cancel取消')
            context.user_data['user_id'] = user_id  # Store user_id in context
        else:
            update.message.reply_text('用户没有愿望')
    return WISH_COME_TRUE

def wish_come_true(update: Update, context: CallbackContext) -> int:
    remark = update.message.text
    user_id = context.user_data['user_id']
    with session_scope() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        if user:
            user.wish_claimed = True
            session.commit()
            bot.send_message(chat_id=user.user_id, parse_mode=ParseMode.MARKDOWN_V2,text='🎉恭喜用户 @{0} 愿望成真\n\n🎁 您的愿望为*{1}*\n{2}\n\n💬中奖地址：`{3}`'.format(user.username, user.wish, remark if remark else '', user.wallet_address if user.wallet_address else '暂未提交'))
            invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate = get_invitees_stats(user_id)
            send_group_message(user_id, invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate)

    with session_scope() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        if user:
            user.wish_claimed = True
            session.commit()
            update.message.reply_text('愿望已实现。谢谢!')
    return ConversationHandler.END

def make_wish(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    with session_scope() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        is_subscribed = is_user_subscribed(user_id)
        logger.info(f'User: {user} & is_subscribed: {is_subscribed}')
        if user and is_subscribed:
            with session_scope() as session:
                invite = session.query(Invite).filter_by(invitee_id=user_id).first()
                if invite:
                    inviter = session.query(User).filter_by(user_id=invite.user_id).first()
                    invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate = get_invitees_stats(inviter.user_id)
                    send_group_message(inviter.user_id, invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate)
                        
            if user.wallet_address:
                if user.wish:
                    update.message.reply_text(f'目前愿望： {user.wish}\n请写下你新的愿望\n或使用/cancel取消')
                else:
                    update.message.reply_text('请写下你的愿望\n使用/cancel取消')
                return WISH
            else:
                update.message.reply_text('请先按绑定钱包按钮绑定钱包地址')
        else:
            message, reply_markup = subscribe_channel_message()
            update.message.reply_text(message, reply_markup=reply_markup)

def get_invitees_stats(user_id):
    with session_scope() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        invitees = session.query(Invite).filter_by(user_id=user_id).all()
        invitees_subscribed_count = session.query(User).filter(User.user_id.in_([invitee.invitee_id for invitee in invitees]), User.is_subscribed == True).count()
        # count the number of invitees who have written down their wishes
        invitees_wish_count = session.query(User).filter(User.user_id.in_([invitee.invitee_id for invitee in invitees]), User.wish != None).count()
        if user.invitees_count > 0:
            invitees_subscribed_rate = invitees_subscribed_count / user.invitees_count
            invitees_wish_rate = invitees_wish_count / user.invitees_count
        else:
            invitees_subscribed_rate = 0
            invitees_wish_rate = 0
        return invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate

def send_group_message(user_id, invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate) -> None:
    with session_scope() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        text_message = f'用户：@{user.username}\n用户id：`{user.user_id}`\n愿望：{user.wish}\n钱包地址：`{user.wallet_address}`\n最后更新时间：{datetime.now():%Y－%m－%d %H:%M}\n目前邀请人数：{user.invitees_count}\n邀请者关注频道人数：{invitees_subscribed_count}\n邀请者关注频道率：{invitees_subscribed_rate:.0%}\n邀请者写下愿望人数：{invitees_wish_count}\n邀请者写下愿望率：{invitees_wish_rate:.0%}'
        if not user.message_id:
            message = bot.send_message(chat_id=group_info.id, text=text_message, parse_mode=ParseMode.MARKDOWN_V2)
            user.message_id = message.message_id
            session.commit()
        else:
            try:
                if user.wish_claimed:
                    message = bot.edit_message_text(chat_id=group_info.id, message_id=user.message_id, parse_mode=ParseMode.MARKDOWN_V2, text=text_message + '\n\n[愿望已实现]')
                else:
                    message = bot.edit_message_text(chat_id=group_info.id, message_id=user.message_id, parse_mode=ParseMode.MARKDOWN_V2, text=text_message)
            except BadRequest as e:
                if 'Message is not modified' in str(e):
                    pass 
                else:
                    raise 

def get_link_keyboard_button():
    group_invite_link = bot.exportChatInviteLink(chat_id=group_info.id)
    keyboard = [
        [InlineKeyboardButton("点我关注频道后参加活动", url=channel_info.invite_link)],
        [InlineKeyboardButton("愿望成真公示群", url=group_invite_link)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup

def get_my_invitees(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    with session_scope() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        if user:
            text_message = f'🥇 TRC20地址：{user.wallet_address if user.wallet_address else "暂未提交"}\n\n🥈 用户名：@{user.username}\n\n🥉 用户ID：{user.user_id}\n\n🔮 邀请人数：{user.invitees_count}'
            update.message.reply_text(text_message, reply_markup=get_link_keyboard_button())

def receive_wish(update: Update, context: CallbackContext) -> int:
    wish_text = update.message.text
    user_id = update.effective_user.id

    with session_scope() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        if user:
            if not user.wish:
                user.wish = wish_text
                user.wish_date = datetime.now()
                invite_link = generate_unique_link(user_id)
                session.commit()
                invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate = 0, 0, 0, 0
                send_group_message(user_id, invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate)
                update.message.reply_text('愿望已记录。谢谢!\n你的邀请链接：' + invite_link)
            elif user.wish_claimed:
                update.message.reply_text('愿望已经实现，不能再许愿。')
                return ConversationHandler.END
            else:
                user.wish = wish_text
                user.wish_date = datetime.now()
                session.commit()
                invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate = get_invitees_stats(user_id)
                send_group_message(user_id, invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate)
                update.message.reply_text('愿望已更新。谢谢!')
            invite = session.query(Invite).filter_by(invitee_id=user_id).first()
            if invite:
                inviter = session.query(User).filter_by(user_id=invite.user_id).first()
                invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate = get_invitees_stats(inviter.user_id)
                send_group_message(inviter.user_id, invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate)
            
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('操作已取消。')
    return ConversationHandler.END

# Define ConversationHandler
WISH = 1
WALLET = 2
WISH_COME_TRUE_READY =3
WISH_COME_TRUE = 4

wish_come_true_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^🌟实现愿望$'), make_wish_come_true)],
    states={
        WISH_COME_TRUE_READY: [MessageHandler(Filters.text & ~Filters.command, receive_wish_come_true)],
        WISH_COME_TRUE: [MessageHandler(Filters.text & ~Filters.command, wish_come_true)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

make_wish_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^🏮写下愿望$'), make_wish)],
    states={
        WISH: [MessageHandler(Filters.text & ~Filters.command, receive_wish)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

bind_wallet_address_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^🧧绑定钱包$'), bind_wallet_address)],
    states={
        WALLET: [MessageHandler(Filters.text & ~Filters.command, receive_wallet_address)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

def is_user_subscribed(user_id):
    try:
        chat_member = bot.get_chat_member(chat_id=os.getenv('CHANNEL_NAME'), user_id=user_id)
        is_subscribed = chat_member.status not in ('left', 'kicked')
        
        # Update the user's status in the database
        with session_scope() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            if user:
                user.is_subscribed = is_subscribed
                session.commit()

        return is_subscribed
    except Exception as e:
        logger.exception(e)
        return False

def start(update: Update, context: CallbackContext) -> None:    
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    username = update.effective_user.username

    invite_user_id = None
    if context.args:
        invite_link_args = context.args[0]
        if '_' in invite_link_args:
            invite_user_id, _ = invite_link_args.split('_')

    with session_scope() as session:
        existing_user = session.query(User).filter_by(user_id=user_id).first()

        # Check if the user is a member of the channel
        is_subscribed = False
        try:
            member = context.bot.get_chat_member(chat_id=os.getenv('CHANNEL_NAME'), user_id=user_id)
            if member.status not in ['left', 'kicked']:
                is_subscribed = True
        except BadRequest:
            pass

        if existing_user:
            add_user_to_db(user_id=user_id, name=user_name, username=username, status=existing_user.status, is_subscribed=is_subscribed)
        else:
            add_user_to_db(user_id=user_id, name=user_name, username=username, is_subscribed=is_subscribed)
            if not is_subscribed:
                message, reply_markup = subscribe_channel_message(True)
                update.message.reply_text(message, reply_markup=reply_markup)
            else:
                update.message.reply_text('📣恭喜，您的帐号创建成功！')

        if invite_user_id:
            invite_user = session.query(User).filter_by(user_id=invite_user_id).first()
            if invite_user and invite_user.user_id != user_id:
                # check if the user has already been invited
                existing_invite = session.query(Invite).filter_by(user_id=invite_user_id, invitee_id=user_id).first()
                if not existing_invite:
                    invite = Invite(user_id=invite_user_id, invitee_id=user_id)
                    invite_user.invitees_count += 1
                    session.add(invite)
                    session.commit()
                    invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate = get_invitees_stats(invite_user_id)
                    send_group_message(invite_user_id, invitees_subscribed_count, invitees_subscribed_rate, invitees_wish_count, invitees_wish_rate)
                    bot.send_message(chat_id=invite_user_id, text=f'你邀请了一个新成员: {user_name}')
                else:
                    bot.send_message(chat_id=user_id, text=f'你已经被邀请过了')

    if user_id in admins:
        update.message.reply_text('欢迎管理员!', reply_markup=get_keyboard(admin=True))
    else:
        # Selected lines from the poems
        poem_lines = [
            "元宵佳节到，请你吃元宵，香甜满心间，新春人更俏。",
            "三五良宵，花灯吐艳映新春；一年初望，明月生辉度佳节。",
            "正月十五良宵到，花灯吐艳把春报；一年初望明月照，汤圆滚烫闹良宵。",
            "龙年好，龙年妙，元宵佳节快乐抱；龙年好，龙年妙，元宵佳节开心邀。",
            "元宵喜庆乐盈盈，大伙开心闹元宵，大街小巷人气旺 ，开开心心过元宵！",
            "灯笼红红，月亮皎皎，朗朗乾坤，思念普照。圆圆元宵，祝福为勺，圆你心愿，圆你梦晓。",
            "一个圆圆的汤圆，送给你；一颗圆圆的心，献给你；一份圆圆的真情，寄给你；一条圆圆的祝福，传给你。",
            "元宵佳节明月圆，人间欢乐丰收年，花灯照亮好前景，日子幸福比蜜甜，健康快乐身体好，万事如意随心愿。",
            "团团圆圆，又是一年。思思念念，冬日无眠。欢欢聚聚，新年独现。汤汤团团，精美甜点。甜甜蜜蜜，生活惬意。元宵佳节，共度欢颜！",
            "元宵节，赏花灯，照的心里亮晶晶；元宵节，闹热闹，幸福好运随春到；元宵节，吃元宵，乐的你呀呱呱叫；元宵节，送祝福，健康吉祥到你府。",
            "元宵节来吃汤圆，吃碗汤圆心甜甜；幸福汤圆一入口，健康快乐常陪伴；爱情汤圆一入口，心如细丝甜如蜜；金钱汤圆一入口，财源滚滚斩不断！",
            "天上繁星晶晶亮，地上彩灯换色彩；天上明月寄相思，地上汤圆寄团圆；又逢一年元宵节，温馨祝福送心田；健康吉祥送给你，愿你梦想都实现。",
            "月儿圆圆挂枝头，元宵圆圆入你口，又是元宵佳节到，吃颗元宵开口笑，笑笑烦恼都跑掉，一生好运围你绕，事事顺利真美妙，元宵佳节乐逍遥！",
            "正月十五赏花灯，祝你心情亮如灯；正月十五吃汤圆，祝你阖家喜团圆；正月十五元宵香，祝你身体更健康；正月十五喜连连，祝你万事皆吉祥。",
            "正月十五闹花灯，焰火惊艳添福运；舞龙舞狮普天庆，且看且叹不须停；热火朝天贺元宵，万家团圆福气绕；祥瑞扑面跟你跑，幸福日子更美好！",
            "正月十五月儿圆，美好祝福在耳边；正月十五元宵甜，祝你今年更有钱；正月十五汤圆香，祝你身体更健康；正月十五乐团圆，祝你元宵乐连连！",
            "正月十五月儿圆，真诚祝福送身边；正月十五元宵甜，祝你龙年更有钱；正月十五展笑颜，快乐长久幸福绵；正月十五享团圆，祝你吉祥在龙年！",
            "车如流水马如龙，相约赏灯乐融融；金狮涌动舞不停，猜中灯谜笑盈盈；皎皎明月泻清辉，颗颗汤圆情意随；元宵佳节已然到，愿你开怀乐淘淘。",
            "花灯照，放鞭炮；月辉耀，幸福绕；好运至，乐逍遥；祝福多，好热闹；财神来，快拥抱；万事顺，在今朝；享团圆，过元宵；传讯息，很美妙。",
            "春风阵阵佳节到，元宵灯会真热闹；四面八方人如潮，欢声笑语声声高；亲朋好友祝福绕，开开心心活到老；祝你佳节好运罩，万事顺利人欢笑！",
            "鱼跃龙门好有福，元宵佳节早送福；大福小福全家福，有福享福处处福；知福来福有祝福，清福鸿福添幸福；接福纳福年年福，守福祈福岁岁福！",
            "新年到，元宵闹，蹦到锅里搅一搅；馅香溢，福满多，包出新春好味道；喜气扬，福气冒，阖家团圆乐滔滔；你一颗，我一颗，品出龙年好味道！",
            "过年好，元宵到，幸幸福福一年绕；过年好，元宵到，开开心心四季妙；过年好，元宵到，顺顺利利全家好；过年好，元宵到，团团圆圆过元宵。",
            "元宵佳节明月升，嫦娥曼舞看清影，元宵香从圆月来，高歌一曲赏美景，亲友团圆叙旧情，一缕相思圆月中，团圆之夜思绪浓，共用快乐互叮咛。",
            "一元复苏大地春，正月十五闹元宵。圆月高照星空灿，灯火辉煌闹春年。万家灯火歌声扬，团团圆圆品汤圆，其乐融融笑声甜，幸福滋味香飘然。",
            "元宵圆圆盘中盛，举家投著来品尝。颗颗润滑甜如蜜，团圆之情入心底。彩灯纷纷空中挂，亲友相约赏灯忙。灯火通明好年景，万千喜悦心中放。",
            "唢呐声声人欢笑，张灯结彩闹元宵。明月花灯两相照，龙狮飞舞热情高。烟花爆竹绽笑颜，剪纸窗花美无边。一碗汤圆香又甜，万千祝福润心田。",
            "圆月照，元宵到，吃口汤圆幸福绕；赏花灯，猜灯谜，万千喜气将你抱；访亲朋，会老友，举杯畅饮心欢笑；人团圆，享天伦，美酒飘香乐淘淘。",
            "点点元宵似珍珠，用心品尝香无数。一个元宵千般情，愿你天天好心情。展展花灯美无边，流连忘返人群间。一个花灯万般愿，愿你生活比蜜甜。",
            "元宵佳节闹花灯，一份祝福藏其中。明月皎皎人团圆，汤圆香甜爱情甜。红灯高照事业旺，美酒醇厚阖家康。愿你元宵乐连连，开心幸福绽笑颜。",
            "正月十五月儿圆，元宵佳节喜庆多，心情愉快朋友多，身体健康快乐多，财源滚滚钞票多，全家团圆幸福多，年年吉祥如意多，岁岁平安多好事！",
            "赏圆月，闹元宵，花灯亮彩快乐挑；舞龙灯，敲锣鼓，幸福为你在做主；放烟花，吃汤圆，祈福祝愿家团圆；诉真情，发贺词，愿你龙年行大运。",
            "杨柳轻扬春意早，十里长街闹元宵。扭动腰肢挑花灯，耄耋童子齐欢笑。糯米揉团蜜馅包，团团圆圆吃到饱。叙过家常侃大山，大家一起乐元宵。",
            "送走冬季的严寒，迎来春天的灿烂；世界随著季节变，思念却是更胜前；元宵佳节心情暖，给你祝福不会变；愿你生活比春花艳，愿你事业比月亮圆。",
            "元宵真热闹，看烟花，放鞭炮；灯笼红又亮，挂满窗，喜洋洋；汤圆香又甜，福气沾，家团圆；日子更红火，财源广，快乐多；祝福情意真，好前程，人安生！"
        ]

        random_line = random.choice(poem_lines)

        italicized_random_line = f"*{random_line}*"

        # Prepare the welcome message with the italicized poem line
        welcome_message = f'欢迎参加🏮元宵节花灯庆祝活动！\n\n{italicized_random_line}\n\n祝你🏮元宵节快乐！'

        update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN, reply_markup=get_link_keyboard_button())

def main() -> None:
    # Create the Updater and pass it your bot's token.
    updater = Updater(bot=bot, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Register command handlers
    dp.add_handler(CommandHandler("start", start)) 
    dp.add_handler(MessageHandler(Filters.regex('^🥣我的邀请$'), get_my_invitees))
    dp.add_handler(make_wish_handler)
    dp.add_handler(bind_wallet_address_handler)
    dp.add_handler(wish_come_true_handler)
    # Start the Bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()