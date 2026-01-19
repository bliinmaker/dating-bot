import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from app.core import config
from app.models import *
from app.models.database import Session
from app.services.user_service import UserService
from app.services.profile_service import ProfileService
from app.services.matching_service import MatchingService
import io
from telegram.error import BadRequest
from app.services.matching_service import preload_profiles

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, config.LOG_LEVEL)
)
logger = logging.getLogger(__name__)

START = 0
REGISTER_NAME = 1
REGISTER_AGE = 2
REGISTER_GENDER = 3
REGISTER_BIO = 4
REGISTER_LOCATION = 5
REGISTER_INTERESTS = 6
REGISTER_PREFERRED_GENDER = 7
REGISTER_PREFERRED_AGE = 8
REGISTER_PREFERRED_LOCATION = 9
UPLOAD_PHOTO = 10
BROWSING = 20
VIEWING_PROFILE = 21
VIEWING_MATCHES = 22
CHATTING = 23
EDIT_PROFILE = 30
EDIT_NAME = 31
EDIT_AGE = 32
EDIT_BIO = 33
EDIT_LOCATION = 34
EDIT_INTERESTS = 35
EDIT_PREFERRED_GENDER = 36
EDIT_PREFERRED_AGE = 37
EDIT_PREFERRED_LOCATION = 38
DIRECT_EDIT_AGE_RANGE = 100
DIRECT_EDIT_LOCATION = 101
user_states = {}

user_data = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.effective_user.id
    username = update.effective_user.username

    session = Session()
    try:
        user = UserService.get_or_create_user(session, user_id, username)

        user_profile = UserService.get_user_profile(session, user_id)

        if user_profile and user_profile.get("has_profile"):
            await show_main_menu(update, context)
            context.user_data['state'] = BROWSING
            user_states[user_id] = BROWSING
        else:
            await update.message.reply_text(
                "👋 Привет! Добро пожаловать в Dating Bot!\n"
                "Давайте создадим вашу анкету, чтобы вы могли найти свою пару."
            )
            await start_registration(update, context)
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text(
            "Произошла ошибка при запуске бота. Пожалуйста, попробуйте снова позже."
        )
    finally:
        session.close()


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the registration process"""
    user_id = update.effective_user.id

    user_data[user_id] = {}
    context.user_data['profile_data'] = {}

    await update.message.reply_text("Как вас зовут?")
    user_states[user_id] = REGISTER_NAME
    context.user_data['state'] = REGISTER_NAME


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main menu"""
    user_id = update.effective_user.id

    keyboard = [
        [KeyboardButton("👀 Смотреть анкеты")],
        [KeyboardButton("❤️ Мои пары"), KeyboardButton("👤 Моя анкета")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Главное меню:",
        reply_markup=reply_markup
    )

    sync_user_state(user_id, context, BROWSING)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo upload"""
    user_id = update.effective_user.id

    if update.message.photo:
        photo = update.message.photo[-1]
        file_id = photo.file_id

        session = Session()
        try:
            user = UserService.get_or_create_user(session, user_id)

            profile_service = ProfileService()

            user_profile = UserService.get_user_profile(session, user_id)

            if not user_profile or not user_profile.get("has_profile"):
                profile_data = user_data.get(user_id, {})
                if not profile_data and 'profile_data' in context.user_data:
                    profile_data = context.user_data['profile_data']

                profile = profile_service.create_profile(session, user.id, profile_data)

                if not profile:
                    await update.message.reply_text(
                        "Произошла ошибка при создании профиля. Пожалуйста, попробуйте снова позже."
                    )
                    return

                profile_id = profile.id
            else:
                profile_id = user_profile["profile_id"]

            photo_file = await context.bot.get_file(photo.file_id)
            photo_bytes = io.BytesIO()
            await photo_file.download_to_memory(photo_bytes)
            photo_bytes.seek(0)

            s3_path = profile_service.add_photo(
                session,
                profile_id,
                photo_bytes.getvalue(),
                telegram_file_id=file_id,
                is_main=True
            )

            if s3_path:
                if user_id in user_data:
                    del user_data[user_id]
                if 'profile_data' in context.user_data:
                    context.user_data.pop('profile_data', None)

                if context.user_data['state'] == UPLOAD_PHOTO and user_profile and user_profile.get("has_profile"):
                    await update.message.reply_text("Фотография успешно обновлена!")
                    await show_my_profile(update, context)
                else:
                    await update.message.reply_text(
                        "Ваша анкета успешно создана! Теперь вы можете начать поиск пары."
                    )
                    await show_main_menu(update, context)
                    user_states[user_id] = BROWSING
                    context.user_data['state'] = BROWSING

                    preload_profiles.delay(user.id)
            else:
                await update.message.reply_text(
                    "Произошла ошибка при загрузке фото. Пожалуйста, попробуйте еще раз:"
                )
        except Exception as e:
            logger.error(f"Error handling photo upload: {e}")
            await update.message.reply_text(
                "Произошла ошибка при обработке фото. Пожалуйста, попробуйте снова позже."
            )
        finally:
            session.close()
    else:
        await update.message.reply_text("Пожалуйста, отправьте фотографию:")


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    user_id = query.from_user.id

    if 'state' not in context.user_data:
        session = Session()
        try:
            user_profile = UserService.get_user_profile(session, user_id)
            if user_profile and user_profile.get("has_profile"):
                state = user_states.get(user_id, BROWSING)
                context.user_data['state'] = state
                logger.info(f"Recovered state for user {user_id}: {state}")
            else:
                await query.answer("Ваша сессия истекла. Используйте /start для создания профиля.")
                return
        except Exception as e:
            logger.error(f"Error recovering state in handle_button: {e}")
        finally:
            session.close()

    await query.answer()

    if query.data.startswith("init_chat_"):
        await show_matches(update, context)
        return

    if query.data in ["match_next", "match_prev"]:
        await show_matches(update, context)
        return
    elif query.data == "back_to_menu":
        await show_main_menu(update, context)
        sync_user_state(user_id, context, BROWSING)
        return
    elif query.data == "match_count":
        return

    if query.data.startswith("like_") or query.data.startswith("skip_"):
        action, profile_id = query.data.split("_")
        await handle_profile_action(update, context, action, int(profile_id))
    elif query.data == "no_username":
        await query.answer(
            "У пользователя нет username в Telegram. Попросите его добавить username в настройках Telegram для прямого общения.")
    elif query.data == "continue_browsing":
        await show_next_profile(update, context)
    elif query.data == "edit_profile":
        await show_edit_profile_menu(update, context)
    elif query.data.startswith("edit_field_"):
        field = query.data.split("_")[2]
        await handle_edit_field_selection(update, context, field)
    elif query.data == "edit_age_range":
        await direct_edit_age_range(update, context)
    elif query.data == "edit_location_pref":
        await direct_edit_location_pref(update, context)
    elif query.data == "add_photo":
        await context.bot.send_message(user_id, "Пожалуйста, отправьте новую фотографию.")
        sync_user_state(user_id, context, UPLOAD_PHOTO)
    elif query.data == "edit_preferences":
        await show_edit_profile_menu(update, context)
    elif query.data == "back_to_profile":
        await show_my_profile(update, context)
    else:
        await context.bot.send_message(user_id, "Действие не распознано.")


async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle name input"""
    user_id = update.effective_user.id
    name = update.message.text.strip()

    if len(name) < 2:
        await update.message.reply_text("Имя должно содержать минимум 2 символа. Пожалуйста, попробуйте еще раз:")
        return

    user_data[user_id]["name"] = name
    if 'profile_data' in context.user_data:
        context.user_data['profile_data']["name"] = name

    await update.message.reply_text("Сколько вам лет?")
    user_states[user_id] = REGISTER_AGE
    context.user_data['state'] = REGISTER_AGE


async def handle_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle age input"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    try:
        age = int(text)
        if age < 18 or age > 100:
            await update.message.reply_text("Возраст должен быть от 18 до 100 лет. Пожалуйста, попробуйте еще раз:")
            return

        user_data[user_id]["age"] = age
        if 'profile_data' in context.user_data:
            context.user_data['profile_data']["age"] = age

        keyboard = [
            [KeyboardButton("Мужской"), KeyboardButton("Женский")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Укажите ваш пол:", reply_markup=reply_markup)
        user_states[user_id] = REGISTER_GENDER
        context.user_data['state'] = REGISTER_GENDER
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите возраст цифрами:")


async def handle_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle gender input"""
    user_id = update.effective_user.id
    gender = update.message.text.strip()

    if gender not in ["Мужской", "Женский"]:
        keyboard = [
            [KeyboardButton("Мужской"), KeyboardButton("Женский")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Пожалуйста, выберите из предложенных вариантов:", reply_markup=reply_markup)
        return

    user_data[user_id]["gender"] = gender
    if 'profile_data' in context.user_data:
        context.user_data['profile_data']["gender"] = gender

    if gender == "Мужской":
        user_data[user_id]["preferred_gender"] = "Женский"
        if 'profile_data' in context.user_data:
            context.user_data['profile_data']["preferred_gender"] = "Женский"
    else:
        user_data[user_id]["preferred_gender"] = "Мужской"
        if 'profile_data' in context.user_data:
            context.user_data['profile_data']["preferred_gender"] = "Мужской"

    await update.message.reply_text(
        "Расскажите о себе (ваша биография, интересы, что вы ищете и т.д.):"
    )
    user_states[user_id] = REGISTER_BIO
    context.user_data['state'] = REGISTER_BIO


async def handle_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle interests input"""
    user_id = update.effective_user.id
    interests_text = update.message.text.strip()

    if len(interests_text) < 3:
        await update.message.reply_text("Пожалуйста, укажите хотя бы один интерес:")
        return

    interests = [i.strip() for i in interests_text.split(",") if i.strip()]
    user_data[user_id]["interests"] = interests
    if 'profile_data' in context.user_data:
        context.user_data['profile_data']["interests"] = interests

    await update.message.reply_text(
        "Укажите предпочитаемый возрастной диапазон через дефис (например: 20-35):"
    )
    user_states[user_id] = REGISTER_PREFERRED_AGE
    context.user_data['state'] = REGISTER_PREFERRED_AGE


async def handle_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bio input"""
    user_id = update.effective_user.id
    bio = update.message.text.strip()

    if len(bio) < 10:
        await update.message.reply_text("Расскажите о себе подробнее (минимум 10 символов):")
        return

    user_data[user_id]["bio"] = bio
    if 'profile_data' in context.user_data:
        context.user_data['profile_data']["bio"] = bio

    await update.message.reply_text("Укажите ваш город:")
    user_states[user_id] = REGISTER_LOCATION
    context.user_data['state'] = REGISTER_LOCATION


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle location input"""
    user_id = update.effective_user.id
    location = update.message.text.strip()

    if len(location) < 2:
        await update.message.reply_text("Пожалуйста, укажите корректное название города:")
        return

    user_data[user_id]["location"] = location
    if 'profile_data' in context.user_data:
        context.user_data['profile_data']["location"] = location

    await update.message.reply_text(
        "Укажите ваши интересы через запятую (например: музыка, спорт, путешествия):"
    )
    user_states[user_id] = REGISTER_INTERESTS
    context.user_data['state'] = REGISTER_INTERESTS


async def handle_preferred_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle preferred gender input"""
    user_id = update.effective_user.id
    preferred_gender = update.message.text.strip()

    if preferred_gender not in ["Мужской", "Женский", "Любой"]:
        keyboard = [
            [KeyboardButton("Мужской"), KeyboardButton("Женский"), KeyboardButton("Любой")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Пожалуйста, выберите из предложенных вариантов:", reply_markup=reply_markup)
        return

    if preferred_gender == "Любой":
        preferred_gender = None

    user_data[user_id]["preferred_gender"] = preferred_gender
    if 'profile_data' in context.user_data:
        context.user_data['profile_data']["preferred_gender"] = preferred_gender

    await update.message.reply_text(
        "Укажите предпочитаемый возрастной диапазон через дефис (например: 20-35):"
    )
    user_states[user_id] = REGISTER_PREFERRED_AGE
    context.user_data['state'] = REGISTER_PREFERRED_AGE


async def handle_preferred_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle preferred age input"""
    user_id = update.effective_user.id
    age_range = update.message.text.strip()

    try:
        if "-" in age_range:
            min_age, max_age = map(int, age_range.split("-"))

            if min_age < 18 or max_age > 100 or min_age > max_age:
                await update.message.reply_text(
                    "Пожалуйста, укажите корректный возрастной диапазон (от 18 до 100 лет):"
                )
                return

            user_data[user_id]["preferred_age_min"] = min_age
            user_data[user_id]["preferred_age_max"] = max_age
            if 'profile_data' in context.user_data:
                context.user_data['profile_data']["preferred_age_min"] = min_age
                context.user_data['profile_data']["preferred_age_max"] = max_age
        else:
            age = int(age_range)
            if age < 18 or age > 100:
                await update.message.reply_text(
                    "Пожалуйста, укажите корректный возраст (от 18 до 100 лет):"
                )
                return

            user_data[user_id]["preferred_age_min"] = age
            user_data[user_id]["preferred_age_max"] = age
            if 'profile_data' in context.user_data:
                context.user_data['profile_data']["preferred_age_min"] = age
                context.user_data['profile_data']["preferred_age_max"] = age

        await update.message.reply_text(
            "Укажите предпочитаемый город для поиска (или \"Любой\"):"
        )
        user_states[user_id] = REGISTER_PREFERRED_LOCATION
        context.user_data['state'] = REGISTER_PREFERRED_LOCATION
    except ValueError:
        await update.message.reply_text(
            "Неверный формат. Пожалуйста, укажите возрастной диапазон через дефис (например: 20-35) или одно число:"
        )


async def handle_preferred_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle preferred location input"""
    user_id = update.effective_user.id
    preferred_location = update.message.text.strip()

    if preferred_location.lower() == "любой":
        preferred_location = None

    user_data[user_id]["preferred_location"] = preferred_location
    if 'profile_data' in context.user_data:
        context.user_data['profile_data']["preferred_location"] = preferred_location

    await update.message.reply_text(
        "Отлично! Теперь загрузите вашу фотографию для анкеты:"
    )
    user_states[user_id] = UPLOAD_PHOTO
    context.user_data['state'] = UPLOAD_PHOTO


async def handle_browsing_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu options when in browsing state"""
    user_id = update.effective_user.id
    text = update.message.text

    logger.info(f"Menu selection for user {user_id}: '{text}', current state: {context.user_data.get('state', 'None')}")

    if text == "👀 Смотреть анкеты":
        await show_next_profile(update, context)
    elif text == "❤️ Мои пары":
        await show_matches(update, context)
    elif text == "👤 Моя анкета":
        await show_my_profile(update, context)
    else:
        await update.message.reply_text("Пожалуйста, используйте меню для навигации.")
        sync_user_state(user_id, context, BROWSING)

    logger.info(f"Menu handling complete, state now: {context.user_data.get('state', 'None')}")


async def handle_profile_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, profile_id: int):
    """Handle like or skip action"""
    query = update.callback_query
    user_id = query.from_user.id

    session = Session()
    try:
        user_profile = UserService.get_user_profile(session, user_id)

        if not user_profile or not user_profile.get("has_profile"):
            await query.answer("Сначала нужно создать анкету. Начните с команды /start.")
            return

        matching_service = MatchingService()

        if action == "like":
            result = matching_service.like_profile(session, user_profile["profile_id"], profile_id)

            if result.get("is_match"):
                other_profile = session.query(Profile).filter_by(id=profile_id).first()

                if not other_profile:
                    logger.error(f"Could not find profile {profile_id} for match notification")
                    await query.answer("Произошла ошибка. Попробуйте еще раз.")
                    return

                other_user = session.query(User).join(Profile).filter(
                    Profile.id == other_profile.id).first()

                await query.answer(f"У вас новая пара с {other_profile.name}!")

                keyboard = []

                if other_user and other_user.username:
                    keyboard = [
                        [InlineKeyboardButton("💬 Написать в Telegram", url=f"https://t.me/{other_user.username}")],
                        [InlineKeyboardButton("👀 Продолжить просмотр", callback_data="continue_browsing")]
                    ]
                else:
                    keyboard = [
                        [InlineKeyboardButton("⚠️ Нет username для связи", callback_data="no_username")],
                        [InlineKeyboardButton("👀 Продолжить просмотр", callback_data="continue_browsing")]
                    ]

                reply_markup = InlineKeyboardMarkup(keyboard)

                await context.bot.send_message(
                    user_id,
                    f"У вас новая пара! Вы и {other_profile.name} понравились друг другу.",
                    reply_markup=reply_markup
                )

                try:
                    if other_user:
                        this_user = session.query(User).filter(User.telegram_id == user_id).first()

                        other_match_keyboard = []
                        if this_user and this_user.username:
                            other_match_keyboard = [
                                [InlineKeyboardButton("💬 Написать в Telegram",
                                                      url=f"https://t.me/{this_user.username}")],
                                [InlineKeyboardButton("👀 Продолжить просмотр", callback_data="continue_browsing")]
                            ]
                        else:
                            other_match_keyboard = [
                                [InlineKeyboardButton("⚠️ Пользователь без username", callback_data="no_username")],
                                [InlineKeyboardButton("👀 Продолжить просмотр", callback_data="continue_browsing")]
                            ]

                        other_match_markup = InlineKeyboardMarkup(other_match_keyboard)

                        this_user_name = user_profile["name"]

                        await context.bot.send_message(
                            other_user.telegram_id,
                            f"📣 У вас новая пара! {this_user_name} также поставил(а) вам лайк!",
                            reply_markup=other_match_markup
                        )
                        logger.info(f"Sent match notification to user {other_user.telegram_id}")
                except Exception as e:
                    logger.error(f"Failed to send match notification to other user: {e}")

                if "current_profiles" in context.user_data and user_id in context.user_data["current_profiles"]:
                    del context.user_data["current_profiles"][user_id]

            else:
                await query.answer("Анкета понравилась!")

                if "current_profiles" in context.user_data and user_id in context.user_data["current_profiles"]:
                    del context.user_data["current_profiles"][user_id]

                await show_next_profile(update, context)
        else:
            matching_service.skip_profile(session, user_profile["profile_id"], profile_id)

            await query.answer("Анкета пропущена")

            if "current_profiles" in context.user_data and user_id in context.user_data["current_profiles"]:
                del context.user_data["current_profiles"][user_id]

            await show_next_profile(update, context)
    except Exception as e:
        logger.error(f"Error handling profile action: {e}")
        await query.answer("Произошла ошибка при обработке действия.")
    finally:
        session.close()


async def show_edit_profile_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the menu for editing profile"""
    query = update.callback_query
    user_id = query.from_user.id

    keyboard = [
        [InlineKeyboardButton("Имя", callback_data="edit_field_name")],
        [InlineKeyboardButton("Возраст", callback_data="edit_field_age")],
        [InlineKeyboardButton("О себе", callback_data="edit_field_bio")],
        [InlineKeyboardButton("Город", callback_data="edit_field_location")],
        [InlineKeyboardButton("Интересы", callback_data="edit_field_interests")],
        [InlineKeyboardButton("Возрастной диапазон", callback_data="edit_age_range")],
        [InlineKeyboardButton("Предпочитаемый город", callback_data="edit_location_pref")],
        [InlineKeyboardButton("Обновить фото", callback_data="add_photo")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        user_id,
        "Выберите, что вы хотите изменить в вашем профиле:",
        reply_markup=reply_markup
    )

    user_states[user_id] = EDIT_PROFILE
    context.user_data['state'] = EDIT_PROFILE


async def handle_edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edit name input"""
    user_id = update.effective_user.id
    name = update.message.text.strip()

    if len(name) < 2:
        await update.message.reply_text("Имя должно содержать минимум 2 символа. Пожалуйста, попробуйте еще раз:")
        return

    session = Session()
    try:
        user_profile = UserService.get_user_profile(session, user_id)

        if not user_profile or not user_profile.get("has_profile"):
            await update.message.reply_text("Профиль не найден. Начните с команды /start.")
            return

        profile_service = ProfileService()

        result = profile_service.update_profile(
            session,
            user_profile["profile_id"],
            {"name": name}
        )

        if result:
            await update.message.reply_text(f"Имя успешно обновлено на '{name}'!")
            await show_my_profile(update, context)
        else:
            await update.message.reply_text("Не удалось обновить имя. Пожалуйста, попробуйте позже.")

    except Exception as e:
        logger.error(f"Error in handle_edit_name: {e}")
        await update.message.reply_text(
            "Произошла ошибка при обновлении имени. Пожалуйста, попробуйте снова позже."
        )
    finally:
        session.close()
        user_states[user_id] = BROWSING
        context.user_data['state'] = BROWSING

async def handle_edit_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edit age input"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    try:
        age = int(text)
        if age < 18 or age > 100:
            await update.message.reply_text("Возраст должен быть от 18 до 100 лет. Пожалуйста, попробуйте еще раз:")
            return

        session = Session()
        try:
            user_profile = UserService.get_user_profile(session, user_id)

            if not user_profile or not user_profile.get("has_profile"):
                await update.message.reply_text("Профиль не найден. Начните с команды /start.")
                return

            profile_service = ProfileService()

            result = profile_service.update_profile(
                session,
                user_profile["profile_id"],
                {"age": age}
            )

            if result:
                await update.message.reply_text(f"Возраст успешно обновлен на {age}!")
                await show_my_profile(update, context)
            else:
                await update.message.reply_text("Не удалось обновить возраст. Пожалуйста, попробуйте позже.")

        except Exception as e:
            logger.error(f"Error in handle_edit_age: {e}")
            await update.message.reply_text(
                "Произошла ошибка при обновлении возраста. Пожалуйста, попробуйте снова позже."
            )
        finally:
            session.close()
            user_states[user_id] = BROWSING
            context.user_data['state'] = BROWSING

    except ValueError:
        await update.message.reply_text("Пожалуйста, введите возраст цифрами:")


async def handle_edit_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edit bio input"""
    user_id = update.effective_user.id
    bio = update.message.text.strip()

    if len(bio) < 10:
        await update.message.reply_text(
            "Описание должно содержать минимум 10 символов. Пожалуйста, попробуйте еще раз:")
        return

    session = Session()
    try:
        user_profile = UserService.get_user_profile(session, user_id)

        if not user_profile or not user_profile.get("has_profile"):
            await update.message.reply_text("Профиль не найден. Начните с команды /start.")
            return

        profile_service = ProfileService()

        result = profile_service.update_profile(
            session,
            user_profile["profile_id"],
            {"bio": bio}
        )

        if result:
            await update.message.reply_text("Описание успешно обновлено!")
            await show_my_profile(update, context)
        else:
            await update.message.reply_text("Не удалось обновить описание. Пожалуйста, попробуйте позже.")

    except Exception as e:
        logger.error(f"Error in handle_edit_bio: {e}")
        await update.message.reply_text(
            "Произошла ошибка при обновлении описания. Пожалуйста, попробуйте снова позже."
        )
    finally:
        session.close()
        user_states[user_id] = BROWSING
        context.user_data['state'] = BROWSING


async def handle_edit_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edit location input"""
    user_id = update.effective_user.id
    location = update.message.text.strip()

    if len(location) < 2:
        await update.message.reply_text("Пожалуйста, укажите корректное название города:")
        return

    session = Session()
    try:
        user_profile = UserService.get_user_profile(session, user_id)

        if not user_profile or not user_profile.get("has_profile"):
            await update.message.reply_text("Профиль не найден. Начните с команды /start.")
            return

        profile_service = ProfileService()

        result = profile_service.update_profile(
            session,
            user_profile["profile_id"],
            {"location": location}
        )

        if result:
            await update.message.reply_text(f"Город успешно обновлен на '{location}'!")
            await show_my_profile(update, context)
        else:
            await update.message.reply_text("Не удалось обновить город. Пожалуйста, попробуйте позже.")

    except Exception as e:
        logger.error(f"Error in handle_edit_location: {e}")
        await update.message.reply_text(
            "Произошла ошибка при обновлении города. Пожалуйста, попробуйте снова позже."
        )
    finally:
        session.close()
        user_states[user_id] = BROWSING
        context.user_data['state'] = BROWSING


async def handle_edit_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edit interests input"""
    user_id = update.effective_user.id
    interests_text = update.message.text.strip()

    if len(interests_text) < 3:
        await update.message.reply_text("Пожалуйста, укажите хотя бы один интерес:")
        return

    interests = [i.strip() for i in interests_text.split(",") if i.strip()]

    session = Session()
    try:
        user_profile = UserService.get_user_profile(session, user_id)

        if not user_profile or not user_profile.get("has_profile"):
            await update.message.reply_text("Профиль не найден. Начните с команды /start.")
            return

        profile_service = ProfileService()

        result = profile_service.update_profile(
            session,
            user_profile["profile_id"],
            {"interests": interests}
        )

        if result:
            await update.message.reply_text("Интересы успешно обновлены!")
            await show_my_profile(update, context)
        else:
            await update.message.reply_text("Не удалось обновить интересы. Пожалуйста, попробуйте позже.")

    except Exception as e:
        logger.error(f"Error in handle_edit_interests: {e}")
        await update.message.reply_text(
            "Произошла ошибка при обновлении интересов. Пожалуйста, попробуйте снова позже."
        )
    finally:
        session.close()
        user_states[user_id] = BROWSING
        context.user_data['state'] = BROWSING


async def handle_edit_preferred_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edit preferred gender input"""
    user_id = update.effective_user.id
    preferred_gender = update.message.text.strip()

    if preferred_gender not in ["Мужской", "Женский", "Любой"]:
        keyboard = [
            [KeyboardButton("Мужской"), KeyboardButton("Женский"), KeyboardButton("Любой")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Пожалуйста, выберите из предложенных вариантов:", reply_markup=reply_markup)
        return

    if preferred_gender == "Любой":
        preferred_gender = None

    session = Session()
    try:
        user_profile = UserService.get_user_profile(session, user_id)

        if not user_profile or not user_profile.get("has_profile"):
            await update.message.reply_text("Профиль не найден. Начните с команды /start.")
            return

        profile_service = ProfileService()

        result = profile_service.update_profile(
            session,
            user_profile["profile_id"],
            {"preferred_gender": preferred_gender}
        )

        if result:
            gender_display = preferred_gender if preferred_gender else "Любой"
            await update.message.reply_text(f"Предпочитаемый пол успешно обновлен на '{gender_display}'!")
            await show_my_profile(update, context)
        else:
            await update.message.reply_text("Не удалось обновить предпочитаемый пол. Пожалуйста, попробуйте позже.")

    except Exception as e:
        logger.error(f"Error in handle_edit_preferred_gender: {e}")
        await update.message.reply_text(
            "Произошла ошибка при обновлении предпочитаемого пола. Пожалуйста, попробуйте снова позже."
        )
    finally:
        session.close()
        user_states[user_id] = BROWSING
        context.user_data['state'] = BROWSING


async def direct_edit_age_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct method to edit age range preferences"""
    query = update.callback_query
    user_id = query.from_user.id

    session = Session()
    try:
        user_profile = UserService.get_user_profile(session, user_id)

        if not user_profile:
            await context.bot.send_message(user_id, "Профиль не найден. Используйте /start для создания профиля.")
            return

        min_age = user_profile['preferred_age_min']
        max_age = user_profile['preferred_age_max']
        current_range = f"{min_age}-{max_age}" if min_age != max_age else str(min_age)

        await context.bot.send_message(
            user_id,
            f"Текущий возрастной диапазон: {current_range}\n\n"
            f"Введите новый возрастной диапазон через дефис (например: 20-35) или одно число:"
        )

        user_states[user_id] = DIRECT_EDIT_AGE_RANGE
        context.user_data['state'] = DIRECT_EDIT_AGE_RANGE

    except Exception as e:
        logger.error(f"Error in direct_edit_age_range: {e}")
        await context.bot.send_message(
            user_id,
            "Произошла ошибка при загрузке данных. Пожалуйста, попробуйте позже."
        )
    finally:
        session.close()


async def direct_edit_location_pref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct method to edit location preferences"""
    query = update.callback_query
    user_id = query.from_user.id

    session = Session()
    try:
        user_profile = UserService.get_user_profile(session, user_id)

        if not user_profile:
            await context.bot.send_message(user_id, "Профиль не найден. Используйте /start для создания профиля.")
            return

        current_location = user_profile['preferred_location'] or "Любой"

        await context.bot.send_message(
            user_id,
            f"Текущий предпочитаемый город: {current_location}\n\n"
            f"Введите новый предпочитаемый город (или \"Любой\"):"
        )

        user_states[user_id] = DIRECT_EDIT_LOCATION
        context.user_data['state'] = DIRECT_EDIT_LOCATION

    except Exception as e:
        logger.error(f"Error in direct_edit_location_pref: {e}")
        await context.bot.send_message(
            user_id,
            "Произошла ошибка при загрузке данных. Пожалуйста, попробуйте позже."
        )
    finally:
        session.close()


async def handle_direct_age_range_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct age range edit input"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    try:
        if "-" in text:
            min_age, max_age = map(int, text.split("-"))

            if min_age < 18 or max_age > 100 or min_age > max_age:
                await update.message.reply_text(
                    "Пожалуйста, укажите корректный возрастной диапазон (от 18 до 100 лет):"
                )
                return

            preferred_age_min = min_age
            preferred_age_max = max_age
        else:
            age = int(text)
            if age < 18 or age > 100:
                await update.message.reply_text(
                    "Пожалуйста, укажите корректный возраст (от 18 до 100 лет):"
                )
                return

            preferred_age_min = age
            preferred_age_max = age

        session = Session()
        try:
            user_profile = UserService.get_user_profile(session, user_id)

            if not user_profile:
                await update.message.reply_text("Профиль не найден. Используйте /start для создания профиля.")
                return

            profile_service = ProfileService()

            result = profile_service.update_profile(
                session,
                user_profile["profile_id"],
                {
                    "preferred_age_min": preferred_age_min,
                    "preferred_age_max": preferred_age_max
                }
            )

            if result:
                age_display = f"{preferred_age_min}-{preferred_age_max}" if preferred_age_min != preferred_age_max else str(
                    preferred_age_min)
                await update.message.reply_text(f"✅ Возрастной диапазон успешно обновлен на {age_display}!")

                await show_my_profile(update, context)
            else:
                await update.message.reply_text(
                    "❌ Не удалось обновить возрастной диапазон. Пожалуйста, попробуйте позже.")
        except Exception as e:
            logger.error(f"Error updating age range: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обновлении. Пожалуйста, попробуйте позже.")
        finally:
            session.close()
            user_states[user_id] = BROWSING
            context.user_data['state'] = BROWSING

    except ValueError:
        await update.message.reply_text(
            "Неверный формат. Пожалуйста, укажите возрастной диапазон через дефис (например: 20-35) или одно число:"
        )


async def handle_direct_location_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct location preference edit input"""
    user_id = update.effective_user.id
    location = update.message.text.strip()

    preferred_location = None if location.lower() == "любой" else location

    session = Session()
    try:
        user_profile = UserService.get_user_profile(session, user_id)

        if not user_profile:
            await update.message.reply_text("Профиль не найден. Используйте /start для создания профиля.")
            return

        profile_service = ProfileService()

        result = profile_service.update_profile(
            session,
            user_profile["profile_id"],
            {
                "preferred_location": preferred_location
            }
        )

        if result:
            display_location = preferred_location or "Любой"
            await update.message.reply_text(f"✅ Предпочитаемый город успешно обновлен на {display_location}!")

            await show_my_profile(update, context)
        else:
            await update.message.reply_text("❌ Не удалось обновить предпочитаемый город. Пожалуйста, попробуйте позже.")
    except Exception as e:
        logger.error(f"Error updating preferred location: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обновлении. Пожалуйста, попробуйте позже.")
    finally:
        session.close()
        context.user_data['state'] = BROWSING


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle normal text messages based on user state"""
    user_id = update.effective_user.id
    text = update.message.text

    state = context.user_data.get('state') or user_states.get(user_id, BROWSING)
    context.user_data['state'] = state
    user_states[user_id] = state

    print(f"User {user_id} state: {state}")

    if state == REGISTER_NAME:
        await handle_name(update, context)
    elif state == REGISTER_AGE:
        await handle_age(update, context)
    elif state == REGISTER_GENDER:
        await handle_gender(update, context)
    elif state == REGISTER_BIO:
        await handle_bio(update, context)
    elif state == REGISTER_LOCATION:
        await handle_location(update, context)
    elif state == REGISTER_INTERESTS:
        await handle_interests(update, context)
    elif state == REGISTER_PREFERRED_AGE:
        await handle_preferred_age(update, context)
    elif state == REGISTER_PREFERRED_LOCATION:
        await handle_preferred_location(update, context)
    elif state == BROWSING:
        await handle_browsing_menu(update, context)
    elif state == EDIT_NAME:
        await handle_edit_name(update, context)
    elif state == EDIT_AGE:
        await handle_edit_age(update, context)
    elif state == EDIT_BIO:
        await handle_edit_bio(update, context)
    elif state == EDIT_LOCATION:
        await handle_edit_location(update, context)
    elif state == EDIT_INTERESTS:
        await handle_edit_interests(update, context)
    elif state == DIRECT_EDIT_AGE_RANGE:
        await handle_direct_age_range_edit(update, context)
    elif state == DIRECT_EDIT_LOCATION:
        await handle_direct_location_edit(update, context)
    else:
        session = Session()
        try:
            user_profile = UserService.get_user_profile(session, user_id)
            if user_profile and user_profile.get("has_profile"):
                user_states[user_id] = BROWSING
                context.user_data['state'] = BROWSING
                await update.message.reply_text("Восстанавливаем ваш профиль...")
                await show_main_menu(update, context)
            else:
                await update.message.reply_text(
                    "Извините, произошел сбой. Используйте /start, чтобы начать сначала."
                )
        except Exception as e:
            logger.error(f"Error while trying to recover user state: {e}")
            await update.message.reply_text(
                "Произошла ошибка. Используйте /start, чтобы начать сначала."
            )
        finally:
            session.close()


def sync_user_state(user_id, context, state=None):
    """Синхронизирует состояние пользователя между глобальным словарем и контекстом"""
    try:
        old_state = "None"
        if state is not None:
            old_state = context.user_data.get('state', 'Unknown')
            user_states[user_id] = state
            context.user_data['state'] = state
            logger.info(f"State change for user {user_id}: {old_state} -> {state}")
        elif user_id in user_states:
            old_state = context.user_data.get('state', 'Unknown')
            context.user_data['state'] = user_states[user_id]
            logger.info(f"Synced state from global to local for user {user_id}: {old_state} -> {user_states[user_id]}")
        elif 'state' in context.user_data:
            old_state = user_states.get(user_id, 'Unknown')
            user_states[user_id] = context.user_data['state']
            logger.info(f"Synced state from local to global for user {user_id}: {old_state} -> {context.user_data['state']}")
        else:
            old_state = "Unknown/None"
            user_states[user_id] = BROWSING
            context.user_data['state'] = BROWSING
            logger.info(f"Reset state to BROWSING for user {user_id} (was {old_state})")
    except Exception as e:
        logger.error(f"Error in sync_user_state for user {user_id}: {e}")
        user_states[user_id] = BROWSING
        context.user_data['state'] = BROWSING


async def handle_edit_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, field: str):
    """Handle selection of field to edit"""
    query = update.callback_query
    user_id = query.from_user.id

    session = Session()
    try:
        user_profile = UserService.get_user_profile(session, user_id)

        if not user_profile or not user_profile.get("has_profile"):
            await context.bot.send_message(user_id, "Профиль не найден. Начните с команды /start.")
            return

        if user_id not in user_data:
            user_data[user_id] = {}

        if field == "name":
            await context.bot.send_message(
                user_id,
                f"Текущее имя: {user_profile['name']}\n\nВведите новое имя:"
            )
            user_states[user_id] = EDIT_NAME
            context.user_data['state'] = EDIT_NAME

        elif field == "age":
            await context.bot.send_message(
                user_id,
                f"Текущий возраст: {user_profile['age']}\n\nВведите новый возраст:"
            )
            user_states[user_id] = EDIT_AGE
            context.user_data['state'] = EDIT_AGE

        elif field == "bio":
            await context.bot.send_message(
                user_id,
                f"Текущее описание:\n{user_profile['bio']}\n\nВведите новое описание:"
            )
            user_states[user_id] = EDIT_BIO
            context.user_data['state'] = EDIT_BIO

        elif field == "location":
            await context.bot.send_message(
                user_id,
                f"Текущий город: {user_profile['location']}\n\nВведите новый город:"
            )
            user_states[user_id] = EDIT_LOCATION
            context.user_data['state'] = EDIT_LOCATION

        elif field == "interests":
            interests_str = ", ".join(user_profile['interests'])
            await context.bot.send_message(
                user_id,
                f"Текущие интересы: {interests_str}\n\nВведите новые интересы через запятую:"
            )
            user_states[user_id] = EDIT_INTERESTS
            context.user_data['state'] = EDIT_INTERESTS

        elif field == "preferred_age":
            min_age = user_profile['preferred_age_min']
            max_age = user_profile['preferred_age_max']
            age_range = f"{min_age}-{max_age}" if min_age != max_age else str(min_age)

            await context.bot.send_message(
                user_id,
                f"Текущий предпочитаемый возрастной диапазон: {age_range}\n\n" +
                "Введите новый возрастной диапазон через дефис (например: 20-35):"
            )
            user_states[user_id] = EDIT_PREFERRED_AGE
            context.user_data['state'] = EDIT_PREFERRED_AGE

        elif field == "preferred_location":
            current_location = user_profile['preferred_location'] or "Любой"
            await context.bot.send_message(
                user_id,
                f"Текущий предпочитаемый город: {current_location}\n\n" +
                "Введите новый предпочитаемый город (или \"Любой\"):"
            )
            user_states[user_id] = EDIT_PREFERRED_LOCATION
            context.user_data['state'] = EDIT_PREFERRED_LOCATION

    except Exception as e:
        logger.error(f"Error in handle_edit_field_selection: {e}")
        await context.bot.send_message(
            user_id,
            "Произошла ошибка при загрузке данных профиля. Пожалуйста, попробуйте снова позже."
        )
    finally:
        session.close()


async def show_my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's own profile"""
    user_id = update.effective_user.id

    logger.info(f"Showing profile for user {user_id}, current state: {context.user_data.get('state', 'None')}")

    session = Session()
    try:
        user_profile = UserService.get_user_profile(session, user_id)

        if not user_profile or not user_profile.get("has_profile"):
            await update.message.reply_text(
                "Сначала нужно создать анкету. Начните с команды /start."
            )
            return

        profile_service = ProfileService()

        photos = profile_service.get_photos(session, user_profile["profile_id"])

        profile_text = (
            f"👤 {user_profile['name']}, {user_profile['age']}\n"
            f"📍 {user_profile['location']}\n\n"
            f"{user_profile['bio']}\n\n"
            f"Интересы: {', '.join(user_profile['interests'])}\n\n"
            f"Предпочтения:\n"
            f"- Пол: {user_profile['preferred_gender'] or 'Любой'}\n"
            f"- Возраст: {user_profile['preferred_age_min']}-{user_profile['preferred_age_max']}\n"
            f"- Город: {user_profile['preferred_location'] or 'Любой'}\n\n"
            f"Заполненность профиля: {int(user_profile['profile_completeness'] * 100)}%"
        )

        keyboard = [
            [InlineKeyboardButton("✏️ Редактировать анкету", callback_data="edit_profile")],
            # [InlineKeyboardButton("📷 Добавить фото", callback_data="add_photo")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message_to_send = None

        if photos and len(photos) > 0:
            main_photo = next((p for p in photos if p.get("is_main")), photos[0])

            photo_source = main_photo.get("telegram_file_id") or main_photo.get("url")

            if photo_source:
                try:
                    if hasattr(update, 'callback_query') and update.callback_query:
                        message_to_send = await update.callback_query.message.reply_photo(
                            photo_source,
                            caption=profile_text,
                            reply_markup=reply_markup
                        )
                    else:
                        message_to_send = await context.bot.send_photo(
                            user_id,
                            photo_source,
                            caption=profile_text,
                            reply_markup=reply_markup
                        )
                except Exception as e:
                    logger.error(f"Error sending photo: {e}")
                    if hasattr(update, 'callback_query') and update.callback_query:
                        message_to_send = await update.callback_query.message.reply_text(
                            profile_text + "\n\n⚠️ Не удалось загрузить фото",
                            reply_markup=reply_markup
                        )
                    else:
                        message_to_send = await update.message.reply_text(
                            profile_text + "\n\n⚠️ Не удалось загрузить фото",
                            reply_markup=reply_markup
                        )
            else:
                if hasattr(update, 'callback_query') and update.callback_query:
                    message_to_send = await update.callback_query.message.reply_text(
                        profile_text + "\n\n⚠️ Фото отсутствует или недоступно",
                        reply_markup=reply_markup
                    )
                else:
                    message_to_send = await update.message.reply_text(
                        profile_text + "\n\n⚠️ Фото отсутствует или недоступно",
                        reply_markup=reply_markup
                    )
        else:
            if hasattr(update, 'callback_query') and update.callback_query:
                message_to_send = await update.callback_query.message.reply_text(
                    profile_text + "\n\n📷 Добавьте фото к вашей анкете",
                    reply_markup=reply_markup
                )
            else:
                message_to_send = await update.message.reply_text(
                    profile_text + "\n\n📷 Добавьте фото к вашей анкете",
                    reply_markup=reply_markup
                )

        if message_to_send:
            context.user_data['last_profile_message'] = message_to_send.message_id

    except Exception as e:
        logger.error(f"Error showing my profile: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.message.reply_text(
                "Произошла ошибка при загрузке профиля. Пожалуйста, попробуйте снова позже."
            )
        else:
            await update.message.reply_text(
                "Произошла ошибка при загрузке профиля. Пожалуйста, попробуйте снова позже."
            )
    finally:
        session.close()
        sync_user_state(user_id, context, BROWSING)
        logger.info(f"Profile display completed, state set to: {context.user_data.get('state', 'None')}")


async def show_next_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the next profile to user"""
    user_id = update.effective_user.id

    logger.info(f"Showing next profile for user {user_id}, current state: {context.user_data.get('state', 'None')}")

    sync_user_state(user_id, context, VIEWING_PROFILE)

    session = Session()
    try:
        user = UserService.get_or_create_user(session, user_id)
        user_profile = UserService.get_user_profile(session, user_id)

        if not user_profile or not user_profile.get("has_profile"):
            message_text = "Сначала нужно создать анкету. Начните с команды /start."
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.message.reply_text(message_text)
            else:
                await update.message.reply_text(message_text)
            sync_user_state(user_id, context, BROWSING)
            return

        matching_service = MatchingService()

        matching_service.redis_client.delete_profile_list(user_id)

        profiles = matching_service.get_next_profiles(session, user.id, 2)

        if not profiles:
            keyboard = [
                [InlineKeyboardButton("🔄 Пересмотреть настройки", callback_data="edit_preferences")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            message_text = "Упс! Пока нет подходящих анкет. Попробуйте изменить параметры поиска или зайти позже."
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.message.reply_text(message_text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(message_text, reply_markup=reply_markup)

            sync_user_state(user_id, context, BROWSING)
            return

        profile = profiles[0]

        if "current_profiles" not in context.user_data:
            context.user_data["current_profiles"] = {}

        context.user_data["current_profiles"][user_id] = profile

        profile_service = ProfileService()
        profile_data = profile_service.get_profile(session, profile["id"])

        if not profile_data:
            message_text = "Ошибка при загрузке анкеты. Попробуйте еще раз."
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.message.reply_text(message_text)
            else:
                await update.message.reply_text(message_text)

            sync_user_state(user_id, context, BROWSING)
            return

        caption = (
            f"👤 {profile_data['name']}, {profile_data['age']}\n"
            f"📍 {profile_data.get('location', 'Не указано')}\n\n"
            f"{profile_data.get('bio', '')}\n\n"
            f"Интересы: {', '.join(profile_data.get('interests', []))}"
        )

        keyboard = [
            [
                InlineKeyboardButton("👎 Пропустить", callback_data=f"skip_{profile['id']}"),
                InlineKeyboardButton("❤️ Нравится", callback_data=f"like_{profile['id']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        photos = profile_service.get_photos(session, profile["id"])
        photo_sent = False

        if photos and len(photos) > 0:
            main_photo = next((p for p in photos if p.get("is_main")), photos[0])

            if main_photo and "url" in main_photo and main_photo["url"]:
                try:
                    if hasattr(update, 'callback_query') and update.callback_query:
                        await update.callback_query.message.reply_photo(
                            main_photo["url"],
                            caption=caption,
                            reply_markup=reply_markup
                        )
                    else:
                        await context.bot.send_photo(
                            user_id,
                            main_photo["url"],
                            caption=caption,
                            reply_markup=reply_markup
                        )
                    photo_sent = True
                except Exception as e:
                    logger.error(f"Error sending profile photo: {e}")

        if not photo_sent:
            text = caption + "\n\n⚠️ Фото недоступно"

            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(text, reply_markup=reply_markup)

        sync_user_state(user_id, context, VIEWING_PROFILE)
        logger.info(f"Next profile shown, state set to: {context.user_data.get('state', 'None')}")

    except Exception as e:
        logger.error(f"Error showing next profile: {e}")
        message_text = "Произошла ошибка при загрузке анкеты. Пожалуйста, попробуйте снова позже."

        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.message.reply_text(message_text)
        else:
            await update.message.reply_text(message_text)

        sync_user_state(user_id, context, BROWSING)
    finally:
        session.close()


async def restore_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Восстанавливает сессию пользователя"""
    user_id = update.effective_user.id

    logger.info(f"Attempting to restore session for user {user_id}")

    session = Session()
    try:
        user_profile = UserService.get_user_profile(session, user_id)

        if user_profile and user_profile.get("has_profile"):
            sync_user_state(user_id, context, BROWSING)

            if 'current_chat' in context.user_data:
                del context.user_data['current_chat']

            if 'last_profile_message' in context.user_data:
                del context.user_data['last_profile_message']

            await update.message.reply_text("✅ Сессия восстановлена!")
            await show_main_menu(update, context)
        else:
            await update.message.reply_text(
                "⚠️ Не удалось восстановить сессию. Используйте /start для создания профиля."
            )
    except Exception as e:
        logger.error(f"Error restoring session for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при восстановлении сессии. Используйте /start, чтобы начать сначала."
        )
    finally:
        session.close()


async def show_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's matches with pagination"""
    user_id = update.effective_user.id

    user_states[user_id] = VIEWING_MATCHES
    context.user_data['state'] = VIEWING_MATCHES

    page = context.user_data.get('matches_page', 0)

    if hasattr(update, 'callback_query') and update.callback_query:
        callback_data = update.callback_query.data
        if callback_data == "match_next":
            page += 1
        elif callback_data == "match_prev":
            page = max(0, page - 1)
        elif callback_data.startswith("init_chat_"):
            parts = callback_data.split("_")
            if len(parts) >= 3:
                match_id = int(parts[2])

                session = Session()
                try:
                    match = session.query(Match).filter_by(id=match_id).first()
                    if match and not match.initiated_chat:
                        match.initiated_chat = True
                        session.commit()
                        logger.info(f"Chat initiated for match {match_id} by user {user_id}")
                        await update.callback_query.answer("Диалог отмечен как начатый!")

                except Exception as e:
                    logger.error(f"Error marking chat as initiated: {e}")
                    await update.callback_query.answer("Ошибка при отметке диалога.")
                finally:
                    session.close()

    context.user_data['matches_page'] = page

    session = Session()
    try:
        user_profile = UserService.get_user_profile(session, user_id)

        if not user_profile or not user_profile.get("has_profile"):
            message_text = "Сначала нужно создать анкету. Начните с команды /start."
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.message.edit_text(message_text)
            else:
                await update.message.reply_text(message_text)
            sync_user_state(user_id, context, BROWSING)
            return

        matching_service = MatchingService()

        matches = matching_service.get_matches(session, user_profile["profile_id"])

        if not matches:
            message_text = "У вас пока нет пар. Продолжайте просматривать анкеты, чтобы найти совпадения!"
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.message.edit_text(message_text)
            else:
                await update.message.reply_text(message_text)
            sync_user_state(user_id, context, BROWSING)
            return

        context.user_data['matches'] = matches

        if page >= len(matches):
            page = 0
            context.user_data['matches_page'] = 0

        match = matches[page]
        other_profile = match["other_profile"]
        match_id = match["match_id"]

        profile_service = ProfileService()

        keyboard = []

        other_user = session.query(User).join(Profile).filter(
            Profile.id == other_profile.get('id')).first()

        if other_user and other_user.username:
            keyboard.append([
                InlineKeyboardButton(
                    "💬 Написать в Telegram",
                    url=f"https://t.me/{other_user.username}"
                )
            ])

            if not match.get("initiated_chat", False):
                keyboard.append([
                    InlineKeyboardButton(
                        "✅ Отметить диалог начатым",
                        callback_data=f"init_chat_{match_id}"
                    )
                ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    "⚠️ Нет username для связи",
                    callback_data="no_username"
                )
            ])

        navigation_buttons = []

        if page > 0:
            navigation_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="match_prev"))

        navigation_buttons.append(InlineKeyboardButton(f"{page + 1}/{len(matches)}", callback_data="match_count"))

        if page < len(matches) - 1:
            navigation_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data="match_next"))

        keyboard.append(navigation_buttons)

        reply_markup = InlineKeyboardMarkup(keyboard)

        chat_status = "✅ Диалог начат" if match.get("initiated_chat", False) else "⏳ Диалог не начат"

        name = other_profile.get('name', 'Без имени')
        age = other_profile.get('age', '')
        location = 'Не указано'

        if 'location' in other_profile:
            location = other_profile['location']
        else:
            try:
                full_profile = profile_service.get_profile(session, other_profile.get('id'))
                if full_profile and 'location' in full_profile:
                    location = full_profile.get('location')
            except Exception as e:
                logger.error(f"Error fetching full profile: {e}")

        match_text = (
            f"👤 {name}, {age}\n"
            f"📍 {location}\n"
            f"Совпадение: {match['created_at'].split('T')[0]}\n"
            f"{chat_status}"
        )

        photo_sent = False

        try:
            photos = profile_service.get_photos(session, other_profile.get('id'))

            if photos and len(photos) > 0:
                main_photo = next((p for p in photos if p.get("is_main")), photos[0])

                if main_photo and "url" in main_photo and main_photo["url"]:
                    if hasattr(update, 'callback_query') and update.callback_query:
                        try:
                            await update.callback_query.message.delete()
                            await context.bot.send_photo(
                                user_id,
                                main_photo["url"],
                                caption=match_text,
                                reply_markup=reply_markup
                            )
                        except Exception as e:
                            logger.error(f"Error updating match photo: {e}")
                            await context.bot.send_photo(
                                user_id,
                                main_photo["url"],
                                caption=match_text,
                                reply_markup=reply_markup
                            )
                    else:
                        await context.bot.send_photo(
                            user_id,
                            main_photo["url"],
                            caption=match_text,
                            reply_markup=reply_markup
                        )
                    photo_sent = True
        except Exception as e:
            logger.error(f"Error processing match photo: {e}")

        if not photo_sent:
            text = match_text + "\n\n⚠️ Фото недоступно"

            if hasattr(update, 'callback_query') and update.callback_query:
                try:
                    await update.callback_query.message.edit_text(text, reply_markup=reply_markup)
                except Exception as e:
                    logger.error(f"Error updating match text: {e}")
                    await context.bot.send_message(user_id, text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(text, reply_markup=reply_markup)

        sync_user_state(user_id, context, VIEWING_MATCHES)

    except Exception as e:
        logger.error(f"Error showing matches: {e}")
        message_text = "Произошла ошибка при загрузке пар. Пожалуйста, попробуйте снова позже."

        if hasattr(update, 'callback_query') and update.callback_query:
            try:
                await update.callback_query.message.edit_text(message_text)
            except:
                await context.bot.send_message(user_id, message_text)
        else:
            await update.message.reply_text(message_text)

        sync_user_state(user_id, context, BROWSING)
    finally:
        session.close()


async def check_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущее состояние пользователя"""
    user_id = update.effective_user.id

    local_state = context.user_data.get('state', 'Not set')
    global_state = user_states.get(user_id, 'Not set')

    state_info = (
        f"Информация о состоянии:\n"
        f"- Локальное состояние: {local_state}\n"
        f"- Глобальное состояние: {global_state}\n"
    )

    await update.message.reply_text(state_info)
    logger.info(f"State check for user {user_id}: local={local_state}, global={global_state}")


def get_user_state(user_id, context):
    """Безопасно получает состояние пользователя, восстанавливая его при необходимости"""
    state = context.user_data.get('state')

    if state is None:
        state = user_states.get(user_id)

    if state is None:
        state = BROWSING
        user_states[user_id] = state
        context.user_data['state'] = state
        logger.info(f"Recovered missing state for user {user_id}, setting to BROWSING")
    else:
        user_states[user_id] = state
        context.user_data['state'] = state

    return state


def main():
    """Start the bot"""
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("restore", restore_session))
    application.add_handler(CommandHandler("state", check_state))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(handle_button))

    application.add_error_handler(error_handler)

    logger.info("Dating Bot is starting")

    application.run_polling()

    logger.info("Dating Bot stopped")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки и отправляет сообщение пользователю"""
    try:
        error = context.error

        logger.error(f"Exception while handling an update: {error}", exc_info=context.error)

        user_id = None
        if update.effective_user:
            user_id = update.effective_user.id

        if isinstance(error, BadRequest) and "message to edit not found" in str(error).lower():
            return

        if user_id:
            await context.bot.send_message(
                user_id,
                "Произошла ошибка при обработке запроса. Пожалуйста, попробуйте еще раз или используйте /start."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")


if __name__ == "__main__":
    main()