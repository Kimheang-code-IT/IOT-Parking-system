// ---------------------------------------------------------------------------
// Smart IoT Parking — ESP32 gate firmware (Arduino C++ / PlatformIO)
//
// One binary, two roles (build flags in platformio.ini):
//   -e entry_gate  PARKING_GATE_ROLE=1  ENTRY_GATE_01
//   -e exit_gate   PARKING_GATE_ROLE=2  EXIT_GATE_01
//
// Entry workflow (RFID drives authorization — ultrasonic never opens alone):
//   1. the approach sensor detects a car       -> LCD "Scan card to enter"
//   2. the RC522 reads a card                  -> POST /api/rfid/entry-scan
//   3. backend registers card+session, prints the receipt and queues
//      ENTRY_APPROVED for this device          -> poll /api/iot/commands/next
//   4. the gate opens, the passage safety sensor watches the car pass,
//      the gate closes and both events + the command ack are posted back.
//
// Exit workflow:
//   1. car at the exit gate                    -> LCD "Scan card to exit"
//   2. card scanned                            -> POST /api/rfid/exit-scan
//   3. backend finds the active session by card, calculates the fee
//      - paid      -> EXIT_APPROVED queued    -> gate opens
//      - unpaid    -> LCD shows the fee, gate stays closed until the
//                     ABA KHQR webhook / dashboard payment marks it paid
//                     (backend then queues EXIT_APPROVED automatically)
//
// Fail-safe rules (lib/parking_core/src/gate_flow.h):
//   - the gate never closes while the passage safety sensor reports an
//     obstruction or a fault; it holds open and reports a gate fault
//   - approvals expire (PARKING_COMMAND_VALIDITY_MS, keep in sync with the
//     backend GATE_COMMAND_TIMEOUT_SECONDS) and are acked as failed
//   - a missing approval never opens the gate; scans time out into a retry
// ---------------------------------------------------------------------------

#include <Arduino.h>

#include <gate_flow.h>

#include "api_client.h"
#include "gate_hardware.h"
#include "parking_config.h"
#include "rfid_reader.h"
#include "ultrasonic_sensor.h"
#include "wifi_manager.h"

using parking::FlowEvent;
using parking::FlowState;
using parking::GateFlow;
using parking::GateFlowConfig;
using parking::GateFlowInputs;
using parking::GateFlowOutputs;
using parking::GateRole;

namespace {

const GateRole kRole =
    (PARKING_GATE_ROLE == PARKING_ROLE_EXIT) ? GateRole::Exit : GateRole::Entry;

const char *roleName() { return kRole == GateRole::Exit ? "EXIT" : "ENTRY"; }
const char *carPassedEvent() { return kRole == GateRole::Exit ? "exit_car_passed" : "entry_car_passed"; }
const char *gateClosedEvent() { return kRole == GateRole::Exit ? "exit_gate_closed" : "entry_gate_closed"; }

GateFlowConfig buildFlowConfig() {
    GateFlowConfig cfg;
    cfg.authTimeoutMs = PARKING_AUTH_TIMEOUT_MS;
    cfg.denialHoldMs = PARKING_DENIAL_HOLD_MS;
    cfg.passTimeoutMs = PARKING_PASS_TIMEOUT_MS;
    cfg.minOpenMs = PARKING_MIN_OPEN_MS;
    cfg.paymentTimeoutMs = PARKING_PAYMENT_TIMEOUT_MS;
    cfg.paymentAbsenceGraceMs = PARKING_PAYMENT_ABSENCE_GRACE_MS;
    cfg.commandValidityMs = PARKING_COMMAND_VALIDITY_MS;
    cfg.passageSensorEnabled = PARKING_PASSAGE_SENSOR_ENABLED != 0;
    return cfg;
}

// ---------------------------------------------------------------- hardware
UltrasonicSensor presenceSensor(PARKING_TRIG_PIN, PARKING_ECHO_PIN);
#if PARKING_PASSAGE_SENSOR_ENABLED
UltrasonicSensor passageSensor(PARKING_PASSAGE_TRIG_PIN, PARKING_PASSAGE_ECHO_PIN);
#endif

GateHardware gateHardware(PARKING_SERVO_PIN,
                          PARKING_GREEN_LED_PIN,
                          PARKING_RED_LED_PIN,
                          PARKING_LCD_I2C_ADDR,
                          PARKING_LCD_COLS,
                          PARKING_LCD_ROWS,
                          PARKING_I2C_SDA_PIN,
                          PARKING_I2C_SCL_PIN);

RfidReader rfidReader(PARKING_RFID_SS_PIN,
                      PARKING_RFID_RST_PIN,
                      PARKING_RFID_SCK_PIN,
                      PARKING_RFID_MOSI_PIN,
                      PARKING_RFID_MISO_PIN,
                      PARKING_RFID_RESCAN_COOLDOWN_MS);

WifiManager wifi(PARKING_WIFI_SSID, PARKING_WIFI_PASSWORD, PARKING_WIFI_RETRY_MS);
ParkingApiClient api(PARKING_API_BASE_URL, PARKING_DEVICE_CODE, PARKING_DEVICE_TOKEN);
GateFlow flow(kRole, buildFlowConfig());

// ---------------------------------------------------------------- runtime state
bool vehiclePresent = false;
bool vehicleDetectorHealthy = true;
int presenceBadReads = 0;

bool passageBlocked = false;
bool passageHealthy = true;
int passageBadReads = 0;

char scannedUid[16] = {0};

// one-shot inputs consumed by GateFlow on the next update() call
bool inCardScanned = false;
bool inAuthApproved = false;
bool inAuthDenied = false;
bool inAuthIgnored = false;
bool inPaymentPending = false;
bool inCommandApproved = false;
bool inCommandDenied = false;

// session context for events, LCD and fee display
String activeSessionId;
String activePlate;
String denialMessage;
bool dueHasAmount = false;
float dueAmount = 0.0f;

// command bookkeeping
String pendingCommandId;
String pendingCommandSession;
String pendingCommandPlate;
bool pendingCommandHasAmount = false;
float pendingCommandAmount = 0.0f;

String latchedCommandId;
String latchedCommandSession;
String latchedCommandPlate;

String deniedCommandId;

uint32_t lastSensorMs = 0;
uint32_t lastPollMs = 0;
uint32_t lastHeartbeatMs = 0;

const char *faultDetail() {
#if PARKING_PASSAGE_SENSOR_ENABLED
    if (!passageHealthy) return "passage sensor fault";
    if (passageBlocked) return "passage blocked";
    return "passage timeout";
#else
    if (!vehicleDetectorHealthy) return "vehicle detector fault";
    return "passage timeout";
#endif
}

void readSensors() {
    float distance = 0.0f;

    if (presenceSensor.readCm(distance)) {
        presenceBadReads = 0;
        vehicleDetectorHealthy = true;
        if (distance <= PARKING_PRESENCE_CM) {
            vehiclePresent = true;
        } else if (distance >= PARKING_PRESENCE_CLEAR_CM) {
            vehiclePresent = false;
        }
    } else if (++presenceBadReads >= PARKING_SENSOR_FAULT_READS) {
        vehicleDetectorHealthy = false;
    }

#if PARKING_PASSAGE_SENSOR_ENABLED
    if (passageSensor.readCm(distance)) {
        passageBadReads = 0;
        passageHealthy = true;
        passageBlocked = (distance <= PARKING_PASSAGE_CM);
    } else if (++passageBadReads >= PARKING_SENSOR_FAULT_READS) {
        passageHealthy = false;
    }
#else
    passageHealthy = true;
    passageBlocked = false;
#endif
}

void performScan() {
    Serial.printf("[RFID] %s scan: %s\n", roleName(), scannedUid);

    if (!wifi.connected()) {
        inAuthDenied = true;
        denialMessage = "WiFi offline";
        Serial.println("[RFID] no Wi-Fi - cannot authorize");
        return;
    }

    const ScanResult result =
        (kRole == GateRole::Exit) ? api.exitScan(scannedUid) : api.entryScan(scannedUid);

    switch (result.outcome) {
        case ScanOutcome::Authorized:
            Serial.printf("[RFID] authorized plate=%s session=%s\n",
                          result.plateNumber.c_str(), result.sessionId.c_str());
            activeSessionId = result.sessionId;
            activePlate = result.plateNumber;
            inAuthApproved = true;
            break;
        case ScanOutcome::PaymentPending:
            Serial.printf("[RFID] payment pending plate=%s fee=%.2f\n",
                          result.plateNumber.c_str(), result.amount);
            activeSessionId = result.sessionId;
            activePlate = result.plateNumber;
            dueAmount = result.amount;
            dueHasAmount = result.hasAmount;
            inPaymentPending = true;
            break;
        case ScanOutcome::Duplicate:
            Serial.println("[RFID] duplicate scan ignored by backend");
            inAuthIgnored = true;
            break;
        case ScanOutcome::Denied:
        case ScanOutcome::Failed:
        default:
            Serial.printf("[RFID] denied: %s\n", result.message.c_str());
            denialMessage = result.message.isEmpty() ? String("Access denied") : result.message;
            inAuthDenied = true;
            break;
    }
}

void handleCommand(const PendingCommand &cmd) {
    Serial.printf("[CMD] %s id=%s\n", cmd.command.c_str(), cmd.commandId.c_str());

    if (cmd.command == "EXIT_DENIED") {
        deniedCommandId = cmd.commandId;
        inCommandDenied = true;
        return;
    }

    // ENTRY_APPROVED / EXIT_APPROVED
    if (flow.state() == FlowState::Opening || flow.state() == FlowState::OpenWaitingPass) {
        api.ackCommand(cmd.commandId, true, "Gate already open");
        return;
    }

    pendingCommandId = cmd.commandId;
    pendingCommandSession = cmd.sessionId;
    pendingCommandPlate = cmd.plateNumber;
    pendingCommandAmount = cmd.amount;
    pendingCommandHasAmount = cmd.hasAmount;
    inCommandApproved = true;
}

void resolveCommandOutcome(const GateFlowOutputs &out, bool fedApproval) {
    if (fedApproval) {
        if (out.event == FlowEvent::Approved) {
            activeSessionId = pendingCommandSession;
            if (!pendingCommandPlate.isEmpty()) {
                activePlate = pendingCommandPlate;
            }
            if (pendingCommandHasAmount) {
                dueAmount = pendingCommandAmount;
                dueHasAmount = true;
            }
            api.ackCommand(pendingCommandId, true, "Gate opened");
        } else if (flow.approvalLatched()) {
            latchedCommandId = pendingCommandId;
            latchedCommandSession = pendingCommandSession;
            latchedCommandPlate = pendingCommandPlate;
            Serial.println("[CMD] approval held until the car arrives");
        } else {
            api.ackCommand(pendingCommandId, false,
                           String("Gate unavailable: ") + GateFlow::stateName(flow.state()));
        }
        pendingCommandId = "";
        pendingCommandSession = "";
        pendingCommandPlate = "";
    }

    // A previously latched approval opened the gate for an arriving car.
    if (!fedApproval && out.event == FlowEvent::Approved && latchedCommandId.length() > 0) {
        activeSessionId = latchedCommandSession;
        if (!latchedCommandPlate.isEmpty()) {
            activePlate = latchedCommandPlate;
        }
        api.ackCommand(latchedCommandId, true, "Gate opened for arriving vehicle");
        latchedCommandId = "";
        latchedCommandSession = "";
        latchedCommandPlate = "";
    }

    if (out.approvalExpired && latchedCommandId.length() > 0) {
        api.ackCommand(latchedCommandId, false, "Approval expired before vehicle arrived");
        latchedCommandId = "";
        latchedCommandSession = "";
        latchedCommandPlate = "";
    }

    if (deniedCommandId.length() > 0) {
        api.ackCommand(deniedCommandId, true, "Denial displayed");
        deniedCommandId = "";
    }
}

void handleFlowEvent(const GateFlowOutputs &out) {
    switch (out.event) {
        case FlowEvent::RequestAuth:
            performScan();
            break;
        case FlowEvent::Denied:
            Serial.printf("[FLOW] denied: %s\n", denialMessage.c_str());
            break;
        case FlowEvent::PaymentDue:
            Serial.printf("[FLOW] payment due %.2f\n", dueAmount);
            break;
        case FlowEvent::CarPassed:
            Serial.println("[FLOW] car passed");
            api.reportGateEvent(carPassedEvent(), activeSessionId, "", "");
            break;
        case FlowEvent::Fault: {
            const String detail(faultDetail());
            Serial.printf("[FLOW] FAILSAFE hold open (%s)\n", detail.c_str());
            api.reportGateEvent("gate_fault", activeSessionId, "", detail);
            break;
        }
        case FlowEvent::FaultCleared:
            Serial.println("[FLOW] passage clear - closing");
            break;
        case FlowEvent::Timeout:
            Serial.println("[FLOW] timeout - back to scan prompt");
            break;
        case FlowEvent::Approved:
        case FlowEvent::PromptCard:
        case FlowEvent::None:
        default:
            break;
    }
}

void renderLcd(const GateFlowOutputs &out) {
    String line1;
    String line2;

    switch (out.state) {
        case FlowState::Closed:
            line1 = "Smart Parking";
            line2 = flow.approvalLatched() ? "Approved - drive in" : "Gate closed";
            break;
        case FlowState::WaitingCard:
            line1 = (kRole == GateRole::Exit) ? "Exit gate" : "Entry gate";
            line2 = flow.approvalLatched() ? "Approved - drive in" : out.message;
            break;
        case FlowState::Authorizing:
            line1 = "Checking card";
            line2 = scannedUid;
            break;
        case FlowState::PaymentPending:
            line1 = "Payment due";
            line2 = dueHasAmount ? ("$" + String(dueAmount, 2) + " - pay now") : "Pay at kiosk";
            break;
        case FlowState::Opening:
        case FlowState::OpenWaitingPass:
            line1 = "Gate open";
            line2 = "Drive slowly";
            break;
        case FlowState::Closing:
            line1 = "Gate closing";
            line2 = "Wait";
            break;
        case FlowState::Denied:
            line1 = "Access denied";
            line2 = denialMessage;
            break;
        case FlowState::FaultHoldOpen:
            line1 = "FAILSAFE open";
            line2 = faultDetail();
            break;
    }

    const bool idleState = (out.state == FlowState::Closed || out.state == FlowState::WaitingCard);
    if (idleState && !rfidReader.online()) {
        line2 = "RFID reader error";
    } else if (idleState && !wifi.connected()) {
        line2 = "WiFi offline";
    }

    gateHardware.showMessage(line1, line2);
}

void renderLeds(const GateFlowOutputs &out, uint32_t now) {
    bool green = false;
    bool red = false;

    switch (out.state) {
        case FlowState::Closed:
            red = true;
            break;
        case FlowState::WaitingCard:
            red = true;
            green = ((now / 400) % 2) == 0;
            break;
        case FlowState::Authorizing:
            green = true;
            break;
        case FlowState::PaymentPending:
            red = true;
            break;
        case FlowState::Opening:
        case FlowState::OpenWaitingPass:
        case FlowState::Closing:
            green = true;
            break;
        case FlowState::Denied:
            red = true;
            break;
        case FlowState::FaultHoldOpen:
            red = ((now / 250) % 2) == 0;
            green = !red;
            break;
    }

    gateHardware.setLeds(green, red);
}

}  // namespace

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.printf("\n=== Smart IoT Parking — %s gate ===\n", roleName());
    Serial.printf("Device %s -> %s\n", PARKING_DEVICE_CODE, PARKING_API_BASE_URL);

    gateHardware.begin();
    presenceSensor.begin();
#if PARKING_PASSAGE_SENSOR_ENABLED
    passageSensor.begin();
    Serial.println("[BOOT] passage safety sensor enabled (fail-safe close)");
#else
    Serial.println("[BOOT] passage safety sensor disabled (close on approach clear)");
#endif

    rfidReader.begin();
    wifi.begin();

    flow.reset(millis());
    gateHardware.showMessage("Smart Parking", String(roleName()) + " gate ready");
}

void loop() {
    const uint32_t now = millis();

    if (now - lastSensorMs >= PARKING_SENSOR_INTERVAL_MS) {
        lastSensorMs = now;
        readSensors();
    }

    wifi.maintain(now);
    if (!rfidReader.online()) {
        rfidReader.maintain(now, PARKING_RFID_RETRY_MS);
    }

    if (rfidReader.poll(scannedUid, sizeof(scannedUid), now)) {
        Serial.printf("[RFID] card detected: %s\n", scannedUid);
        inCardScanned = true;
    }

    if (wifi.connected() && now - lastPollMs >= PARKING_CMD_POLL_INTERVAL_MS) {
        lastPollMs = now;
        PendingCommand command;
        if (api.pollCommand(command) && command.hasCommand) {
            handleCommand(command);
        }
    }

    if (wifi.connected() && now - lastHeartbeatMs >= PARKING_HEARTBEAT_INTERVAL_MS) {
        lastHeartbeatMs = now;
        if (!api.heartbeat()) {
            Serial.println("[API] heartbeat failed");
        }
    }

    GateFlowInputs in;
    in.vehiclePresent = vehiclePresent;
    in.vehicleDetectorHealthy = vehicleDetectorHealthy;
    in.passageBlocked = passageBlocked;
    in.passageHealthy = passageHealthy;
    in.cardScanned = inCardScanned;
    in.authorizationApproved = inAuthApproved;
    in.authorizationDenied = inAuthDenied;
    in.authorizationIgnored = inAuthIgnored;
    in.paymentPendingResponse = inPaymentPending;
    in.gateCommandApproved = inCommandApproved;
    in.gateCommandDenied = inCommandDenied;
    in.nowMs = now;

    // Snapshot the command flag, then clear every one-shot so events fired
    // below (performScan etc.) can safely set the next tick's inputs.
    const bool fedApproval = inCommandApproved;
    inCardScanned = false;
    inAuthApproved = false;
    inAuthDenied = false;
    inAuthIgnored = false;
    inPaymentPending = false;
    inCommandApproved = false;
    inCommandDenied = false;

    const GateFlowOutputs out = flow.update(in);

    resolveCommandOutcome(out, fedApproval);
    handleFlowEvent(out);

    if (out.openGate) {
        gateHardware.openGate();
        Serial.println("[GATE] OPEN");
    }
    if (out.closeGate) {
        gateHardware.closeGate();
        Serial.println("[GATE] CLOSED");
        api.reportGateEvent(gateClosedEvent(), activeSessionId, "", "");
        activeSessionId = "";
        activePlate = "";
        dueHasAmount = false;
        dueAmount = 0.0f;
    }

    renderLcd(out);
    renderLeds(out, now);

    delay(5);
}
