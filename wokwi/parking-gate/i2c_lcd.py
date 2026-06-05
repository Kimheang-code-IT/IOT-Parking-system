"""PCF8574 backpack for Wokwi wokwi-lcd1602 (I2C address 0x27 or 0x3F)."""

import time

from lcd_api import LcdApi


class I2cLcd(LcdApi):
    """I2C LCD driver — import: from i2c_lcd import I2cLcd"""

    def __init__(self, i2c, i2c_addr, num_lines=2, num_columns=16):
        self.i2c = i2c
        self.i2c_addr = i2c_addr
        self.display_data = 0x08  # backlight on (PCF8574 P3)
        self.i2c.writeto(self.i2c_addr, b"\x00")
        time.sleep_ms(50)
        super().__init__(num_lines, num_columns)

    def hal_write_init_nibble(self, nibble):
        nibble = nibble & 0x0F
        buf = bytearray(1)
        buf[0] = (nibble << 4) | self.display_data
        self.i2c.writeto(self.i2c_addr, buf)
        buf[0] |= 0x04  # EN high
        self.i2c.writeto(self.i2c_addr, buf)
        buf[0] &= 0xFB  # EN low
        self.i2c.writeto(self.i2c_addr, buf)
        time.sleep_ms(2)

    def hal_write_byte(self, value, rs):
        high = value & 0xF0
        low = (value << 4) & 0xF0
        self._write4bits(high, rs)
        self._write4bits(low, rs)

    def _write4bits(self, value, rs):
        value = value & 0xF0
        buf = bytearray(1)
        buf[0] = value | self.display_data | rs
        self.i2c.writeto(self.i2c_addr, buf)
        buf[0] |= 0x04
        self.i2c.writeto(self.i2c_addr, buf)
        buf[0] &= 0xFB
        self.i2c.writeto(self.i2c_addr, buf)
        time.sleep_us(100)
