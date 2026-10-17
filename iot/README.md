# ESP32 Gate Firmware (PlatformIO)

Arduino C++ firmware for the Smart IoT Parking gates. One code base runs in two
roles, selected by the PlatformIO build flags:

| Env | Role | Device code | Behaviour |
|-----|------|-------------|-----------|
| `esp32dev` / `entry_gate` | entry lane | `ENTRY_GATE_01` | car detected → **RFID entry scan** → backend session + `ENTRY_APPROVED` → gate opens → passage sensor → closes |
| `exit_gate` | exit lane | `EXIT_GATE_01` | car detected → **RFID exit scan** → backend fee + payment check → `EXIT_APPROVED` only when paid → gate opens |

The ultrasonic sensor alone can **never** open a gate — only a card scan that
the backend authorizes (and the resulting gate command) can.

---

## 1. Bill of materials

| Part | Qty | Notes |
|------|-----|-------|
| ESP32 DevKit (WROOM-32) | 1 per lane | 3.3 V logic |
| RC522 RFID module + MIFARE cards/tags | 1 + cards | **3.3 V only** |
| SG90 / MG996R servo | 1 | gate arm |
| HC-SR04 ultrasonic | 1 (approach) | existing wiring kept |
| HC-SR04 ultrasonic | 1 (passage safety) | optional but recommended (fail-safe) |
| 16x2 I2C LCD (PCF8574, addr 0x27) | 1 | existing wiring kept |
| Green + red LEDs (+ 220 Ω) | 2 | existing wiring kept |
| Buzzer (optional) | — | not used by this firmware |

## 2. Pin map

Existing pins are unchanged; new devices use free, non-conflicting GPIOs.

| Signal | GPIO | Notes |
|--------|------|-------|
| **Existing** | | |
| Vehicle presence HC-SR04 TRIG / ECHO | 5 / 18 | approach detector |
| Gate servo signal | 13 | 50 Hz PWM |
| Green LED / Red LED | 25 / 26 | gate state |
| LCD I²C SDA / SCL | 21 / 22 | addr `0x27` |
| **RC522 RFID (SPI, remapped to avoid GPIO 5/18)** | | |
| SDA / SS (CS) | 4 | |
| SCK | 14 | |
| MOSI | 23 | |
| MISO | 19 | |
| RST | 27 | |
| 3.3 V / GND | — | **never 5 V** |
| **Passage safety sensor (HC-SR04 #2)** | | |
| TRIG / ECHO | 32 / 33 | under the gate, watches the car cross |

```text
                 ESP32 DevKit (WROOM-32)
        +------------------------------------------+
 RC522  | 3V3  GND  4   14   23   19   27         |
 SDA -->| SS   SCK  MOSI MISO RST                  |
        |                                          |
 HC-SR04#1  VCC(5V)  TRIG=5   ECHO=18             |
 HC-SR04#2  VCC(5V)  TRIG=32  ECHO=33             |
        |  GPIO13 -> servo signal                  |
        |  GPIO25 -> green LED   GPIO26 -> red LED |
        |  GPIO21/22 -> I2C LCD (SDA/SCL)          |
        +------------------------------------------+
```

Wiring notes:

- **RC522 must be on 3.3 V.** 5 V will destroy it.
- HC-SR04 runs on 5 V; its `ECHO` output is 5 V. A simple divider
  (1 kΩ from ECHO to the pin, 2 kΩ from the pin to GND) keeps the ESP32 safe.
  Many boards tolerate it directly, but the divider is the correct wiring.
- RC522 SPI is remapped with `SPI.begin(14, 19, 23, 4)` — this is safe on the
  ESP32 (any GPIO can carry SPI through the GPIO matrix).
- Want to run without the passage sensor while testing? Set
  `PARKING_PASSAGE_SENSOR_ENABLED 0` in `include/parking_config.h`; the gate
  then closes when the approach sensor clears (less safe, for desk testing).

## 3. Configure secrets

```powershell
cd iot
Copy-Item include\parking_secrets.example.h include\parking_secrets.h
# edit include\parking_secrets.h:
#   PARKING_WIFI_SSID / PARKING_WIFI_PASSWORD
#   PARKING_API_BASE_URL   -> LAN IP of the PC running FastAPI, e.g. http://192.168.1.20:8000
#   PARKING_ENTRY_DEVICE_TOKEN / PARKING_EXIT_DEVICE_TOKEN (must match backend/.env)
```

`include/parking_secrets.h` is git-ignored — never commit real credentials.

Start the backend so the LAN can reach it:
`uvicorn app.main:app --host 0.0.0.0 --port 8000` (see repo README).
Allow port 8000 through the Windows Firewall on private networks.

## 4. Build, upload, monitor

```powershell
cd iot

pio run                      # build entry gate (default env)
pio run -e exit_gate         # build exit gate
pio run -e entry_gate -t upload --upload-port COM5
pio run -e exit_gate  -t upload --upload-port COM7
pio device monitor -b 115200
```

Expected boot log (entry gate example):

```text
=== Smart IoT Parking — ENTRY gate ===
Device ENTRY_GATE_01 -> http://192.168.1.20:8000
[RFID] RC522 online (version 0x92)
[BOOT] passage safety sensor enabled (fail-safe close)
[WiFi] Connecting to MyWifi ...
[GATE] CLOSED
```

Presentation: flash the *entry* build on the entry-lane ESP32 and the *exit*
build on the exit-lane ESP32. Same wiring, same modules.

## 5. Gate behaviour (firmware state machine)

Implemented in `lib/parking_core/src/gate_flow.h` (pure C++, unit-tested):

| State | Meaning | LCD |
|-------|---------|-----|
| `Closed` | idle | `Gate closed` |
| `WaitingCard` | car present | `Scan card to enter/exit` |
| `Authorizing` | scan sent, waiting for the approval command | `Checking card` |
| `PaymentPending` | exit: fee due | `Payment due $x.xx` |
| `Opening` / `OpenWaitingPass` | gate open | `Gate open` |
| `Closing` / `Closed` | car passed | `Gate closing` |
| `Denied` | blocked/unknown card etc. | `Access denied` |
| `FaultHoldOpen` | **fail-safe**: passage blocked or sensor fault | `FAILSAFE open` |

Fail-safe rules:

- The gate only opens after the backend queues `ENTRY_APPROVED`/`EXIT_APPROVED`
  (polled via `GET /api/iot/commands/next`) and never from the ultrasonic
  sensor alone.
- The gate never closes while the passage safety sensor reports an obstruction
  or a fault; it holds open, blinks the red LED and reports `gate_fault`.
- Approvals expire (`PARKING_COMMAND_VALIDITY_MS`, aligned with the backend
  `GATE_COMMAND_TIMEOUT_SECONDS` default 180 s). An approval for a car that
  never arrives is acknowledged back as *failed/expired* instead of opening
  the gate later.
- Sensor faults degrade safely: a broken approach sensor still allows card
  scans; a broken passage sensor blocks closing (hold open) instead of
  risking a car under the gate.
- Every gate command is acknowledged (`POST /api/iot/commands/ack`) and the
  gate posts `car_passed` / `gate_closed` / `gate_fault` events back.

## 6. Firmware unit tests (no hardware needed)

The pure logic (UID handling, duplicate-scan gate, fail-safe state machine) is
in `lib/parking_core` and is unit-tested on the PC:

```powershell
cd iot
pio test -e native
```

This needs a host C++ compiler on PATH (`gcc`/`g++`). On Windows install one
e.g. with `winget install MartinStorsjo.LLVM-MinGW.UCRT` (per-user, no admin)
or MinGW-w64/MSYS2, then reopen the terminal.
The 27 tests cover: UID formatting/normalization, duplicate-scan suppression,
full entry/exit flows, authorization timeouts, denials, passage-blocked
hold-open, sensor faults, approval latching/expiry, payment-pending flow and
the "ultrasonic alone never opens" safety rule.

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| LCD shows `RFID reader error` | RC522 not detected — check 3.3 V, SS=4, SCK=14, MOSI=23, MISO=19, RST=27 and that the cables are short |
| LCD shows `WiFi offline` | secrets SSID/password wrong, or ESP32 out of Wi-Fi range |
| Scan returns `Access denied — Card not registered` | register the card UID in the dashboard **RFID** page |
| Scan returns `Payment due $x.xx` at exit | expected — pay on the dashboard/Payment page or via ABA KHQR webhook; the gate opens when the backend queues `EXIT_APPROVED` |
| Gate scans but never opens | backend unreachable (check `PARKING_API_BASE_URL`, firewall), or the device token does not match `backend/.env` |
| Gate stays open with `FAILSAFE open` | obstruction under the gate or passage sensor fault/wiring — clear it; the gate closes automatically when safe |
| Servo jitters / resets | power the servo from a separate 5 V supply with a common ground |

Hardware checks that still require the physical build are listed at the end
of the root `README.md` (Phase validation report).
