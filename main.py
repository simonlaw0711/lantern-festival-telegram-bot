from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters, CallbackQueryHandler, ConversationHandler
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
    invitees_count = Column(Integer, default=0)
    username = Column(String(255), unique=True)
    wallet_address = Column(String(255), nullable=True)
    is_subscribed = Column(Boolean, default=False)
    message_id = Column(BigInteger, nullable=True)

    __table_args__ = (Index('idx_username','username'),)

DATABASE_URL = f"mysql+mysqlconnector://{os.getenv('MYSQL_USERNAME')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}/{os.getenv('MYSQL_DATABASE')}?charset=utf8mb4"
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

# Admins list
admins = [os.getenv("ADMIN_IDS").split(',')]

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

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("实现愿望", callback_data='rub_the_lamp')]
    ]
    return InlineKeyboardMarkup(keyboard)

def generate_unique_link(user_id: int) -> str:
    """Generate a unique link for each user based on their user_id"""
    unique_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    bot_username = bot.getMe().username
    return f'https://t.me/{bot_username}?start={user_id}_{unique_str}'

def bind_wallet_address(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('请写下你的钱包地址\n使用/cancel取消')
    return WALLET

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

def make_wish(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    with session_scope() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        if user and user.is_subscribed:
            if user.wallet_address:
                update.message.reply_text('请写下你的愿望\n使用/cancel取消')
                return WISH
            else:
                update.message.reply_text('请先绑定钱包地址')
        else:
            update.message.reply_text(f'请先關注頻道\n{os.getenv("CHANNEL_LINK")}')

def receive_wish(update: Update, context: CallbackContext) -> int:
    wish_text = update.message.text
    user_id = update.effective_user.id

    with session_scope() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        if user:
            # Save the wish to the database
            user.wish = wish_text
            user.wish_date = datetime.now()
            invite_link = generate_unique_link(user_id)
            # Send a message to the group chat
            message = bot.send_message(chat_id=group_chat_id, text=f'用户： {user.username}\n愿望： {wish_text}\n钱包地址： {user.wallet_address}\n时间： {datetime.now():%Y-%m-%d %H:%M}\n目前邀请人数：{user.invitees_count}')
            user.message_id = message.message_id
            session.commit()
            # Send a message to the user
            update.message.reply_text('愿望已记录。谢谢!\n你的邀请链接：' + invite_link)

    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('操作已取消。')
    return ConversationHandler.END

# Define ConversationHandler
WISH = 1
WALLET = 2

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

def chat_member_joined(update: Update, context: CallbackContext) -> None:
    new_members = update.message.new_chat_members
    for new_member in new_members:
        with session_scope() as session:
            existing_user = session.query(User).filter_by(user_id=new_member.id).first()
            if existing_user:
                existing_user.is_subscribed = True
                session.commit()

def chat_member_left(update: Update, context: CallbackContext) -> None:
    left_member = update.message.left_chat_member
    with session_scope() as session:
        existing_user = session.query(User).filter_by(user_id=left_member.id).first()
        if existing_user:
            existing_user.is_subscribed = False
            session.commit()

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
        existing_username = session.query(User).filter_by(username=username).first()

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
        elif existing_username:
            update_user_to_db(user_id=user_id, name=user_name, username=username, is_subscribed=is_subscribed)
        else:
            add_user_to_db(user_id=user_id, name=user_name, username=username, is_subscribed=is_subscribed)

        if invite_user_id:
            inviter = session.query(User).filter_by(user_id=invite_user_id).first()
            if inviter:
                inviter.invitees_count += 1
                session.commit()
                bot.edit_message_text(chat_id=group_chat_id, message_id=inviter.message_id, text=f'用户： {inviter.username}\n愿望： {inviter.wish}\n钱包地址： {inviter.wallet_address}\n时间： {datetime.now():%Y-%m-%d %H:%M}\n目前邀请人数：{inviter.invitees_count}')

    if user_id in admins:
        admin_keyboard = get_admin_keyboard()
        user_keyboard = get_user_keyboard()
        update.message.reply_text('欢迎管理员!', reply_markup=admin_keyboard)
        update.message.reply_text('以下是用户功能', reply_markup=user_keyboard)
    else:
        keyboard = get_user_keyboard()
        update.message.reply_text('欢迎使用!', reply_markup=keyboard)


def main() -> None:
    # Create the Updater and pass it your bot's token.
    updater = Updater(bot=bot, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Register command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, chat_member_joined))
    dp.add_handler(MessageHandler(Filters.status_update.left_chat_member, chat_member_left))
    dp.add_handler(make_wish_handler)
    dp.add_handler(bind_wallet_address_handler)
    # Start the Bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()