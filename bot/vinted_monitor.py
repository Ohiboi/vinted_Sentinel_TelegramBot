import asyncio
from datetime import datetime
from api.vinted_api import VintedAPI
from bot.telegram_bot import TelegramBot
from db.product_database import ProductDatabase
import logging

logger = logging.getLogger(__name__)


class VintedMonitor:
    def __init__(self, config):
        self.config = config
        self.db = ProductDatabase()
        self.bot = TelegramBot(config['token'], config['channel_id'])

    def is_active_hour(self):
        ora_attuale = datetime.now().hour
        # Attivo tra le 9:00 e le 22:00, in pausa di notte
        return 9 <= ora_attuale < 22

    async def start_monitoring(self):
        while True:
            try:
                if not self.is_active_hour():
                    logger.info("Fuori orario attivo (22:00-9:00), bot in pausa")
                    await asyncio.sleep(600)  # ricontrolla ogni 10 minuti se è tornato l'orario attivo
                    continue

                for country_code in self.config['countries']:
                    # Iniziamo una nuova sessione API per ciascun paese
                    self.api = VintedAPI(country_code)

                    for search_term in self.config['search_terms']:
                        logger.debug(f"Searching for term: {search_term} in {country_code}")
                        items = await self.api.search_products(search_term)

                        for item in items:
                            try:
                                item_id = str(item.get('id'))
                                if not item_id or self.db.is_product_seen(item_id):
                                    continue

                                self.db.add_product(item)

                                message_text = self.create_message(item, country_code)

                                self.bot.send_message(
                                    message_text,
                                    image_url=item.get('image_url'),
                                    product_url=item['url']
                                )
                                logger.info(f"New product found and posted: {item.get('title')}")
                            except Exception as e:
                                logger.error(f"Error processing item: {str(e)}")
                                continue

                await asyncio.sleep(self.config['refresh_delay'] * 60)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(30)

    def create_message(self, item, country_code):
        country_name = self.get_country_name_from_code(country_code)

        # Dettagli del prodotto
        title = item['title']
        price = item['price']
        url = item['url']
        image_url = item.get('image_url')  # Assumiamo che l'immagine sia nell'oggetto 'item'

        # Creazione del messaggio
        message_text = f"New Product in {country_name}: {title}\nPrice: {price}€\nCountry: {country_name}\nLink: {url}"

        return message_text

    def get_country_name_from_code(self, country_code):
        country_map = {
            ".de": "Germany",
            ".it": "Italy",
            ".fr": "France",
            ".es": "Spain",
            ".uk": "United Kingdom"
        }
        return country_map.get(country_code, "Unknown Country")
