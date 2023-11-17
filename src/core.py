from telegram import *
from telegram.ext import *
from telegram._utils.types import ReplyMarkup

import asyncio
import logging
import os 
import sys
from random import randint
from datetime import datetime

# TODO: Dumbest way to grab image, because we need to cleanup all cached images 
#       And send it to user 
#       Grabing URL will be better

from icrawler.builtin import GoogleImageCrawler

class botcore:
    TG_BOT_TOKEN = os.getenv("AIS_TOKEN")

    states: dict[int, list] = { }
    STATE_START, STATE_SEARCH, STATE_EXIT = range(3)
    
    message_handler = None
    message_handler_state = 0

    # TODO: Add user prefix to folder 
    DATA_FOLDER_NAME = "data"
    # TODO: Will be saved in user data 
    search_request = ""


    def start(self) -> None:
        # initialize logger 
        self.init_logger()

        logging.log(logging.INFO, "Run bot core...")
        
        # Add token and build our app 
        self.application = ApplicationBuilder().token(self.TG_BOT_TOKEN).build()

        # Create the ConversationHandler to handle events 
        self.conversationHandler = ConversationHandler(
            # Set entry point
            entry_points=[CommandHandler("start", self.event_on_start)],
            states = self.states,
            fallbacks=[],
        )
        self.application.add_handler(self.conversationHandler)

        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    def init_logger(self):
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
        logging.getLogger("httpx").setLevel(logging.WARNING) # Remove "httpx" INFO messages

        LOG_FOLDER_NAME = "Logs"
        # Create folder if it not exist 
        if not os.path.exists(LOG_FOLDER_NAME):
            os.makedirs(LOG_FOLDER_NAME)

        # Create log file    
        LOG_FILE_NAME_ROOT = f"{LOG_FOLDER_NAME}\\root-{datetime.now().year}-{datetime.now().month}-{datetime.now().day}-{datetime.now().hour}-{datetime.now().minute}-{datetime.now().second}.log"

        f = open(os.path.join(os.getcwd(), LOG_FILE_NAME_ROOT) , 'w+') 
        f.write('gamebotgpt log file:\n')
        f.close()
        
        fh = logging.FileHandler(LOG_FILE_NAME_ROOT)
        fh.setLevel(logging.INFO)
        logging.getLogger("root").addHandler(fh)

    async def event_on_cancel(self, update: Update, context: ContextTypes = ContextTypes.DEFAULT_TYPE) -> int:
        logging.log(logging.INFO, "Switch to event_on_cancel")
        
        await update.message.reply_text("Пока! Если же ты хочешь начать снова работу, введи команду \start")
        return ConversationHandler.END

    async def event_on_start(self, update: Update, context: ContextTypes = ContextTypes.DEFAULT_TYPE) -> int:
        logging.log(logging.INFO, "Switch to event_on_start")
        
        # TODO: Make it more informative 
        WELCOME_TEXT: str = "Привет, это бот который позволяет искать любые картинки в стиле аниме."

        # Send start message         
        startScreenKeyboardMarkup = ReplyKeyboardMarkup([["Начать", "Отмена"]], one_time_keyboard=True, resize_keyboard=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text = WELCOME_TEXT, reply_markup=startScreenKeyboardMarkup)
        self.states[self.STATE_START] = [MessageHandler(filters.Regex("^Начать$"), self.event_ask_for_pic), MessageHandler(filters.Regex("^Отмена$"), self.event_on_cancel)]

        # Create message handle if it not exist 
        if self.message_handler == None:
            self.message_handler = MessageHandler(filters= filters.TEXT, callback=self.event_get_message)
            self.application.add_handler(self.message_handler)

        return self.STATE_START

    async def event_ask_for_pic(self, update: Update, context: ContextTypes = ContextTypes.DEFAULT_TYPE) -> int:
        logging.log(logging.INFO, "Switch to event_ask_for_pic")
        
        ASK_TEXT = "Введите название того что вы хотите найти"
        await context.bot.send_message(chat_id=update.effective_chat.id, text = ASK_TEXT)
        self.message_handler_state = 1

        return self.STATE_START

    async def event_get_message(self, update: Update, context: ContextTypes = ContextTypes.DEFAULT_TYPE) -> int:
        if self.message_handler_state == 1:
            logging.log(logging.INFO, "Switch to event_get_message")

            self.search_request = update.message.text

            SEARCH_TEXT = f"Пытаюсь найти картинку под запросом {self.search_request}"
            await context.bot.send_message(chat_id=update.effective_chat.id, text = SEARCH_TEXT)

            loop = asyncio.get_event_loop()
            loop.create_task(self.event_send_pic(context=context, update=update))
            
        return self.STATE_SEARCH

    async def event_send_pic(self, update: Update, context: ContextTypes = ContextTypes.DEFAULT_TYPE):
        logging.log(logging.INFO, "Switch to event_send_pic")
        
        """
            1. Bot: Sends picture 
            2. User will have a choice             
                Next or Ask somethin else     
        """

        # TODO: Search a pic

        sendPicScreenKeyboardMarkup = ReplyKeyboardMarkup([["Продолжить", "Другой запрос"]], one_time_keyboard=True, resize_keyboard=True)

        isRequestFailed = False 
        
        file: os.FileIO = None
        finalPath: str = ""

        # FIXME: Hack {randint(1, 10000)} for random result  
        searchName = f"{randint(1, 10000)} Anime {self.search_request}"
        
        logging.log(logging.INFO, f"{searchName}")
        # TODO: So, how we need to get failed request 

        crawler = GoogleImageCrawler(storage = {'root_dir': self.DATA_FOLDER_NAME})
        crawler.crawl(keyword = searchName, overwrite=True, max_num = 1)
        folderPath = f"{self.DATA_FOLDER_NAME}"
        if not os.path.isdir(folderPath):
            logging.log(logging.ERROR, f"Folder is not exist with this path {folderPath}")
            isRequestFailed = True
        else:
            logging.log(logging.INFO, "Folder found! Try to open next step...")

        for format in {"png", "jpg"}:
            try:            
                finalPath = f"{folderPath}\\000001.{format}"
                file = open(finalPath, 'rb')
            except IOError:
                logging.log(logging.ERROR, "Failed to open image file...")
                file = None
            finally:
                break
        
        isRequestFailed = (file == None)

        if isRequestFailed == False:
            PIC_IS_FOUND_TEXT = "Картинка найдена!\nЖелаете ли вы ввести другой запрос или же искать другие с тем же запросом ?"

            await context.bot.send_message(chat_id=update.effective_chat.id, text = PIC_IS_FOUND_TEXT, reply_markup=sendPicScreenKeyboardMarkup)
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=file,  reply_markup=sendPicScreenKeyboardMarkup)
            file.close()
        
            # Cleanup image file 
            os.remove(finalPath)
        else: 
            REQUEST_FAILED_ERR_TEXT = "Картинка не была найдена\nЖелаете ли вы ввести другой запрос или же искать другие с тем же запросом ?"
            await context.bot.send_message(chat_id=update.effective_chat.id, text = REQUEST_FAILED_ERR_TEXT, reply_markup=sendPicScreenKeyboardMarkup)
        
        self.message_handler_state = 0

        self.states[self.STATE_START] = [MessageHandler(filters.Regex("^Продолжить$"), self.event_send_pic), 
            MessageHandler(filters.Regex("^Другой запрос$"), self.event_ask_for_pic)]

        return self.STATE_START


