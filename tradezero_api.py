import os
import time
import pytz
from datetime import datetime
import pandas as pd
from collections import namedtuple
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from termcolor import colored
import warnings
os.system('color')


class TradeZero:
    def __init__(self, chrome_driver_path: str, user_name: str, password: str, headless: bool = True,
                 hide_attributes: bool = False):
        """
        :param chrome_driver_path: path to chromedriver.exe
        :param user_name: TradeZero user_name
        :param password: TradeZero password
        :param headless: True will run the browser in headless mode, which means it won't be visible
        :param hide_attributes: bool, if True: Hide account attributes (acc username, equity, total exposure...)
        """
        self.user_name = user_name
        self.password = password
        self.hide_attributes = hide_attributes

        s = Service(chrome_driver_path)
        options = webdriver.ChromeOptions()
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        if headless is True:
            options.headless = headless

        self.driver = webdriver.Chrome(service=s, options=options)
        self.driver.get("https://standard.tradezeroweb.us/")

        self.Watchlist = Watchlist(self.driver)

        # to instantiate the time, pytz, and datetime modules:
        time.time()
        self.time_between(self.time, self.time)

    def _dom_fully_loaded(self, iter_amount: int = 1):
        """
        check that webpage elements are fully loaded/visible.
        there is no need to call this method, but instead call tz_conn() and that will take care of all the rest.

        :param iter_amount: int, default: 1, number of times it will iterate.
        :return: if the elements are fully loaded: return True, else: return False.
        """
        container_xpath = "//*[contains(@id,'portfolio-container')]//div//div//h2"
        for i in range(iter_amount):
            elements = self.driver.find_elements(By.XPATH, container_xpath)
            text_elements = [x.text for x in elements]
            if 'Portfolio' in text_elements:
                return True
            time.sleep(0.5)
        return False

    def login(self, log_time_elapsed: bool = False):
        """
        log-in TradeZero's website

        :param log_time_elapsed: bool, if True it will print time elapsed for login
        """
        timer_start1 = time.time()

        login_form = self.driver.find_element(By.ID, "login")
        login_form.send_keys(self.user_name)

        password_form = self.driver.find_element(By.ID, "password")
        password_form.send_keys(self.password, Keys.RETURN)

        self._dom_fully_loaded(150)
        if self.hide_attributes:
            self._hide_attributes()

        Select(self.driver.find_element(By.ID, "trading-order-select-type")).select_by_index(1)

        if log_time_elapsed is True:
            print(f'Time elapsed (log in): {time.time() - timer_start1 :.2f}')

    def conn(self, log_tz_conn: bool = False):
        """
        make sure that the website stays connected and is fully loaded.
        TradeZero will ask for a Login twice a day, and sometimes it will require the page to be reloaded,
        so this will make sure that its fully loaded, by reloading or doing the login.

        :param log_tz_conn: bool, default: False. if True it will print if it reconnects through the login or refresh.
        :return: True if connected
        :raises Exception: if it fails to reconnect after a while
        """
        if self._dom_fully_loaded(1):
            return True

        try:
            self.driver.find_element(By.ID, "login")
            self.login()

            self.Watchlist.restore()
            if log_tz_conn is True:
                print(colored('tz_conn(): Login worked', 'cyan'))
            return True

        except NoSuchElementException:
            self.driver.get("https://standard.tradezeroweb.us/")
            if self._dom_fully_loaded(150):

                if self.hide_attributes:
                    self._hide_attributes()
                self.Watchlist.restore()
                if log_tz_conn is True:
                    print(colored('tz_conn(): Refresh worked', 'cyan'))
                return True

        raise Exception('@ tz_conn(): Error: not able to reconnect, max retries exceeded')

    def exit(self):
        """close Selenium window and driver"""
        try:
            self.driver.close()
        except WebDriverException:
            pass

        self.driver.quit()

    @property
    def time(self):
        """return current EST time in str, ex: '12:04:31.217'"""
        tz_ny = pytz.timezone('US/Eastern')
        datetime_ny = datetime.now(tz_ny)
        time1 = datetime_ny.strftime("%H:%M:%S.%f")[:-3]
        return time1

    def time_between(self, time1: str, time2: str):
        """
        return True if current time between: time1, and time2, else: return False

        :param time1: str
        :param time2: str
        :return: bool
        """
        if time1 <= self.time < time2:
            return True
        return False

    def load_symbol(self, symbol: str):
        """
        make sure the data for the symbol is fully loaded and that the symbol itself is valid

        :param symbol: str
        :return: True if symbol data loaded, False if prices == 0.00 (mkt closed), Error if symbol not found
        :raises Exception: if symbol not found
        """
        if symbol.upper() == self.current_symbol():
            price = self.driver.find_element(By.ID, "trading-order-ask").text.replace('.', '').replace(',', '')
            if price.isdigit() and float(price) > 0:
                return True

        input_symbol = self.driver.find_element(By.ID, "trading-order-input-symbol")
        input_symbol.send_keys(symbol, Keys.RETURN)
        time.sleep(0.04)

        for i in range(300):
            price = self.driver.find_element(By.ID, "trading-order-ask").text.replace('.', '').replace(',', '')
            if price == '':
                time.sleep(0.01)

            elif price.isdigit() and float(price) == 0:
                warnings.warn(f"Market Closed, ask/bid = {price}")
                return False

            elif price.isdigit():
                return True

            elif i == 15 or i == 299:
                last_notif = self.fetch_last_notif_message()
                message = f'Symbol not found: {symbol.upper()}'
                if message == last_notif:
                    raise Exception(f"ERROR: {symbol=} Not found")

    def current_symbol(self):
        """get current symbol"""
        return self.driver.find_element(By.ID, 'trading-order-symbol').text.replace('(USD)', '')

    @property
    def bid(self):
        """get bid price"""
        return float(self.driver.find_element(By.ID, 'trading-order-bid').text.replace(',', ''))

    @property
    def ask(self):
        """get ask price"""
        return float(self.driver.find_element(By.ID, 'trading-order-ask').text.replace(',', ''))

    @property
    def last(self):
        """get last price"""
        return float(self.driver.find_element(By.ID, 'trading-order-p').text.replace(',', ''))

    def data(self, symbol: str):
        """
        return a namedtuple with data for the given symbol, the properties are:
        'open', 'high', 'low', 'close', 'volume', 'last', 'ask', 'bid'.

        :param symbol: str: ex: 'aapl', 'amd', 'NVDA', 'GM'
        :return: namedtuple = (open, high, low, close, volume, last, ask, bid)
        """
        Data = namedtuple('Data', ['open', 'high', 'low', 'close', 'volume', 'last', 'ask', 'bid'])

        if self.load_symbol(symbol) is False:
            return Data(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        element_ids = [
            'trading-order-open',
            'trading-order-high',
            'trading-order-low',
            'trading-order-close',
            'trading-order-vol',
            'trading-order-p',
            'trading-order-ask',
            'trading-order-bid',
        ]
        lst = []
        for id_ in element_ids:
            val = self.driver.find_element(By.ID, id_).text
            val = float(val.replace(',', ''))  # replace comma for volume, and when prices > 999
            lst.append(val)

        return Data._make(lst)

    def calculate_order_quantity(self, symbol: str, buying_power: float, float_option: bool = False):
        """
        returns the amount of shares you can buy with the given buying_power as int(), but if float_option is True,
        it will return the amount as a float.

        :param symbol: str
        :param buying_power: float,
        :param float_option: bool, default: False, if True returns the original number as float
        :return: int or float
        """
        if self.load_symbol(symbol) is False:
            return
        quantity = (buying_power / self.last)

        if float_option is True:
            return quantity
        return int(quantity)

    def locate_stock(self, symbol: str, share_amount: int, max_price: float = 0, debug_info: bool = False):
        """
        Locate a stock, requires: stock symbol, and share_amount. optional: max_price.
        if the locate_price is less than max_price: it will accept, else: decline.

        :param symbol: str, symbol to locate.
        :param share_amount: int, must be a multiple of 100 (100, 200, 300...)
        :param max_price: float, default: 0, total price you are willing to pay for locates
        :param debug_info: bool, if True it will print info about the locates in the console
        :return: named tuple with the following attributes: 'price_per_share' and 'total'
        :raises Exception: if share_amount is not divisible by 100
        """
        Data = namedtuple('Data', ['price_per_share', 'total'])

        if share_amount is not None and share_amount % 100 != 0:
            raise Exception(f'ERROR: share_amount is not divisible by 100 ({share_amount=})')

        if not self.load_symbol(symbol):
            return

        if self.last <= 1.00:
            print(f'Error: Cannot locate stocks priced under $1.00 ({symbol=}, price={self.last})')

        self.driver.find_element(By.ID, "locate-tab-1").click()
        input_symbol = self.driver.find_element(By.ID, "short-list-input-symbol")
        input_symbol.clear()
        input_symbol.send_keys(symbol, Keys.RETURN)

        input_shares = self.driver.find_element(By.ID, "short-list-input-shares")
        input_shares.clear()
        input_shares.send_keys(share_amount)

        while self.driver.find_element(By.ID, "short-list-locate-status").text == '':
            time.sleep(0.1)

        if self.driver.find_element(By.ID, "short-list-locate-status").text == 'Easy to borrow':
            locate_pps = 0.00
            locate_total = 0.00
            if debug_info:
                print(colored(f'Stock ({symbol}) is "Easy to borrow"', 'green'))
            return Data(locate_pps, locate_total)

        self.driver.find_element(By.ID, "short-list-button-locate").click()

        for i in range(300):
            try:
                locate_pps = float(self.driver.find_element(By.ID, f"oitem-l-{symbol.upper()}-cell-2").text)
                locate_total = float(self.driver.find_element(By.ID, f"oitem-l-{symbol.upper()}-cell-6").text)
                break

            except NoSuchElementException:
                time.sleep(0.15)
                if i == 15 or i == 299:
                    insufficient_bp = 'Insufficient BP to short a position with requested quantity.'
                    last_notif = self.fetch_last_notif_message()
                    if insufficient_bp in last_notif:
                        warnings.warn(f"ERROR! {insufficient_bp}")
                        return
        else:
            raise Exception(f'Error: not able to locate symbol element ({symbol=})')

        if locate_total <= max_price:
            self.driver.find_element(By.XPATH, f'//*[@id="oitem-l-{symbol.upper()}-cell-8"]/span[1]').click()
            if debug_info:
                print(colored(f'HTB Locate accepted ({symbol}, $ {locate_total})', 'cyan'))
        else:
            self.driver.find_element(By.XPATH, f'//*[@id="oitem-l-{symbol.upper()}-cell-8"]/span[2]').click()

        return Data(locate_pps, locate_total)

    def credit_locates(self, symbol: str, quantity=None):
        """
        sell/ credit stock locates, if no value is given in 'quantity', it will credit all the shares
        available of the given symbol.

        :param symbol: str
        :param quantity: amount of shares to sell, must be a multiple of 100, ie: 100, 200, 300
        :return:
        :raises Exception: if given symbol in not already located
        :raises ValueError: if quantity is not divisible by 100 or quantity > located shares
        """
        located_symbols = self.driver.find_elements(By.XPATH, '//*[@id="locate-inventory-table"]/tbody/tr/td[1]')
        located_symbols = [x.text for x in located_symbols]

        if symbol.upper() not in located_symbols:
            raise Exception(f"ERROR! cannot find {symbol} in located symbols")

        if quantity is not None:
            if quantity % 100 != 0:
                raise ValueError(f"ERROR! quantity is not divisible by 100 ({quantity=})")

            located_shares = float(self.driver.find_element(By.ID, f"inv-{symbol.upper()}-cell-1").text)
            if quantity > located_shares:
                raise ValueError(f"ERROR! you cannot credit more shares than u already have "
                                 f"({quantity} vs {located_shares}")

            input_quantity = self.driver.find_element(By.ID, f"inv-{symbol.upper()}-sell-qty")
            input_quantity.clear()
            input_quantity.send_keys(quantity)

        self.driver.find_element(By.XPATH, f'//*[@id="inv-{symbol.upper()}-sell"]/button').click()
        return

    def limit_order(self, order_direction: str, symbol: str, share_amount: int, limit_price: float,
                    time_in_force: str = 'DAY', log_info: bool = False):
        """
        Place a Limit Order, the following params are required: order_direction, symbol, share_amount, and limit_price.

        :param order_direction: str: 'buy', 'sell', 'short', 'cover'
        :param symbol: str: e.g: 'aapl', 'amd', 'NVDA', 'GM'
        :param limit_price: float
        :param share_amount: int
        :param time_in_force: str, default: 'DAY', must be one of the following: 'DAY', 'GTC', or 'GTX'
        :param log_info: bool, if True it will print information about the order
        :return: True if operation succeeded
        :raises AttributeError: if time_in_force argument not one of the following: 'DAY', 'GTC', 'GTX'
        """
        timer_start = time.time()
        symbol = symbol.lower()
        order_direction = order_direction.lower()
        time_in_force = time_in_force.upper()

        if time_in_force not in ['DAY', 'GTC', 'GTX']:
            raise AttributeError(f"Error: time_in_force argument must be one of the following: 'DAY', 'GTC', 'GTX'")

        self.load_symbol(symbol)

        order_menu = Select(self.driver.find_element(By.ID, "trading-order-select-type"))
        order_menu.select_by_index(1)

        tif_menu = Select(self.driver.find_element(By.ID, "trading-order-select-time"))
        tif_menu.select_by_visible_text(time_in_force)

        input_quantity = self.driver.find_element(By.ID, "trading-order-input-quantity")
        input_quantity.clear()
        input_quantity.send_keys(share_amount)

        price_input = self.driver.find_element(By.ID, "trading-order-input-price")
        price_input.clear()
        price_input.send_keys(limit_price)

        self.driver.find_element(By.ID, f"trading-order-button-{order_direction}").click()
        if log_info is True:
            print(f"Time: {self.time}, Time elapsed: {time.time() - timer_start :.2f}, Order direction:",
                  f"{order_direction}, Symbol: {symbol}, Limit Price: {limit_price}, Shares amount: {share_amount}")
        return

    def market_order(self, order_direction: str, symbol: str, share_amount: int,
                     time_in_force: str = 'DAY', log_info: bool = False):
        """
        Place a Market Order, The following params are required: order_direction, symbol, and share_amount

        :param order_direction: str: 'buy', 'sell', 'short', 'cover'
        :param symbol: str: e.g: 'aapl', 'amd', 'NVDA', 'GM'
        :param share_amount: int
        :param time_in_force: str, default: 'DAY', must be one of the following: 'DAY', 'GTC', or 'GTX'
        :param log_info: bool, if True it will print information about the order
        :return:
        :raises Exception: if time not during market hours (9:30 - 16:00)
        :raises AttributeError: if time_in_force argument not one of the following: 'DAY', 'GTC', 'GTX'
        """
        timer_start = time.time()
        symbol = symbol.lower()
        order_direction = order_direction.lower()
        time_in_force = time_in_force.upper()

        if not self.time_between('09:30:00', '16:00:00'):
            raise Exception(f'Error: Market orders are not allowed at this time ({self.time})')

        if time_in_force not in ['DAY', 'GTC', 'GTX']:
            raise AttributeError(f"Error: time_in_force argument must be one of the following: 'DAY', 'GTC', 'GTX'")

        self.load_symbol(symbol)

        order_menu = Select(self.driver.find_element(By.ID, "trading-order-select-type"))
        order_menu.select_by_index(0)

        tif_menu = Select(self.driver.find_element(By.ID, "trading-order-select-time"))
        tif_menu.select_by_visible_text(time_in_force)

        input_quantity = self.driver.find_element(By.ID, "trading-order-input-quantity")
        input_quantity.clear()
        input_quantity.send_keys(share_amount)

        self.driver.find_element(By.ID, f"trading-order-button-{order_direction}").click()
        if log_info is True:
            print(f"Time: {self.time}, Time elapsed: {time.time() - timer_start :.2f}, Order direction:",
                  f"{order_direction}, Symbol: {symbol}, Price: {self.last}, Shares amount: {share_amount}")
        return

    def stop_market_order(self, order_direction: str, symbol: str, share_amount: int, stop_price: float,
                          time_in_force: str = 'DAY', log_info: bool = False):
        """
        Place a Stop Market Order, the following params are required: order_direction, symbol,
        share_amount, and stop_price.
        note that a Stop Market Order can only be placed during market-hours (09:30:00 - 16:00:00), therefore if a
        Stop Market Order is placed outside market hours it will raise an error.

        :param order_direction: str: 'buy', 'sell', 'short', 'cover'
        :param symbol: str: e.g: 'aapl', 'amd', 'NVDA', 'GM'
        :param stop_price: float
        :param share_amount: int
        :param time_in_force: str, default: 'DAY', must be one of the following: 'DAY', 'GTC', or 'GTX'
        :param log_info: bool, if True it will print information about the order
        :return: True if operation succeeded
        :raises Exception: if time not during market hours (9:30 - 16:00)
        :raises AttributeError: if time_in_force argument not one of the following: 'DAY', 'GTC', 'GTX'
        """
        timer_start = time.time()
        symbol = symbol.lower()
        order_direction = order_direction.lower()
        time_in_force = time_in_force.upper()

        if not self.time_between('09:30:00', '16:00:00'):
            raise Exception(f'Error: Stop Market orders are not allowed at this time ({self.time})')

        if time_in_force not in ['DAY', 'GTC', 'GTX']:
            raise AttributeError(f"Error: time_in_force argument must be one of the following: 'DAY', 'GTC', 'GTX'")

        self.load_symbol(symbol)

        order_menu = Select(self.driver.find_element(By.ID, "trading-order-select-type"))
        order_menu.select_by_index(2)

        tif_menu = Select(self.driver.find_element(By.ID, "trading-order-select-time"))
        tif_menu.select_by_visible_text(time_in_force)

        input_quantity = self.driver.find_element(By.ID, "trading-order-input-quantity")
        input_quantity.clear()
        input_quantity.send_keys(share_amount)

        price_input = self.driver.find_element(By.ID, "trading-order-input-sprice")
        price_input.clear()
        price_input.send_keys(stop_price)

        self.driver.find_element(By.ID, f"trading-order-button-{order_direction}").click()
        if log_info is True:
            print(f"Time: {self.time}, Time elapsed: {time.time() - timer_start :.2f}, Order direction:",
                  f"{order_direction}, Symbol: {symbol}, Stop Price: {stop_price}, Shares amount: {share_amount}")

    def fetch_last_notif_message(self):
        """
        return message in last notification

        :return: str
        """
        return self.driver.find_element(By.CSS_SELECTOR, 'span.message').text

    def fetch_notif(self, notif_amount: int = 1):
        """
        return a nested list with each sublist containing [time, title, message],
        note that u can only view the amount of notifications that are visible in the box/widget
        without scrolling down (which usually is around 6-9 depending on each message length)
        example of nested list: (see the docs for a better look):
        [['11:34:49', 'Order canceled', 'Your Limit Buy order of 1 AMD was canceled.'],
        ['11:23:34', 'Level 2', 'You are not authorized for symbol: AMD'],
        ['11:23:34', 'Error', 'You are not authorized for symbol: AMD']].

        :param notif_amount: int amount of notifications to retrieve sorted by most recent
        :return: nested list
        """
        notif_lst = self.driver.find_elements(By.XPATH,
                                              '//*[@id="notifications-list-1"]/li')
        notif_lst_text = [x.text.split('\n') for x in notif_lst if x.text != '']
        notifications = []
        for (notification, i) in zip(notif_lst_text, range(notif_amount)):
            if len(notification) == 2:
                notification.insert(0, self.time)
            elif notification[0] == '' or notification[0] == '-':
                notification[0] = self.time

            notifications.append(notification)
        return notifications

    def portfolio(self, return_type: str = 'df'):
        """
        return the Portfolio table as a pandas.DataFrame or nested dict, with the symbol column as index.
        the column names are the following: 'type', 'qty', 'p_close', 'entry',
        'price', 'change', '%change', 'day_pnl', 'pnl', 'overnight'
        note that if the portfolio is empty Pandas won't be able to locate the table,
        and therefore will return None

        :param return_type: 'df' or 'dict'
        :return: pandas.DataFrame or None if table empty
        """
        portfolio_symbols = self.driver.find_elements(By.XPATH, '//*[@id="opTable-1"]/tbody/tr/td[1]')
        if len(portfolio_symbols) == 0:
            warnings.warn('Portfolio is empty')
            return None

        df = pd.read_html(self.driver.page_source, attrs={'id': 'opTable-1'})[0]
        df.columns = [
            'symbol', 'type', 'qty', 'p_close', 'entry', 'price', 'change', '%change', 'day_pnl', 'pnl', 'overnight'
        ]
        df = df.set_index('symbol')
        if return_type == 'dict':
            return df.to_dict('index')
        return df

    def open_orders(self):
        """
        return DF with only positions that were opened today (intraday positions)

        :return: pandas.DataFrame
        """
        df = self.portfolio()
        filt = df['overnight'] == 'Yes'
        return df.loc[~filt]

    def invested(self, symbol):
        """
        returns True if the given symbol is in portfolio, else: false

        :param symbol: str: e.g: 'aapl', 'amd', 'NVDA', 'GM'
        :return: bool
        """
        data = self.portfolio('dict')
        symbols_list = list(data.keys())

        if symbol.upper() in symbols_list:
            return True
        return False

    def _hide_attributes(self):
        """
        Hides all account attributes i.e, account username, equity-value, cash-value, realized-value...
        """
        element_ids = [
            "h-realized-value",
            "h-unrealizd-pl-value",
            "h-total-pl-value",
            "p-bp",
            "h-cash-value",
            "h-exposure-value",
            "h-equity-value",
            "h-equity-ratio-value",
            "h-used-lvg-value",
            "p-allowed-lev",
            "h-select-account",
            "h-loginId",
            "trading-order-label-account"
        ]
        for id_ in element_ids:
            element = self.driver.find_element(By.ID, id_)
            self.driver.execute_script("arguments[0].setAttribute('style', 'display: none;')", element)

    def fetch_attribute(self, attribute: str):
        """
        fetch_attribute allows you to fetch a certain attribute from you're account, the attribute must be one of the
        following elements: 'Day Realized', 'Day Unrealized', 'Day Total', 'Buying Power', 'Cash BP', 'Total Exposure',
        'Equity', 'Equity ratio', 'Used LVG', 'Allowed LVG'.
        note that if _hide_attributes() has been called, the account values are hidden, and therefore aren't
        accessible.

        :param attribute: str
        :return: attribute value or None if attribute hidden
        :raises KeyError: if given attribute is not valid
        """
        attributes = {
            'Day Realized': 'h-realized-value',
            'Day Unrealized': 'h-unrealizd-pl-value',
            'Day Total': 'h-total-pl-value',
            'Buying Power': 'p-bp',
            'Cash BP': 'h-cash-value',
            'Total Exposure': 'h-exposure-value',
            'Equity': 'h-equity-value',
            'Equity ratio': 'h-equity-ratio-value',
            'Used LVG': 'h-used-lvg-value',
            'Allowed LVG': 'p-allowed-lev'
        }

        if attribute not in attributes.keys():
            raise KeyError('ERROR! given attribute is not valid')

        element = self.driver.find_element(By.ID, attributes[attribute])
        if element.get_attribute('style') == 'display: none;':
            warnings.warn('cannot fetch attribute that has been hidden')
            return None

        value = self.driver.find_element(By.ID, attributes[attribute]).text

        chars = ['$', '%', 'x', ',']
        for char in chars:
            value = value.replace(char, '')

        return float(value)


class Watchlist:
    """
    this class is for managing the data withing the watchlist container
    note that if the container is placed on the left side of the UI it will show
    only about half of the properties (Last, Bid, Ask, %Chg, Chg, Vol) instead of all 12.
    """
    def __init__(self, driver):
        self.driver = driver
        self.symbols = set()

    def add(self, symbol: str):
        """
        add symbol to watchlist

        :param symbol:
        :raises Exception: if given symbol is not valid
        """
        symbol = symbol.upper()
        symbol_input = self.driver.find_element(By.ID, 'trading-l1-input-symbol')
        symbol_input.send_keys(symbol, Keys.RETURN)

        time.sleep(0.4)
        if self._symbol_valid(symbol):
            self.symbols.add(symbol)
        else:
            raise Exception(f'Error: Given symbol is not valid ({symbol})')

    def remove(self, symbol: str):
        """
        remove symbol from watchlist

        :param symbol:
        """
        symbol = symbol.upper()
        if symbol not in self._get_current_symbols():
            warnings.warn(f'Given Symbol is not present in watchlist ({symbol})')
            return

        delete_button = f'//*[@id="wl-{symbol}"]/td[1]'
        self.driver.find_element(By.XPATH, delete_button).click()
        self.symbols.remove(symbol)

    def reset(self):
        """
        remove all symbols from watchlist
        """
        rows = self.driver.find_elements(By.XPATH, '//*[@id="trading-l1-tbody"]/tr/td[1]')
        for delete_button in rows:
            delete_button.click()
        self.symbols = set()

    def restore(self):
        """
        make sure all symbols that have been added,
        are present in the watchlist (after refresh the watchlist resets)
        """
        current_list = set(self._get_current_symbols())  # set because the order might be different
        if self.symbols != current_list:
            for symbol in self.symbols:
                if symbol not in current_list:
                    self.add(symbol)

    def _get_current_symbols(self):
        """
        return list with current symbols on watchlist
        """
        rows = self.driver.find_elements(By.XPATH, '//*[@id="trading-l1-tbody"]/tr/td[2]')
        if len(rows) == 0:
            return []

        data = self.data('dict')
        return list(data.keys())

    def _symbol_valid(self, symbol: str):
        """
        check if a symbol is valid

        :param symbol:
        :return: bool
        """
        last_notif_message = self.driver.find_element(By.CSS_SELECTOR, 'span.message').text
        if last_notif_message == f'Symbol not found: {symbol.upper()}':
            return False
        return True

    def data(self, return_type: str = 'df'):
        """
        returns the watchlist table as either a DataFrame or Dict,
        if return_type is equal to: 'df' it will return a pandas.DataFrame
        or if return_type equal to: 'dict' it will return a Dictionary with the symbols as keys
        and the data as values.
        note that if there are no symbols in the watchlist, Pandas will not be able
        to locate the table and therefore will return False

        :param return_type: 'df' or 'dict'
        :return: None if empty, else: DF or dict
        """
        symbols_lst = self.driver.find_elements(By.XPATH, '//*[@id="trading-l1-tbody"]//td[2]')
        if len(symbols_lst) == 0:
            warnings.warn('There are no symbols present in your watchlist')
            return None

        # selenium can only read visible rows, while pandas can find also non-visible text
        # if there are no rows pandas will not be able to locate the table, and throw an error
        df = pd.read_html(self.driver.page_source, attrs={'id': 'trading-l1-table'})[0]

        if len(df.columns) == 8:
            df = df.drop(columns=[0])  # drop 'x'
            df.columns = ['symbol', 'last', 'bid', 'ask', '%chg', 'chg', 'vol']

        elif len(df.columns) == 14:
            df = df.drop(columns=[0, 2])  # drop 'x' and currency_get_current_symbols
            df.columns = ['symbol', 'open', 'close', 'last', 'bid', 'ask',
                          'high', 'low', '%chg', 'chg', 'vol', 'time']

        df = df.set_index('symbol')
        if return_type == 'dict':
            return df.to_dict('index')
        return df
