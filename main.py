import logging
import asyncio
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String
import threading
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# Function to get the greeting based on the current time
def get_greeting() -> str:
    current_hour = datetime.now().hour
    if 5 <= current_hour < 12:
        return "Buenos días"
    elif 12 <= current_hour < 18:
        return "Buenas tardes"
    else:
        return "Buenas noches"


# Database model for Category
class Category(Base):
    __tablename__ = 'Category'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    slug = Column(String, index=True)
    #products = Column(String, index=True)  # Assuming 'products' is a string, update if it's another type


# Database model for Product
class Product(Base):
    __tablename__ = 'Product'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(String, index=True)
    image = Column(String)
    categoryId = Column(Integer, index=True)
    #category = Column(String)
    #orderItems = Column(String)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a greeting message followed by inline buttons."""
    if isinstance(update, Update) and update.message:
        user_first_name = update.message.from_user.first_name
        chat_id = update.message.chat_id
    elif isinstance(update, Update) and update.callback_query:
        user_first_name = update.callback_query.from_user.first_name
        chat_id = update.callback_query.message.chat_id
    else:
        return  # Exit if neither condition is met

    bot_name = "BotMesero"
    greeting = get_greeting()
    greeting_message = (
        f"{greeting}, {user_first_name}. Me llamo {bot_name}, estoy aquí para ayudarte en la toma de pedidos el día "
        f"de hoy. Para poder avanzar, permíteme mostrarte la ID de este chat: \n\n{chat_id}\n\nNecesito que la "
        f"guardes para"
        f" el momento que uses el aplicativo.🤖🦾"
    )

    if isinstance(update, Update) and update.message:
        await update.message.reply_text(greeting_message, parse_mode='Markdown')
    elif isinstance(update, Update) and update.callback_query:
        await update.callback_query.message.edit_text(greeting_message, parse_mode='Markdown')

    keyboard = [
        [
            InlineKeyboardButton("Cuál es el menú de hoy 📋", callback_data="menu")
        ],
        [
            InlineKeyboardButton("Cómo puedo realizar un pedido 📑❓", callback_data="pedido")
        ],
        [
            InlineKeyboardButton("Preguntas acerca del Bot 🤖⁉️", callback_data="otros")
        ],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if isinstance(update, Update) and update.message:
        await update.message.reply_text("Para poder avanzar, elige una opción ⬇️:", reply_markup=reply_markup)
    elif isinstance(update, Update) and update.callback_query:
        await update.callback_query.message.edit_text("Para poder avanzar, elige una opción:",
                                                      reply_markup=reply_markup)


def get_otros_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for 'Preguntas acerca del Bot'."""
    keyboard = [
        [InlineKeyboardButton("¿Cuánto tiempo demora en llegar mi pedido? ⏳", callback_data="tiempo_pedido")],
        [InlineKeyboardButton("¿Cuál es el producto más pedido de este establecimiento? 📊",
                              callback_data="producto_mas_pedido")],
        [InlineKeyboardButton("Puse mal una orden ¿Qué puedo hacer? 😬❓", callback_data="orden_mal")],
        [InlineKeyboardButton("El aplicativo no abre. 😖", callback_data="app_no_abre")],
        [InlineKeyboardButton("Sobre la información Proporcionada 🤔:", callback_data="info_proporcionada")],
        [InlineKeyboardButton("Regresar al Inicio ↩️", callback_data="return_start")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    await query.answer()

    if query.data == "menu":
        await show_categories(query)
    elif query.data.startswith("category_"):
        category_id = int(query.data.split("_")[1])
        await show_products(query, category_id)
    elif query.data == "pedido":
        response = (
            "Para realizar un pedido, usarás una MiniApp 🥸📲:\n"
            "1. En la esquina inferior izquierda alado de la caja de envio de mensajes encontrarás un botón de Menú.\n"
            "2. El boton de llevará la ventana del menu donde esogerás todos los pedidos que desees o requieras.\n"
            "3. Deberás tener en cuenta el valor del pago en los pedidos asi que se cuidadoso de no pasarte de tu presupuesto.\n"
            "4. Al momento de enviar los pedidos en caja analizarán tu pedido procura ser paciente.\n"
            "5. Si tu pago es en transferencia el cajero analizará el comprobante de pago que hayas cargado, recuerda debe ser una captura de pantalla clara y legible, si lo haces mal deberás repetir tu pedido.\n"
            "6. Si tu pago es en efectivo puedes acercarte en caja a pagar, informa al cajero cual es tu ID, y si tienes alguna pregunta realizala."
        )
        keyboard = [[InlineKeyboardButton("Regresar al Inicio ↩️", callback_data="return_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=response, reply_markup=reply_markup)
    elif query.data == "otros":
        reply_markup = get_otros_keyboard()
        await query.edit_message_text(text="Preguntas acerca del Bot 🤖⁉️:", reply_markup=reply_markup)
    elif query.data == "tiempo_pedido":
        response = (
            "Tu pedido demorará dependiendo la complejidad de la preparación del mismo no puede sobrepasar los 15 minutos "
            "si algo sucede informa algun encargado del establecimiento."
        )
        keyboard = [[InlineKeyboardButton("Regresar a las Preguntas ↩️", callback_data="return_otros")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=response, reply_markup=reply_markup)
    elif query.data == "producto_mas_pedido":
        response = "Aquí quiero que lo dejes vacío porque esto lo haré con la BDD."
        keyboard = [[InlineKeyboardButton("Regresar a las Preguntas ↩️", callback_data="return_otros")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=response, reply_markup=reply_markup)
    elif query.data == "orden_mal":
        response = (
            "Tus ordenes se reciben y tienes un rango de 5 minutos para realizar el pago sino el tiempo se considerará como "
            "excedido y el cajero eliminará tu orden, deberás crear otra nuevamente."
        )
        keyboard = [[InlineKeyboardButton("Regresar a las Preguntas ↩️", callback_data="return_otros")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=response, reply_markup=reply_markup)
    elif query.data == "app_no_abre":
        response = (
            "Si la aplicación no abre, verifica que tienes conexión a Internet y que tienes la última versión instalada."
        )
        keyboard = [[InlineKeyboardButton("Regresar a las Preguntas ↩️", callback_data="return_otros")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=response, reply_markup=reply_markup)
    elif query.data == "info_proporcionada":
        response = (
            "Se proporciona información básica para poder ayudarte en lo que necesites, si requieres más ayuda contacta a un"
            " encargado del establecimiento."
        )
        keyboard = [[InlineKeyboardButton("Regresar a las Preguntas ↩️", callback_data="return_otros")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=response, reply_markup=reply_markup)
    elif query.data == "return_start":
        await start(update, context)
    elif query.data == "return_otros":
        reply_markup = get_otros_keyboard()
        await query.edit_message_text(text="Preguntas acerca del Bot 🤖⁉️:", reply_markup=reply_markup)


async def show_categories(query: Update.callback_query):
    """Fetches categories from the database and shows them as inline buttons."""
    async with SessionLocal() as session:
        async with session.begin():
            categories = (await session.execute(select(Category))).scalars().all()
            keyboard = [
                [InlineKeyboardButton(category.name, callback_data=f"category_{category.id}")]
                for category in categories
            ]
            # Add the return button at the end
            keyboard.append([InlineKeyboardButton("Regresar al Inicio", callback_data="return_start")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text="Elige una categoría:", reply_markup=reply_markup)


async def show_products(query: Update, category_id: int) -> None:
    """Fetches products for a category from the database and displays them as buttons."""
    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(select(Product).where(Product.categoryId == category_id))
            products = result.scalars().all()

    if not products:
        await query.edit_message_text("No se encontraron productos para esta categoría. 😔")
        return

    keyboard = [
        [InlineKeyboardButton(f"{product.name} - ${product.price}", callback_data=f"product_{product.id}")]
        for product in products
    ]

    # Add the return to categories button
    keyboard.append(
        [InlineKeyboardButton("Regresar a las categorías", callback_data="return_start")])  # Cambiado a "return_start"

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Selecciona un producto ⬇️:", reply_markup=reply_markup)


def run_bot(application: Application) -> None:
    """Run the bot in its own event loop."""
    asyncio.set_event_loop(asyncio.new_event_loop())
    application.run_polling()


async def main() -> None:
    """Start the bot."""
    bot_token_1 = os.getenv("BOT_TOKEN_1")
    bot_token_2 = os.getenv("BOT_TOKEN_2")
    bot_token_3 = os.getenv("BOT_TOKEN_3")

    # Create application instances for each bot
    application_1 = Application.builder().token(bot_token_1).build()
    application_2 = Application.builder().token(bot_token_2).build()
    application_3 = Application.builder().token(bot_token_3).build()

    # Add handlers to the first bot
    application_1.add_handler(CommandHandler("start", start))
    application_1.add_handler(CallbackQueryHandler(button))

    # Add handlers to the second bot
    application_2.add_handler(CommandHandler("start", start))
    application_2.add_handler(CallbackQueryHandler(button))

    # Add handlers to the third bot
    application_3.add_handler(CommandHandler("start", start))
    application_3.add_handler(CallbackQueryHandler(button))

    # Start the bots using threading
    threading.Thread(target=run_bot, args=(application_1,), daemon=True).start()
    threading.Thread(target=run_bot, args=(application_2,), daemon=True).start()
    threading.Thread(target=run_bot, args=(application_3,), daemon=True).start()

    # Keep the main thread alive
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
