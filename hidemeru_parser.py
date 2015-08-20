#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


from urllib.parse import urljoin
from urllib.request import urlopen, Request
from collections import namedtuple
import logging
import sys
from io import BytesIO
import traceback
from random import randint, choice

from PIL import Image
from lxml import etree

from parsing_port import PortImgParser


def get_logger(name, file='log.txt', encoding='utf8'):
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s')

    fh = logging.FileHandler(file, encoding=encoding)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    log.addHandler(fh)

    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    log.addHandler(ch)

    return log


def tag_text(el):
    """Функция склеивает текст тега и его подтегов, удаляет с концов
    пробельные символы и возвращает его.

    Если передается строка, просто удаляются с концов пробельные символы
    и возвращает строка.

    """

    if isinstance(el, str):
        return el.strip()

    text = ''.join([x for x in el.itertext()])
    return text.strip()


def go_url(url, headers):
    """Функция возвращает страницу url в виде байтового массива."""

    # Добавляем заголовок, чтобы hideme.ru не посчитал нас ботом
    rq = Request(url, headers=headers)

    logger.debug('Перехожу по url: %s.', url)

    with urlopen(rq) as rs:
        return rs.read()


def download_image(url, headers):
    """Функция скачивает картинку с указанного url'а и возвращает Image из PIL'а."""

    data = go_url(url, headers)
    if data:
        return Image.open(BytesIO(data))


USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:39.0) Gecko/20100101 Firefox/39.0',
    'Mozilla/5.0 (Windows; U; Windows NT 5.1; de; rv:1.9.1.5) Gecko/20091102 Firefox/3.5.5',
]


Proxy = namedtuple('Proxy', 'ip port country city speed type anonymity checked')

logger = get_logger('hideme.ru_parser')


class HidemeRuParser:
    """Класс для парсинга сайта hideme.ru"""

    def __init__(self):
        # Будем притворяться браузером, иначе доступа к странице с списком прокси hideme.ru не даст
        self.headers = {
            'User-agent': choice(USER_AGENTS),
            'Accept': 'text/xml,application/xml,application/xhtml+xml,text/html;'
                      'q=0.9,text/plain;q=0.8,image/png,*/*;q=0.%d' % randint(2, 5),
            'Accept-Language': 'en-us,en;q=0.%d' % randint(5, 9),
            'Accept-Charset': 'utf-8,windows-1251;q=0.7,*;q=0.%d' % randint(5, 7),
            'Keep-Alive': '300',
        }

        self.proxy_list = list()

        logger.debug('Инициализация парсера капчи.')
        self.port_parser = PortImgParser()

    def process_el_port(self, url, port_el):
        """Функция получает ссылку на адрес страницы с прокси и элемент, содержащий порт.

        Далее функция парсит элемент с портом и возвращает строку с портом.

        """

        # Получаем ссылку на изображение с портом
        (port_img_src, ) = port_el.xpath('img/@src')
        port_img_src = urljoin(url, port_img_src)

        logger.debug('Скачиваю картинку с портом.')
        port_img = download_image(port_img_src, self.headers)
        if port_img is None:
            raise Exception('Не удалось загрузить картинку с портом. url: {}.'.format(port_img_src))

        logger.debug('Закончено скачивание картинки с портом.')

        # Разбираем картинку с портом
        port = self.port_parser.run(port_img)
        if '-' in port:
            raise Exception('Картинка распарсена не полностью. port: {}.\n'.format(port))

        logger.debug('Картинка распарсена. port: %s.', port)
        return port

    def run(self, url='http://hideme.ru/proxy-list/'):
        """Функция парсит указанный адрес сайта hideme.ru,
        заполняет proxy_list и возвращает его.

        """

        data = go_url(url, self.headers)
        if data is None:
            raise Exception('Страница не получена.')

        logger.info('Страница загружена.')

        tree = etree.HTML(data.decode('cp1251'))

        # Вытаскиваем список строк таблицы с атрибутом class="pl", у строк должны быть вложены теги td
        xpath = '//table[@class="pl"]/tr[td]'

        logger.debug('Начинаю парсить загруженную страницу.\n')

        try:
            rows = tree.xpath(xpath)
            if len(rows) == 0:
                raise Exception('Список прокси пустой')

            for i, row in enumerate(rows, 1):
                logger.debug('Начинаю разбирать %s строку с прокси.', i)

                ip, port, country, city, speed, proxy_type, anonymity, checked = row.xpath('td')

                try:
                    port = self.process_el_port(url, port)
                    proxy_type = tag_text(proxy_type).split(', ')

                    proxy = Proxy(tag_text(ip), port, tag_text(country), tag_text(city), tag_text(speed),
                                  proxy_type, tag_text(anonymity), tag_text(checked))

                    self.proxy_list.append(proxy)

                except Exception as e:
                    logger.warn(e)
                    continue

                logger.info('Закончен парсинг строки с прокси: %s.\n', proxy)

        except Exception as e:
            if isinstance(e, ValueError):
                logger.error('Изменилось количество столбцов таблицы. Ошибка: %s. xpath: %s', e, xpath)
            else:
                logger.error('Ошибка: %s. xpath: %s', e, xpath)

            logger.error(traceback.format_exc())

        logger.debug('Закончен разбор. Найдено %s прокси.', len(self.proxy_list))

    def save(self, out='proxy-list.txt'):
        """Функция сохраняет прокси из proxy_list в файл."""

        if self.proxy_list:
            logger.debug('Сохраняю прокси в файл: %s.', out)

            # Сохраним найденные прокси в файл
            with open(out, mode='w') as f:
                for proxy in self.proxy_list:
                    f.write('{0.ip}:{0.port}\n'.format(proxy))
        else:
            logger.warn('Список прокси пустой, отмена сохранения.')
