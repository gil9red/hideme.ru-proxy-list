#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


if __name__ == '__main__':
    from hidemeru_parser import HidemeRuParser

    parser = HidemeRuParser()
    parser.run()
    parser.save()
