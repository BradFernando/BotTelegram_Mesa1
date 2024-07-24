import logging
import asyncio
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, func
import threading
from dotenv import load_dotenv
import os
import json

# Load environment variables from .env file
load_dotenv()

# Load responses from JSON file
with open("text/responses.json", "r", encoding="utf-8") as f:
    responses = json.load(f)

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


# Database model for Product
class Product(Base):
    __tablename__ = 'Product'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(Numeric(10, 2), index=True)  # Changed String to Numeric
    image = Column(String)
    categoryId = Column(Integer, ForeignKey('Category.id'))

    # Define the relationship with OrderProducts
    orders = relationship("OrderProducts", back_populates="product")


# Database model for Order
class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    order_products = relationship("OrderProducts", back_populates="order")


# Database model for OrderProducts
class OrderProducts(Base):
    __tablename__ = 'OrderProducts'
    id = Column(Integer, primary_key=True)
    orderId = Column(Integer, ForeignKey('orders.id'))
    productId = Column(Integer, ForeignKey('Product.id'))
    quantity = Column(Integer)

    # Define relationships
    order = relationship("Order", back_populates="order_products")
    product = relationship("Product", back_populates="orders")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a greeting message followed by inline buttons."""
    logger.info("Handling /start command")
    if isinstance(update, Update) and update.message:
        user_first_name = update.message.from_user.first_name
        chat_id = update.message.chat_id
    elif isinstance(update, Update) and update.callback_query:
        user_first_name = update.callback_query.from_user.first_name
        chat_id = update.callback_query.message.chat_id
    else:
        logger.warning("Update does not have message or callback_query")
        return  # Exit if neither condition is met

    bot_name = "BotMesero"
    greeting = get_greeting()
    greeting_message = responses["greeting_message"].format(user_first_name=user_first_name, chat_id=chat_id)

    if isinstance(update, Update) and update.message:
        await update.message.reply_text(greeting_message, parse_mode='Markdown')
    elif isinstance(update, Update) and update.callback_query:
        await update.callback_query.message.edit_text(greeting_message, parse_mode='Markdown')

    keyboard = [
        [InlineKeyboardButton("Cuál es el menú de hoy 📋", callback_data="menu")],
        [InlineKeyboardButton("Cómo puedo realizar un pedido 📑❓", callback_data="pedido")],
        [InlineKeyboardButton("Preguntas acerca del Bot 🤖⁉", callback_data="otros")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if isinstance(update, Update) and update.message:
        await update.message.reply_text(responses["menu_message"], reply_markup=reply_markup)
    elif isinstance(update, Update) and update.callback_query:
        await update.callback_query.message.edit_text(responses["menu_message"], reply_markup=reply_markup)


def get_otros_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for 'Preguntas acerca del Bot'."""
    keyboard = [
        [InlineKeyboardButton("¿Cuánto tiempo demora en llegar mi pedido? ⏳", callback_data="tiempo_pedido")],
        [InlineKeyboardButton("¿Cuál es el producto más pedido de este establecimiento? 📊",
                              callback_data="producto_mas_pedido")],
        [InlineKeyboardButton("Puse mal una orden ¿Qué puedo hacer? 😬❓", callback_data="orden_mal")],
        [InlineKeyboardButton("El aplicativo no abre. 😖", callback_data="app_no_abre")],
        [InlineKeyboardButton("Sobre la información Proporcionada 🤔:", callback_data="info_proporcionada")],
        [InlineKeyboardButton("Regresar al Inicio ↩", callback_data="return_start")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    await query.answer()

    logger.info(f"Callback data received: {query.data}")

    if query.data == "menu":
        await show_categories(query)
    elif query.data.startswith("category_"):
        category_id = int(query.data.split("_")[1])
        await show_products(query, category_id)
    elif query.data == "pedido":
        response = responses["pedido_response"]
        keyboard = [[InlineKeyboardButton("Regresar al Inicio ↩", callback_data="return_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=response, reply_markup=reply_markup)
    elif query.data == "otros":
        reply_markup = get_otros_keyboard()
        await query.edit_message_text(text=responses["other_questions_message"], reply_markup=reply_markup)
    elif query.data == "tiempo_pedido":
        response = responses["tiempo_pedido_response"]
        keyboard = [[InlineKeyboardButton("Regresar a las Preguntas ↩", callback_data="return_otros")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=response, reply_markup=reply_markup)
    elif query.data == "producto_mas_pedido":
        await show_most_ordered_product(query)
    elif query.data == "orden_mal":
        response = responses["orden_mal_response"]
        keyboard = [[InlineKeyboardButton("Regresar a las Preguntas ↩", callback_data="return_otros")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=response, reply_markup=reply_markup)
    elif query.data == "app_no_abre":
        response = responses["app_no_abre_response"]
        keyboard = [[InlineKeyboardButton("Regresar a las Preguntas ↩", callback_data="return_otros")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=response, reply_markup=reply_markup)
    elif query.data == "info_proporcionada":
        response = responses["info_proporcionada_response"]
        keyboard = [[InlineKeyboardButton("Regresar a las Preguntas ↩", callback_data="return_otros")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=response, reply_markup=reply_markup)
    elif query.data == "return_start":
        await start(update, context)
    elif query.data == "return_otros":
        reply_markup = get_otros_keyboard()
        await query.edit_message_text(text=responses["other_questions_message"], reply_markup=reply_markup)
    elif query.data == "return_categories":
        logger.info("Returning to categories")
        await show_categories(query)


async def show_categories(query: Update.callback_query):
    """Fetches categories from the database and shows them as inline buttons."""
    logger.info("Fetching categories from the database")
    async with SessionLocal() as session:
        async with session.begin():
            categories = (await session.execute(select(Category))).scalars().all()
            logger.info(f"Found categories: {categories}")

    if not categories:
        await query.edit_message_text(text="No hay categorías disponibles.")
        return

    keyboard = []
    for category in categories:
        keyboard.append([InlineKeyboardButton(category.name, callback_data=f"category_{category.id}")])

    keyboard.append([InlineKeyboardButton("Regresar al Inicio ⬆️", callback_data="return_start")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Selecciona una categoría:", reply_markup=reply_markup)


async def show_products(query: Update.callback_query, category_id: int) -> None:
    """Fetches products for a given category and shows them as inline buttons."""
    logger.info(f"Fetching products for category_id: {category_id}")
    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(select(Product).where(Product.categoryId == category_id))
            products = result.scalars().all()
            logger.info(f"Found products: {products}")

    if not products:
        await query.edit_message_text(text="No hay productos disponibles en esta categoría.")
        return

    keyboard = []
    for product in products:
        # Include product price in the button text
        button_text = f"{product.name} - ${product.price:.2f}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"product_{product.id}")])

    keyboard.append([InlineKeyboardButton("Regresar a las Categorías ⬆️", callback_data="return_categories")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Elige un producto:", reply_markup=reply_markup)


async def show_most_ordered_product(query: Update.callback_query) -> None:
    """Fetches the most ordered product from the database and shows it."""
    logger.info("Fetching the most ordered product from the database")

    try:
        async with SessionLocal() as session:
            async with session.begin():
                stmt = (
                    select(Product.name, func.sum(OrderProducts.quantity).label("total_quantity"))
                    .join(OrderProducts, Product.id == OrderProducts.productId)  # Join Product and OrderProducts
                    .group_by(Product.name)  # Group by product name
                    .order_by(func.sum(OrderProducts.quantity).desc())  # Order by total quantity descending
                    .limit(1)  # Limit the result to 1 (the most ordered)
                )
                result = await session.execute(stmt)
                most_ordered = result.first()

                # Verify if a result was found
                if most_ordered:
                    product_name, total_quantity = most_ordered
                    response = f"El producto más pedido es: {product_name} con un total de {total_quantity} pedidos."
                else:
                    response = "No se encontraron pedidos."

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        response = "Ocurrió un error al procesar la solicitud."

    # Create the keyboard with a button to return
    keyboard = [[InlineKeyboardButton("Regresar a las Preguntas ↩", callback_data="return_otros")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Edit the user's message with the response and the keyboard
    await query.edit_message_text(text=response, reply_markup=reply_markup)


def run_bot(application: Application) -> None:
    """Runs the bot using an event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    application.run_polling()


async def main() -> None:
    """Start the bot."""
    logger.info("Starting the bot")
    bot_token_1 = os.getenv("BOT_TOKEN_1")
    bot_token_2 = os.getenv("BOT_TOKEN_2")
    bot_token_3 = os.getenv("BOT_TOKEN_3")

    if not bot_token_1 or not bot_token_2 or not bot_token_3:
        logger.error("Bot tokens are not set. Please check your .env file.")
        return

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
