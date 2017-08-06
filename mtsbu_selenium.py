#!/usr/bin/env python3

from selenium import webdriver
from base64 import b64encode
import json
import itertools
import logging
import logging.handlers
import random
import argparse
import os

logger = logging.getLogger('mtsbu')
logger.setLevel(logging.DEBUG)

# always write everything to the rotating log files
if not os.path.exists('logs'): os.mkdir('logs')
log_file_handler = logging.handlers.TimedRotatingFileHandler('logs/mtsbu.log', when='M', interval=2)
log_file_handler.setFormatter( logging.Formatter('%(asctime)s [%(levelname)s](%(name)s:%(funcName)s:%(lineno)d): %(message)s') )
log_file_handler.setLevel(logging.DEBUG)
logger.addHandler(log_file_handler)

# also log to the console at a level determined by the --verbose flag
console_handler = logging.StreamHandler() # sys.stderr
console_handler.setLevel(logging.CRITICAL) # set later by set_log_level_from_verbose() in interactive sessions
console_handler.setFormatter( logging.Formatter('[%(levelname)s](%(name)s): %(message)s') )
logger.addHandler(console_handler)

logger.info("Starting...")

parser = argparse.ArgumentParser(
    description="get information via selenium",
)
parser.add_argument('command', nargs="?", default="count", help="command to execute", choices=['count', 'head', 'tail'])

parser.add_argument('-V', '--version', action="version", version="%(prog)s 2.0")
parser.add_argument('-v', '--verbose', action="count", help="verbose level... repeat up to three times.")


def set_log_level_from_verbose(args):

    if not args.verbose:
        console_handler.setLevel('ERROR')
    elif args.verbose == 1:
        console_handler.setLevel('WARNING')
    elif args.verbose == 2:
        console_handler.setLevel('INFO')
    elif args.verbose >= 3:
        console_handler.setLevel('DEBUG')
    else:
        logger.critical("UNEXPLAINED NEGATIVE COUNT!")


def check_car_cache(car_number):
    car_entry = {}
    try:
        with open('cardb.json', mode='r', encoding='utf-8') as f:
            car_entry = json.load(f)
        if car_number in car_entry:
            return True
        else:
            return False
    except IOError as err:
        # if cache file is empty create with default content
        car_entry["car_number"] = "url"
        with open('cardb.json', mode='w', encoding='utf-8') as f:
            json.dump(car_entry, f, indent=2)


def add_to_file_cache(car_number, url):
    '''
    :param car_number: car number
    :param url: url with info to add
    :return:
    '''
    car_entry = {}
    with open('cardb.json', mode='r', encoding='utf-8') as f:
        car_entry = json.load(f)
    car_entry[car_number] = url
    # print(car_entry)
    with open('cardb.json', mode='w', encoding='utf-8') as f:
        json.dump(car_entry, f, indent=2)

def get_car_info(car_number, ignore_cache = 0, proxy = 0):
    if check_car_cache(car_number) and ignore_cache == 0:
        print(car_number, " already in cache")
        pass
    else:
        try:
            if proxy == 0:
                # driver = webdriver.Chrome()
                driver = webdriver.Firefox()
            elif len(proxy) == 4:
                fp = webdriver.FirefoxProfile()
                fp.add_extension('/Users/alex/close_proxy_authentication-1.1-sm+tb+fx.xpi')
                fp.set_preference('network.proxy.type', 1)
                fp.set_preference('network.proxy.http', proxy['host'])
                fp.set_preference('network.proxy.http_port', int(proxy['port']))
                fp.set_preference('network.proxy.ssl', proxy['host'])
                fp.set_preference('network.proxy.ssl_port', int(proxy['port']))
                # ... ssl, socks, ftp ...
                fp.set_preference('network.proxy.no_proxies_on', 'localhost, 127.0.0.1')
                credentials = '{user}:{password}'.format(**proxy)
                credentials = b64encode(credentials.encode('ascii')).decode('utf-8')
                # print(credentials)
                fp.set_preference('extensions.closeproxyauth.authtoken', credentials)
                fp.update_preferences()
                driver = webdriver.Firefox(firefox_profile=fp)
            elif len(proxy) == 2:
                fp = webdriver.FirefoxProfile()
                fp.set_preference('network.proxy.type', 1)
                fp.set_preference('network.proxy.http', proxy['host'])
                fp.set_preference('network.proxy.http_port', int(proxy['port']))
                fp.set_preference('network.proxy.ssl', proxy['host'])
                fp.set_preference('network.proxy.ssl_port', int(proxy['port']))
                # ... ssl, socks, ftp ...
                fp.set_preference('network.proxy.no_proxies_on', 'localhost, 127.0.0.1')
                fp.update_preferences()
                driver = webdriver.Firefox(firefox_profile=fp)
            else:
                logger.error("error with proxy {}".format(proxy))

            driver.implicitly_wait(10) # seconds
            driver.get('https://cbd.mtibu.kiev.ua/')
            se_enter = driver.find_element_by_id("OuterHolder_LoginButton")
            se_enter.click()
            se_car_number = driver.find_element_by_link_text("Визначити статус полісу та страховика, що видав поліс за транспортним засобом")
            se_car_number.click()
            driver.find_element_by_id("OuterHolder_InnerPlaceHolder_FVehicle.RegNo").send_keys(car_number)
            se_search = driver.find_element_by_id("OuterHolder_InnerPlaceHolder_SearchSubmit")
            se_search.click()

            try:
                if driver.find_element_by_id("OuterHolder_InnerPlaceHolder_TechInfo").text == "не дав результатів":
                    logger.info("{} не дав результатів".format(car_number))
                    print(car_number, " не дав результатів")
                    add_to_file_cache(car_number, False)
                else:
                    se_output = driver.find_element_by_id("OuterHolder_InnerPlaceHolder_ResultGrid_tccell0_0")
                    href = se_output.find_element_by_css_selector('a').get_attribute('href')
                    if href:
                        print("found url for car number ", car_number)
                        logger.info("found url for {} url is {}".format(car_number, href))
                        add_to_file_cache(car_number, href)
                        return href
            except (RuntimeError, TypeError, NameError) as err:
                print(err)
                se_output = driver.find_element_by_id("OuterHolder_InnerPlaceHolder_ResultGrid_tccell0_0")
                href = se_output.find_element_by_css_selector('a').get_attribute('href')
                if href:
                    print("found url for car number ", car_number)
                    add_to_file_cache(car_number, href)
                    return href
                else:
                    print("not found any info for", car_number)
                    add_to_file_cache(car_number, href)
            # print(driver.page_source)
            driver.close()
        except IOError as err:
            print("error getting info for", car_number)
            print(str(err))
            add_to_file_cache(car_number, False)
            driver.close()
            pass

def get_proxy(filename):
    '''
    :param filename: where located proxylist in format user:password:host:port or host:port
    :return: proxy list
    '''
    proxy = []
    with open(filename, encoding='utf-8') as proxy_file:
        for line in proxy_file:
            line = line.strip()
            if not line.startswith("#"):
                line = line.rstrip()
                if (len(line.split(":")) == 4):
                    user, password, host, port = line.split(":")
                    proxy.append({"host": host, "port": port, "user": user, "password": password})
                elif (len(line.split(":")) == 2):
                    host, port = line.split(":")
                    proxy.append({"host": host, "port": port})
                else:
                    logger.error("unable to parse proxy in line \"{}\" start parse next line...".format(line))
                    print("Unable to parse proxy", line)
                random.shuffle(proxy)
    logger.info("loading {} proxy".format(len(proxy)))
    return proxy



if __name__ == '__main__':
    latin_letters = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "V", "X", "Y", "Z", "J", "U")
    args = parser.parse_args()
    set_log_level_from_verbose(args)
    proxy = get_proxy("proxy.txt")

    proxy_iter = itertools.cycle(proxy)
    for letter in latin_letters:
        current_proxy = next(proxy_iter)
        car_number = "J" + letter + "D380"
        # car_number = "J" + letter + "C380"
        logger.debug("{} get info via proxy {}:{}".format(car_number, current_proxy["host"], current_proxy["port"]))
        href_info = get_car_info(car_number, proxy = current_proxy)

    # car_number = "AK2453BA"
    # href_info = get_car_info(car_number, ignore_cache=1, proxy=proxy)