from telegram import Bot, Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
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
bot = Bot(token=os.getenv('BOT_TOKEN')) # Test Bot
# bot = Bot(token='6524274145:AAF80QHBzEmbyC8GLVNw7N-iH383yAyBmBU') # Production
# group_chat_id = '-4076578089' # Test Group
group_chat_id = os.getenv('ADMIN_GROUP_ID') # Production

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

def get_user_keyboard():
    keyboard = [
        [KeyboardButton("写下愿望"), KeyboardButton("绑定钱包")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def generate_unique_link(user_id: int) -> str:
    """Generate a unique link for each user based on their user_id"""
    unique_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    bot_username = bot.getMe().username
    return f'https://t.me/{bot_username}?start={user_id}_{unique_str}'

def subscribe_channel_message(start_message: bool = False):
    message = f"请先加入👉{channel_name}频道👈"
    if start_message:
        message = f"📣恭喜，您的帐号创建成功！\n\n" + message
    channel_info = bot.getChat(chat_id=os.getenv('CHANNEL_ID'))
    channel_name = channel_info.username
    
    keyboard = [
        [InlineKeyboardButton(f"{channel_name}", url=f"https://t.me/{os.getenv('CHANNEL_NAME')}")]
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
            update.message.reply_text('是否确认实现愿望？请回答Yes或者使用/cancel取消')
            context.user_data['user_id'] = user_id  # Store user_id in context
        else:
            update.message.reply_text('用户没有愿望')
    return WISH_COME_TRUE

def wish_come_true(update: Update, context: CallbackContext) -> int:
    if update.message.text.lower() == 'yes':
        user_id = context.user_data['user_id']
        with session_scope() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            if user:
                user.wish_claimed = True
                session.commit()
                bot.send_message(chat_id=user.user_id, text='你的愿望已实现。谢谢!')
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
        text_message = f'用户： {user.username}\n用户id： {user.user_id}\n愿望： {user.wish}\n钱包地址： {user.wallet_address}\n最后更新时间： {datetime.now():%Y-%m-%d %H:%M}\n目前邀请人数：{user.invitees_count}\n邀请者关注频道人数： {invitees_subscribed_count}\n邀请者关注频道率： {invitees_subscribed_rate:.0%}\n邀请者写下愿望人数： {invitees_wish_count}\n邀请者写下愿望率： {invitees_wish_rate:.0%}'
        if not user.message_id:
            message = bot.send_message(chat_id=group_chat_id, text=text_message)
            user.message_id = message.message_id
            session.commit()
        else:
            try:
                if user.wish_claimed:
                    message = bot.edit_message_text(chat_id=group_chat_id, message_id=user.message_id, text=text_message + '\n\n[愿望已实现]')
                else:
                    message = bot.edit_message_text(chat_id=group_chat_id, message_id=user.message_id, text=text_message)
            except BadRequest as e:
                if 'Message is not modified' in str(e):
                    pass  # Ignore 'Message is not modified' error
                else:
                    raise  # Re-raise exception if it's a different error

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
    entry_points=[MessageHandler(Filters.regex('^实现愿望$'), make_wish_come_true)],
    states={
        WISH_COME_TRUE_READY: [MessageHandler(Filters.text & ~Filters.command, receive_wish_come_true)],
        WISH_COME_TRUE: [MessageHandler(Filters.text & ~Filters.command, wish_come_true)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

make_wish_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^写下愿望$'), make_wish)],
    states={
        WISH: [MessageHandler(Filters.text & ~Filters.command, receive_wish)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

bind_wallet_address_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^绑定钱包$'), bind_wallet_address)],
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

        if invite_user_id:
            invite_user = session.query(User).filter_by(user_id=invite_user_id).first()
            if invite_user:
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
        
        if not is_subscribed:
            message, reply_markup = subscribe_channel_message(True)
            update.message.reply_text(message, reply_markup=reply_markup)
        else:
            update.message.reply_text('📣恭喜，您的帐号创建成功！')

    if user_id in admins:
        keyboard = get_user_keyboard().keyboard + [[KeyboardButton("实现愿望")]]
        update.message.reply_text('欢迎管理员!', reply_markup=ReplyKeyboardMarkup(keyboard))
    else:
        keyboard = get_user_keyboard().keyboard
        update.message.reply_text('欢迎使用!', reply_markup=ReplyKeyboardMarkup(keyboard))


def main() -> None:
    # Create the Updater and pass it your bot's token.
    updater = Updater(bot=bot, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Register command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(make_wish_handler)
    dp.add_handler(bind_wallet_address_handler)
    dp.add_handler(wish_come_true_handler)
    # Start the Bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()