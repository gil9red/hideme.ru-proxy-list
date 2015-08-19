#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


from grab import Grab
from urllib.parse import urljoin
from urllib.request import urlopen, Request
from parsing_captcha import CaptchaParser
from collections import namedtuple
import logging
import sys
from PIL import Image
from io import BytesIO
import traceback


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


from random import randint, choice

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:39.0) Gecko/20100101 Firefox/39.0',
    'Mozilla/5.0 (Windows; U; Windows NT 5.1; de; rv:1.9.1.5) Gecko/20091102 Firefox/3.5.5',
]

# Притворяемся браузером
HEADERS = {
    'User-agent': choice(USER_AGENTS),
    'Accept': 'text/xml,application/xml,application/xhtml+xml,text/html;'
              'q=0.9,text/plain;q=0.8,image/png,*/*;q=0.%d' % randint(2, 5),
    'Accept-Language': 'en-us,en;q=0.%d' % randint(5, 9),
    'Accept-Charset': 'utf-8,windows-1251;q=0.7,*;q=0.%d' % randint(5, 7),
    'Keep-Alive': '300',
    'Expect': '',
}


def go_url(url):
    """Функция возвращает страницу url в виде байтового массива."""

    # Добавляем заголовок, чтобы hideme.ru не посчитал нас ботом
    rq = Request(url, headers=HEADERS)

    logger.debug('Перехожу по url: %s.', url)

    with urlopen(rq) as rs:
        return rs.read()


def download_image(url):
    """Функция скачивает картинку с указанного url'а и возвращает Image из PIL'а."""

    data = go_url(url)
    if data:
        return Image.open(BytesIO(data))


Proxy = namedtuple('Proxy', 'ip port country city speed type anonymity checked')


if __name__ == '__main__':
    logger = get_logger('hideme.ru_parser')

    logger.debug('Инициализация парсера капчи.')
    parser = CaptchaParser()

    url = 'http://hideme.ru/proxy-list/'

    data = go_url(url)
    if data is None:
        raise Exception('Страница не получена.')

    logger.info('Страница загружена.')


    from lxml import etree

    # Вытаскиваем список строк таблицы с атрибутом class="pl", у строк должны быть вложены теги td
    xpath = '//table[@class="pl"]/tr[td]'
    # print(data.decode('cp1251'))
    tree = etree.HTML(data.decode('cp1251'))
    rows = tree.xpath(xpath)

    print(len(rows), rows)


# from lxml import etree
#
# tree = etree.XML(xml) # Парсинг строки
# #tree = etree.parse('1.xml') # Парсинг файла
#
# nodes = tree.xpath('/soft/os/item') # Открываем раздел
# for node in nodes: # Перебираем элементы
#     print node.tag,node.keys(),node.values()
#     print 'name =',node.get('name') # Выводим параметр name
#     print 'text =',[node.text] # Выводим текст элемента
#
# # Доступ к тексту напрямую, с указанием фильтра
# print 'text1',tree.xpath('/soft/os/item[@name="linux"]/text()')
# print 'text2',tree.xpath('/soft/os/item[2]/text()')
# # Доступ к параметру напрямую
# print 'dist',tree.xpath('/soft/os/item[@name="linux"]')[0].get('dist')
# # Выборка по ключу
# print 'dist by key',tree.xpath('//*[@name="windows"]')[0].get('dist')
#
# print 'iterfind:'
# for node in tree.iterfind('.//item'): # поиск элементов
#     print node.get('name')
#
# # Рекурсивный перебор элементов
# print 'recursiely:'
# def getn(node):
#     print node.tag,node.keys()
#     for n in node:
#         getn(n)
# getn(tree.getroottree().getroot())

    quit()

    # TODO: полностью заменить grab на lxml
    g = Grab(data)

    proxy_list = list()

    # Вытаскиваем список строк таблицы с атрибутом class="pl", у строк должны быть вложены теги td
    xpath = '//table[@class="pl"]/tr[td]'

    logger.debug('Начинаю парсить загруженную страницу.\n')

    try:
        rows = g.doc.select(xpath)
        if len(rows) == 0:
            raise Exception('Список прокси пустой')

        for row in rows:
            logger.debug('Начинаю разбирать строку с прокси.')
            ip, port, country, city, speed, proxy_type, anonymity, checked = row.select('td')

            port_img_src = port.select('img/@src').text()
            port_img_src = urljoin(url, port_img_src)
            logger.debug('Скачиваю картинку с портом.')
            port_img = download_image(port_img_src)
            if port_img is None:
                raise Exception('Не удалось загрузить картинку с портом. url: {}.'.format(port_img_src))
            logger.debug('Закончено скачивание картинки с портом.')

            port = parser.run(port_img)
            if '-' not in port:
                logger.debug('Картинка распарсена. port: %s.', port)
            else:
                logger.warn('Картинка распарсена не полностью. port: %s.\n', port)
                continue

            proxy_type = proxy_type.text().split(', ')

            proxy = Proxy(ip.text(), port, country.text(), city.text(), speed.text(),
                          proxy_type, anonymity.text(), checked.text())

            proxy_list.append(proxy)

            logger.info('Закончен парсинг строки с прокси: %s.\n', proxy)

    except ValueError as e:
        logger.error('Изменилось количество столбцов таблицы. Ошибка: %s. xpath: %s', e, xpath)
        logger.error(traceback.format_exc())

    except Exception as e:
        logger.error('Ошибка: %s. xpath: %s', e, xpath)
        logger.error(traceback.format_exc())

    logger.debug('Закончен разбор. Найдено %s прокси.', len(proxy_list))

    out = 'proxy-list.txt'

    if proxy_list:
        logger.debug('Сохраняю прокси в файл: %s.', out)

        # Сохраним найденные прокси в файл
        with open(out, mode='w') as f:
            for proxy in proxy_list:
                f.write('{0.ip}:{0.port}\n'.format(proxy))
    else:
        logger.warn('Список прокси пустой, отмена сохранения.')
