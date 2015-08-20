#!/usr/bin/env python
# -*- coding: utf-8 -*-


__author__ = 'ipetrash'


"""Скрипт разбирает номер порта на картинке.

Алгоритм разбора не умеет разбирать буквы, которые по вертикали не имеет просветов.
"""


import hashlib


BLACK_PXL = 0
WHITE_PXL = 255


def clear_img(im):
    """Функция очищает изображение от множества цветов, должно быть только 2 цвета: черный и белый.
    Один для фона, другой для текста на картинке.

    Вокруг текста изображения есть какой-то шум, в основном ближе к черному при L, а цвет текста
    колеблется к белому -- в основном 255, но как правило встречаются также, в диапазоне от
    244 до 254 и чтобы убрать лишние пиксели и сделать фон чистом черным, а текст чисто белого цвета,
    сделаем простую проверку -- к какой половине пиксели ближе -- к черной или белой и к той, которая
    больше склоняется и закрасим в нее.

    """

    w, h = im.size

    for x in range(w):
        for y in range(h):
            pxl = im.getpixel((x, y))

            # Цвета представлены диапазоном от 0 до 255
            # Если цвет ближе к белом, закрашиваем в белый, и наоборот
            if pxl >= WHITE_PXL // 2:
                im.putpixel((x, y), WHITE_PXL)
            else:
                im.putpixel((x, y), BLACK_PXL)


def get_margins(im, text_color=BLACK_PXL):
    """Функция для определения границ текста на картинке."""

    w, h = im.size
    left, right, top, bottom = w, -1, h, -1

    for y in range(h):
        for x in range(w):
            pxl = im.getpixel((x, y))

            if pxl == text_color:
                if left > x:
                    left = x

                if right < x:
                    right = x

                if top > y:
                    top = y

                if bottom < y:
                    bottom = y

    return left, right, top, bottom


def crop_text(im):
    """Функция вырезает из изображения текст и возвращает его копию"""

    left, right, top, bottom = get_margins(im)
    return im.crop((left, top, right+1, bottom+1))


def border_letters(im, text_color=BLACK_PXL):
    """Функция ищет просветы между буквами и возвращает координаты границ.
    Между двумя буквами вернется один и первый попавшийся просвет"""

    # Разделить на части
    w, h = im.size

    # Бывает, просвет между буквами больше одного пикселя
    # и чтобы у нас не набрались несколько координат просветов
    # между двумя буквами, а нам нужно только одну координату,
    # мы заводим флаг, который при нахождении просвета будет
    # возведен, а при встрече первого черного пикселя (дошли
    # до буквы) опущен
    multi_line = False

    lines = []

    # Ищем просветы между буквами
    for x in range(w):
        line = True

        for y in range(h):
            pxl = im.getpixel((x, y))

            # Если наткнулись на белый пиксель, значит
            # тут не просвета, выходим из цикла
            if pxl == text_color:
                line = False
                multi_line = False
                break

        if line and not multi_line:
            multi_line = True
            lines.append(x)

    return lines


def get_letters_from_img(im):
    """Функция находит просветы между буквами изображения и вырезает буквы,
    предварительно обрезав вокруг каждой буквы фон, после функция
    вернет список изображений букв.

    """

    lines = border_letters(im)

    w, h = im.size

    # left -- просвет слева, для первой буквы будет равен 0
    left = 0
    top = 0
    bottom = h

    # Границей последней буквы будет ширина изображения
    lines.append(w)

    # Список для хранения букв
    letters = []

    for line in lines:
        # right - просвет справа
        right = line

        # Вырезаем букву
        letter_im = im.crop((left, top, right, bottom))

        # Убрезам фон вокруг буквы
        letter_im = crop_text(letter_im)

        letters.append(letter_im)

        # Для следующей буквы сдвигаем просвет слева
        # до просвета справа текущей буквы
        left = right

    return letters


def get_hash_mask_letter(letter_im):
    """Функция возвращает хеш маски изображения буквы."""

    str_bitarr = []
    w, h = letter_im.size

    for y in range(h):
        for x in range(w):
            pxl = letter_im.getpixel((x, y))

            # Если пиксель черный добавим в список '1', иначе '0'
            str_bitarr.append('1' if pxl == BLACK_PXL else '0')

    # Получим маску
    mask = ''.join(str_bitarr)

    # Подсчитаем хеш маски и будем по хешу определять буквы
    hash = hashlib.new('md5')
    hash.update(mask.encode())
    return hash.hexdigest()


import os
import string


# Папка с образцами цифр порта
LETTER_DIR = 'digits'


class PortImgParser:
    """Класс для парсинга изображения с номером порта."""

    def __init__(self):
        self.letter_mask = {}
        self.mask_letter = {}

        for file in os.listdir(LETTER_DIR):
            try:
                if '.png' in file:
                    name = file.replace('.png', '')
                    letter, mask = name.split('_')
                    self.letter_mask[letter] = mask
                    self.mask_letter[mask] = letter

            except ValueError as e:
                print('Обнаружен файл, имеющий нестандартное имя: {}, ошибка: {}'.format(file, e))

        all_letters = string.digits
        for letter in self.letter_mask.keys():
            all_letters = all_letters.replace(letter, '')

        if all_letters:
            print('Не хватает {} цифр(ы): {}\n'.format(len(all_letters), list(all_letters)))

    def run(self, img):
        """Функция принимает объект Image из модуля PIL, парсит его и
        возвращает распарсенную строку с текстом изображения.

        """

        im = img.convert('L')

        clear_img(im)
        im = crop_text(im)
        letters_img = get_letters_from_img(im)

        img_text = ''

        found_new_digit = set([file.replace('.png', '') for file in os.listdir(LETTER_DIR)])

        for im_letter in letters_img:
            # Получаем маску буквы
            mask = get_hash_mask_letter(im_letter)
            letter = self.mask_letter.get(mask)

            if letter is None:
                if mask not in found_new_digit:
                    full_file = os.path.join(LETTER_DIR, mask + '.png')
                    print('Найдена новая цифра mask={}. Сохраняю ее в {}. '
                          'Не забудь ее опознать!'.format(mask, full_file))
                    im_letter.save(full_file)

                    found_new_digit.add(mask)

                img_text += '-'
            else:
                img_text += letter

        return img_text
