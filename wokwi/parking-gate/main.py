"""
IOT Parking — Wokwi combined gate simulator (MicroPython).

Buttons replace PC cameras (Wokwi cannot use host webcam).
Set API_HOST to your PC LAN IP running FastAPI on port 8000.

Serial commands (optional): ENTRY_SCAN, EXIT_INVOICE <hash>, EXIT_PLATE <plate>, PAY_OK
"""

import json
import time
from machine import Pin, PWM, I2C

try:
    import network
    import urequests
except ImportError:
    network = None
    urequests = None

# --- Config: change API_HOST to your computer LAN IP ---
API_HOST = "192.168.0.100"
API_PORT = 8000
DEVICE_CODE = "GATE_SIM_01"
DEVICE_TOKEN = "secret-entry-token"
WEBHOOK_SECRET = "change-me-webhook-secret"

SIM_PLATE = "WK-SIM01"
SIM_VERIFY = "SIMHASH00001"

# Pins
PIN_SERVO_ENTRY = 18
PIN_SERVO_EXIT = 19
PIN_LED_GREEN = 25
PIN_LED_RED = 26
PIN_BUZZER = 33
PIN_BTN_ENTRY_SCAN = 27
PIN_BTN_ENTRY_CLOSE = 14
PIN_BTN_INVOICE = 12
PIN_BTN_EXIT_PLATE = 13
PIN_BTN_PAY_OK = 15
PIN_BTN_EXIT_CLOSE = 4
I2C_SCL = 22
I2C_SDA = 21

OPEN_ANGLE = 90
CLOSED_ANGLE = 0

state = {
    "verify_hash": SIM_VERIFY,
    "exit_plate": SIM_PLATE,
    "last_invoice_id": None,
    "last_session_id": None,
    "entry_open": False,
    "exit_open": False,
}


class Lcd1602:
    """Minimal I2C LCD (0x27). Falls back to Serial if LCD init fails."""

    def __init__(self):
        self.ok = False
        try:
            self.i2c = I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=400000)
            self.addr = 0x27
            self._write4(0x03)
            time.sleep_ms(5)
            self._write4(0x03)
            time.sleep_ms(1)
            self._write4(0x03)
            self._write4(0x02)
            self._cmd(0x28)
            self._cmd(0x0C)
            self._cmd(0x06)
            self.ok = True
            self.show("IOT Parking", "Wokwi ready")
        except Exception as exc:
            print("LCD init:", exc)

    def _write4(self, n):
        buf = bytearray([n << 4 | 0x04 | 0x08, n << 4 | 0x04, n << 4 | 0x08, n << 4])
        self.i2c.writeto(self.addr, buf)
        time.sleep_ms(2)

    def _cmd(self, c):
        self._write4(c >> 4)
        self._write4(c & 0x0F)

    def _data(self, c):
        self._write4((c >> 4) | 0x01)
        self._write4((c & 0x0F) | 0x01)

    def show(self, line1, line2=""):
        line1 = (line1 or "")[:16]
        line2 = (line2 or "")[:16]
        print("LCD:", line1, "|", line2)
        if not self.ok:
            return
        self._cmd(0x80)
        for ch in line1.ljust(16):
            self._data(ord(ch))
        self._cmd(0xC0)
        for ch in line2.ljust(16):
            self._data(ord(ch))


def servo_angle(pwm, deg):
    deg = max(0, min(180, deg))
    duty = int(26 + (deg / 180) * 102)
    pwm.duty(duty)


def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect("Wokwi-GUEST", "")
    print("WiFi connecting", end="")
    for _ in range(40):
        if wlan.isconnected():
            print("\nWiFi OK", wlan.ifconfig())
            return True
        print(".", end="")
        time.sleep_ms(500)
    print("\nWiFi failed")
    return False


def api_url(path):
    return "http://{}:{}{}".format(API_HOST, API_PORT, path)


def http_post(path, body, iot=True, webhook=False):
    headers = {"Content-Type": "application/json"}
    if iot:
        headers["x-device-code"] = DEVICE_CODE
        headers["x-device-token"] = DEVICE_TOKEN
    if webhook:
        headers["x-webhook-secret"] = WEBHOOK_SECRET
    url = api_url(path)
    print("POST", path, body)
    r = urequests.post(url, data=json.dumps(body), headers=headers)
    text = r.text
    code = r.status_code
    r.close()
    print(" ->", code, text[:200])
    if code >= 400:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def http_get(path, iot=True):
    headers = {}
    if iot:
        headers["x-device-code"] = DEVICE_CODE
        headers["x-device-token"] = DEVICE_TOKEN
    url = api_url(path)
    r = urequests.get(url, headers=headers)
    text = r.text
    code = r.status_code
    r.close()
    if code == 204 or not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def set_ok(lcd, msg):
    led_green.value(1)
    led_red.value(0)
    lcd.show(msg[:16], "OK")


def set_err(lcd, msg):
    led_green.value(0)
    led_red.value(1)
    buzzer.value(1)
    time.sleep_ms(400)
    buzzer.value(0)
    lcd.show("ERROR", msg[:16])


def open_entry_gate():
    servo_angle(servo_entry, OPEN_ANGLE)
    state["entry_open"] = True


def close_entry_gate():
    servo_angle(servo_entry, CLOSED_ANGLE)
    state["entry_open"] = False
    http_post(
        "/api/iot/gate/event",
        {"deviceCode": DEVICE_CODE, "event": "entry_gate_closed", "sessionId": state["last_session_id"]},
    )


def open_exit_gate():
    servo_angle(servo_exit, OPEN_ANGLE)
    state["exit_open"] = True


def close_exit_gate():
    servo_angle(servo_exit, CLOSED_ANGLE)
    state["exit_open"] = False
    http_post(
        "/api/iot/gate/event",
        {"deviceCode": DEVICE_CODE, "event": "exit_gate_closed", "sessionId": state["last_session_id"]},
    )


def run_entry_scan(lcd):
    lcd.show("Entry scan...", SIM_PLATE)
    res = http_post(
        "/api/gate/entry/process",
        {
            "licensePlate": SIM_PLATE,
            "vehicleType": "Car",
            "source": "simulator",
            "targetDevice": "GATE_SIM_01",
        },
        iot=False,
    )
    if not res or not res.get("success"):
        set_err(lcd, (res or {}).get("message", "Entry fail")[:16])
        return
    gc = res.get("gateCommand") or {}
    state["last_session_id"] = gc.get("sessionId")
    state["last_invoice_id"] = gc.get("invoiceId")
    pd = gc.get("printData") or res.get("printData")
    if pd and pd.get("verifyHash"):
        state["verify_hash"] = pd["verifyHash"]
    if gc.get("command") == "ENTRY_APPROVED" or res.get("executeOnDevice"):
        open_entry_gate()
        set_ok(lcd, "ENTRY APPROVED")
        lcd.show("Gate OPEN", "Pass vehicle")
    else:
        set_err(lcd, "No approval")


def run_exit_flow(lcd):
    lcd.show("Exit verify...", state["exit_plate"][:16])
    res = http_post(
        "/api/gate/exit/process",
        {
            "verifyHash": state["verify_hash"],
            "licensePlate": state["exit_plate"],
            "source": "simulator",
            "targetDevice": "GATE_SIM_01",
            "requirePaid": True,
        },
        iot=False,
    )
    if not res:
        set_err(lcd, "HTTP error")
        return
    gc = res.get("gateCommand") or {}
    cmd = gc.get("command", "")
    if cmd == "EXIT_APPROVED" and res.get("success"):
        state["last_session_id"] = gc.get("sessionId")
        open_exit_gate()
        set_ok(lcd, "EXIT APPROVED")
        lcd.show("Gate OPEN", "Pass vehicle")
    else:
        set_err(lcd, (gc.get("message") or res.get("message", "Denied"))[:16])


def payment_success(lcd):
    inv = state.get("last_invoice_id") or "IN-000001"
    http_post(
        "/api/payment/webhook",
        {
            "invoiceId": inv,
            "amount": 2.0,
            "paymentMethod": "KHQR",
            "success": True,
        },
        iot=False,
        webhook=True,
    )
    set_ok(lcd, "Payment OK")
    time.sleep_ms(300)
    run_exit_flow(lcd)


def poll_commands(lcd):
    res = http_get("/api/iot/commands/next?deviceCode=" + DEVICE_CODE)
    if not res:
        return
    cmd = res.get("command")
    cid = res.get("commandId")
    print("Poll command:", cmd)
    if cmd == "ENTRY_APPROVED":
        open_entry_gate()
        set_ok(lcd, "ENTRY APPROVED")
    elif cmd == "EXIT_APPROVED":
        open_exit_gate()
        set_ok(lcd, "EXIT APPROVED")
    elif cmd == "EXIT_DENIED":
        set_err(lcd, res.get("message", "Denied")[:16])
    if cid:
        http_post(
            "/api/iot/commands/ack",
            {"deviceCode": DEVICE_CODE, "commandId": cid, "status": "completed"},
        )


def read_btn(pin, last):
    v = pin.value()
    pressed = last == 1 and v == 0
    return v, pressed


# --- Setup ---
led_green = Pin(PIN_LED_GREEN, Pin.OUT)
led_red = Pin(PIN_LED_RED, Pin.OUT)
buzzer = Pin(PIN_BUZZER, Pin.OUT)
servo_entry = PWM(Pin(PIN_SERVO_ENTRY), freq=50)
servo_exit = PWM(Pin(PIN_SERVO_EXIT), freq=50)
servo_angle(servo_entry, CLOSED_ANGLE)
servo_angle(servo_exit, CLOSED_ANGLE)

buttons = {
    "entry_scan": Pin(PIN_BTN_ENTRY_SCAN, Pin.IN, Pin.PULL_UP),
    "entry_close": Pin(PIN_BTN_ENTRY_CLOSE, Pin.IN, Pin.PULL_UP),
    "invoice": Pin(PIN_BTN_INVOICE, Pin.IN, Pin.PULL_UP),
    "exit_plate": Pin(PIN_BTN_EXIT_PLATE, Pin.IN, Pin.PULL_UP),
    "pay_ok": Pin(PIN_BTN_PAY_OK, Pin.IN, Pin.PULL_UP),
    "exit_close": Pin(PIN_BTN_EXIT_CLOSE, Pin.IN, Pin.PULL_UP),
}
last_btn = {k: 1 for k in buttons}

lcd = Lcd1602()
print("\n=== IOT Parking Gate Simulator ===")
if network:
    wifi_connect()

while True:
    for name, pin in buttons.items():
        last_btn[name], pressed = read_btn(pin, last_btn[name])
        if not pressed:
            continue
        time.sleep_ms(80)
        if name == "entry_scan":
            run_entry_scan(lcd)
        elif name == "entry_close":
            close_entry_gate()
            http_post(
                "/api/iot/gate/event",
                {"deviceCode": DEVICE_CODE, "event": "entry_car_passed", "sessionId": state["last_session_id"]},
            )
            lcd.show("Entry closed", "")
        elif name == "invoice":
            state["verify_hash"] = SIM_VERIFY
            lcd.show("Invoice scanned", SIM_VERIFY[:16])
        elif name == "exit_plate":
            state["exit_plate"] = SIM_PLATE
            lcd.show("Plate scanned", SIM_PLATE)
        elif name == "pay_ok":
            payment_success(lcd)
        elif name == "exit_close":
            close_exit_gate()
            lcd.show("Exit closed", "")
        time.sleep_ms(200)

    poll_commands(lcd)
    time.sleep_ms(300)
