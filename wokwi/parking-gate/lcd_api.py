"""HD44780 LCD base driver (MicroPython) — robert-hh / Wokwi-compatible."""

import time
from micropython import const


class LcdApi:
    LCD_CLR = const(0x01)
    LCD_HOME = const(0x02)
    LCD_ENTRYMODE = const(0x04)
    LCD_DISPLAYON = const(0x0C)
    LCD_DISPLAYOFF = const(0x08)
    LCD_FUNCTIONSET = const(0x20)
    LCD_SETDDRAM = const(0x80)

    LCD_4BITMODE = const(0x00)
    LCD_2LINE = const(0x08)
    LCD_5x8DOTS = const(0x00)
    LCD_ENTRYLEFT = const(0x02)

    LCD_8BITMODE = const(0x10)

    def __init__(self, num_lines, num_columns):
        self.num_lines = num_lines
        self.num_columns = num_columns
        self.cursor_x = 0
        self.cursor_y = 0
        self.implied_newline = False

        self.hal_write_init_nibble(0x03)
        time.sleep_ms(5)
        self.hal_write_init_nibble(0x03)
        time.sleep_ms(1)
        self.hal_write_init_nibble(0x03)
        time.sleep_ms(1)
        self.hal_write_init_nibble(0x02)

        self.hal_write_command(self.LCD_FUNCTIONSET | self.LCD_4BITMODE | self.LCD_2LINE | self.LCD_5x8DOTS)
        self.hal_write_command(self.LCD_DISPLAYON)
        self.hal_write_command(self.LCD_ENTRYMODE | self.LCD_ENTRYLEFT)
        self.clear()

    def clear(self):
        self.hal_write_command(self.LCD_CLR)
        time.sleep_ms(2)
        self.hal_write_command(self.LCD_HOME)
        self.cursor_x = 0
        self.cursor_y = 0

    def move_to(self, col, row):
        self.cursor_x = col
        self.cursor_y = row
        addr = col & 0x3F
        if row & 1:
            addr += 0x40
        if row & 2:
            addr += 0x14
        self.hal_write_command(self.LCD_SETDDRAM | addr)

    def putstr(self, string):
        for ch in string:
            self.putchar(ch)

    def putchar(self, ch):
        if ch == "\n":
            self.cursor_x = 0
            self.cursor_y = (self.cursor_y + 1) % self.num_lines
            self.move_to(self.cursor_x, self.cursor_y)
        else:
            self.hal_write_data(ord(ch))
            self.cursor_x += 1

    def write_line(self, row, text):
        """Write exactly one row (16 cols), no auto-wrap."""
        text = (str(text) + " " * self.num_columns)[: self.num_columns]
        self.move_to(0, row)
        for ch in text:
            self.hal_write_data(ord(ch))
        self.cursor_x = 0
        self.cursor_y = row

    def hal_write_command(self, cmd):
        self.hal_write_byte(cmd, 0)

    def hal_write_data(self, data):
        self.hal_write_byte(data, 1)

    def hal_write_byte(self, value, rs):
        raise NotImplementedError

    def hal_write_init_nibble(self, nibble):
        raise NotImplementedError
