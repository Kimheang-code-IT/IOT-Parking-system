"""
IOT Parking — Wokwi ESP32 (entry/exit buttons + FastAPI).

LCD test lines shown first, then gate + API logic.
"""

import json
import sys
import time
from machine import I2C, Pin, PWM, SoftI2C

print("Booting...")

try:
    from i2c_lcd import I2cLcd

    print("Import OK: i2c_lcd.I2cLcd")
except ImportError as e:
    print("IMPORT ERROR:", e)
    print("Add lcd_api.py and i2c_lcd.py to this Wokwi project folder.")
    raise

try:
    import network
    import urequests
except ImportError:
    network = None
    urequests = None

# --- config ---
API_HOST = "host.wokwi.internal"
API_PORT = 8000
SIM_PLATE = "WK-SIM01"

PIN_SERVO_ENTRY = 18
PIN_SERVO_EXIT = 19
PIN_BTN_ENTRY = 27
PIN_BTN_EXIT = 12
I2C_SDA = 21
I2C_SCL = 22

OPEN_ANGLE = 90
CLOSED_ANGLE = 0
AUTO_CLOSE_SECONDS = 5
EXIT_AUTO_CLOSE_SECONDS = 20
PAYMENT_POLL_SECONDS = 120
PAYMENT_POLL_INTERVAL_MS = 2000
# Entry/exit: PC webcam OCR via FastAPI (OpenCV on the machine running uvicorn)
USE_GATE_CAMERA = True

# Set False to skip API/WiFi and only test LCD + buttons
RUN_GATE_API = True

state = {
    "verify_hash": None,
    "invoice_id": None,
    "session_id": None,
    "plate": SIM_PLATE,
    "entry_close_at": None,
    "exit_close_at": None,
    "exit_opened": False,
}

last_payment_poll_at = 0


def make_i2c():
    """Hardware I2C first, then SoftI2C (both work on Wokwi ESP32)."""
    try:
        return I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=100000)
    except Exception as exc:
        print("I2C(0) failed:", exc, "-> SoftI2C")
        return SoftI2C(scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=100000)


def scan_i2c(i2c):
    raw = i2c.scan()
    print("Scanning I2C...")
    print("I2C devices:", raw)
    for a in raw:
        print("  addr", a, "= 0x{:02X}".format(a))
    return raw


def pick_lcd_addr(found):
    """39 decimal = 0x27, 63 decimal = 0x3F."""
    for addr in (0x27, 0x3F):
        if addr in found:
            return addr
    return None


class Lcd1602:
    def __init__(self):
        self.ok = False
        self.lcd = None
        time.sleep_ms(300)
        print("Init LCD on SDA={} SCL={}".format(I2C_SDA, I2C_SCL))
        try:
            i2c = make_i2c()
            found = scan_i2c(i2c)
            if not found:
                print("ERROR: i2c.scan() returned [] — fix diagram.json wiring to lcd:SDA / lcd:SCL")
                return
            addr = pick_lcd_addr(found)
            if addr is None:
                print("ERROR: no LCD at 0x27 or 0x3F. Found:", [hex(x) for x in found])
                return
            print("Using LCD address 0x{:02X} ({})".format(addr, addr))
            self.lcd = I2cLcd(i2c, addr, 2, 16)
            self.ok = True
            self.show("IOT Parking", "LCD Working")
            print("LCD test OK")
        except Exception as exc:
            print("LCD init failed:", exc)
            sys.print_exception(exc)

    def show(self, line1, line2=""):
        print("LCD:", line1, "|", line2)
        if not self.ok or not self.lcd:
            return
        self.lcd.write_line(0, line1)
        self.lcd.write_line(1, line2)


def servo_set(pwm, deg):
    deg = max(0, min(180, deg))
    pwm.duty(int(26 + (deg / 180) * 102))


def get_json(path):
    url = "http://{}:{}{}".format(API_HOST, API_PORT, path)
    print("GET", url)
    try:
        r = urequests.get(url, timeout=15)
        code = r.status_code
        text = r.text
        r.close()
    except Exception as exc:
        print("HTTP fail:", exc)
        return None, str(exc)[:32]
    if code >= 400:
        return None, "HTTP {}".format(code)
    try:
        return json.loads(text), None
    except Exception:
        return None, "bad JSON"


def post_json(path, body):
    """Returns (parsed_json_or_none, error_message_or_none). API errors still return JSON body."""
    url = "http://{}:{}{}".format(API_HOST, API_PORT, path)
    print("POST", path)
    try:
        r = urequests.post(
            url,
            data=json.dumps(body),
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        code = r.status_code
        text = r.text
        r.close()
    except Exception as exc:
        print("HTTP fail:", exc)
        return None, str(exc)[:32]
    print(code, text[:200])
    try:
        data = json.loads(text)
    except Exception:
        return None, "HTTP {} bad JSON".format(code)
    if code >= 400:
        msg = data.get("message")
        if not msg and isinstance(data.get("detail"), dict):
            msg = data["detail"].get("message")
        if not msg:
            msg = text[:32]
        return data, str(msg)[:48]
    if not data.get("success", True):
        return data, (data.get("message") or "failed")[:48]
    return data, None


def schedule_close(which, seconds):
    deadline = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    if which == "entry":
        state["entry_close_at"] = deadline
    else:
        state["exit_close_at"] = deadline


def check_auto_close(servo_entry, servo_exit):
    now = time.ticks_ms()
    if state["entry_close_at"] and time.ticks_diff(now, state["entry_close_at"]) >= 0:
        servo_set(servo_entry, CLOSED_ANGLE)
        state["entry_close_at"] = None
        lcd.show("Entry closed", "")
    if state["exit_close_at"] and time.ticks_diff(now, state["exit_close_at"]) >= 0:
        servo_set(servo_exit, CLOSED_ANGLE)
        state["exit_close_at"] = None
        lcd.show("Exit closed", "")


def entry_button(servo_entry):
    print(">>> ENTRY button")
    lcd.show("Entry...", "PC camera OCR")
    body = {
        "source": "simulator",
        "useCamera": USE_GATE_CAMERA,
        "autoCloseSeconds": AUTO_CLOSE_SECONDS,
    }
    if not USE_GATE_CAMERA:
        body["mockPlate"] = SIM_PLATE
    res, err = post_json("/api/gate/entry/trigger", body)
    if not res:
        lcd.show("NO API", (err or "network")[:16])
        return
    if err or not res.get("success"):
        lcd.show("ENTRY FAIL", (err or res.get("message", ""))[:16])
        return
    state["invoice_id"] = res.get("invoiceId")
    state["session_id"] = res.get("sessionId")
    state["verify_hash"] = res.get("verifyHash")
    plate = res.get("plateNumber") or SIM_PLATE
    state["plate"] = plate
    state["exit_opened"] = False
    servo_set(servo_entry, OPEN_ANGLE)
    sec = res.get("autoCloseSeconds") or AUTO_CLOSE_SECONDS
    schedule_close("entry", sec)
    lcd.show("ENTRY OPEN", str(plate)[:16])


def check_auto_exit_on_payment(servo_entry, servo_exit):
    """When dashboard payment succeeds, open exit servo — no exit button needed."""
    global last_payment_poll_at
    inv = state.get("invoice_id")
    vhash = state.get("verify_hash")
    if not inv or not vhash or state.get("exit_opened"):
        return
    now = time.ticks_ms()
    if time.ticks_diff(now, last_payment_poll_at) < PAYMENT_POLL_INTERVAL_MS:
        return
    last_payment_poll_at = now
    path = "/api/payment/status?invoiceId={}&verifyHash={}".format(inv, vhash)
    data, err = get_json(path)
    if err or not data or not data.get("paid"):
        return
    plate = data.get("plateNumber") or state.get("plate") or SIM_PLATE
    print("Payment OK — auto opening exit gate")
    lcd.show("Payment OK", "Exit opening")
    servo_set(servo_exit, OPEN_ANGLE)
    schedule_close("exit", EXIT_AUTO_CLOSE_SECONDS)
    state["exit_opened"] = True
    lcd.show("EXIT OPEN", str(plate)[:16])
    print("Exit gate open for {}s".format(EXIT_AUTO_CLOSE_SECONDS))


def exit_button(servo_entry, servo_exit):
    """Exit is automatic after payment — button shows hint only."""
    print(">>> EXIT button (auto exit after pay)")
    lcd.show("Pay on web", "Auto exit gate")


# ========== main ==========
lcd = Lcd1602()

if not lcd.ok:
    print("HALT: fix LCD wiring / I2C — see Serial Monitor above")
    while True:
        time.sleep_ms(1000)

time.sleep_ms(2)

servo_entry = PWM(Pin(PIN_SERVO_ENTRY), freq=50)
servo_exit = PWM(Pin(PIN_SERVO_EXIT), freq=50)
servo_set(servo_entry, CLOSED_ANGLE)
servo_set(servo_exit, CLOSED_ANGLE)
btn_entry = Pin(PIN_BTN_ENTRY, Pin.IN, Pin.PULL_UP)
btn_exit = Pin(PIN_BTN_EXIT, Pin.IN, Pin.PULL_UP)
last_e, last_x = 1, 1


def button_pressed(last_val, cur_val):
    """Wokwi: btn between GND and GPIO + PULL_UP -> LOW when pressed."""
    return last_val == 1 and cur_val == 0

if not RUN_GATE_API:
    lcd.show("LCD only mode", "Press buttons")
    while True:
        e, ex = btn_entry.value(), btn_exit.value()
        if button_pressed(last_e, e):
            lcd.show("Entry btn", "OK")
        if button_pressed(last_x, ex):
            lcd.show("Exit btn", "OK")
        last_e, last_x = e, ex
        time.sleep_ms(50)

print("\n=== Parking gate + API ===")
print("API http://{}:{}".format(API_HOST, API_PORT))

if network:
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect("Wokwi-GUEST", "")
    wifi_ok = False
    for _ in range(40):
        if wlan.isconnected():
            print("WiFi OK", wlan.ifconfig())
            wifi_ok = True
            break
        time.sleep_ms(500)
    if wifi_ok:
        lcd.show("WiFi OK", "Checking API")
    else:
        lcd.show("WiFi FAIL", "No network")

    ping, ping_err = get_json("/health")
    if ping_err:
        lcd.show("API offline", ping_err[:16])
    elif ping:
        lcd.show("API online", "Press buttons")
else:
    lcd.show("No network lib", "Buttons only")

while True:
    check_auto_close(servo_entry, servo_exit)
    check_auto_exit_on_payment(servo_entry, servo_exit)
    e, ex = btn_entry.value(), btn_exit.value()
    if button_pressed(last_e, e):
        time.sleep_ms(80)
        entry_button(servo_entry)
    elif button_pressed(last_x, ex):
        time.sleep_ms(80)
        exit_button(servo_entry, servo_exit)
    last_e, last_x = e, ex
    time.sleep_ms(20)
