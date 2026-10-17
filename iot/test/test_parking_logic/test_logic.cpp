// ---------------------------------------------------------------------------
// Firmware unit tests for the pure logic in lib/parking_core.
//
// Run on the PC:
//   cd iot
//   pio test -e native
//
// Requires a host C++ compiler on PATH (see iot/test/README).
// No ESP32 / RFID hardware needed — GateFlow, ScanGate and UID helpers take
// plain inputs, so every safety rule can be exercised deterministically.
// ---------------------------------------------------------------------------

#include <string.h>

#include <gate_flow.h>
#include <rfid_uid.h>
#include <scan_gate.h>
#include <unity.h>

using namespace parking;

void setUp() {}
void tearDown() {}

// ---------------------------------------------------------------- helpers

static GateFlowConfig testConfig() {
    GateFlowConfig cfg;
    cfg.authTimeoutMs = 15000;
    cfg.denialHoldMs = 4000;
    cfg.passTimeoutMs = 20000;
    cfg.minOpenMs = 1500;
    cfg.paymentTimeoutMs = 300000;
    cfg.paymentAbsenceGraceMs = 10000;
    cfg.commandValidityMs = 180000;
    cfg.passageSensorEnabled = true;
    return cfg;
}

static GateFlowInputs inputs(uint32_t nowMs) {
    GateFlowInputs in;
    in.nowMs = nowMs;
    return in;
}

// Drives the flow from Closed through scan to the open state.
static void driveToOpen(GateFlow &flow, uint32_t &now) {
    GateFlowInputs in = inputs(now += 100);
    in.vehiclePresent = true;
    flow.update(in);

    in = inputs(now += 100);
    in.vehiclePresent = true;
    in.cardScanned = true;
    flow.update(in);

    in = inputs(now += 100);
    in.vehiclePresent = true;
    in.gateCommandApproved = true;
    const GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_TRUE(out.openGate);

    in = inputs(now += 100);
    in.vehiclePresent = true;
    flow.update(in);  // Opening -> OpenWaitingPass
    TEST_ASSERT_TRUE(flow.state() == FlowState::OpenWaitingPass);
}

// ================================================================ rfid_uid

static void test_uid_bytes_to_hex() {
    const uint8_t bytes[4] = {0x04, 0xA1, 0xB2, 0xC3};
    char out[16];
    TEST_ASSERT_EQUAL_UINT(8, uidBytesToHex(bytes, 4, out, sizeof(out)));
    TEST_ASSERT_EQUAL_STRING("04A1B2C3", out);

    const uint8_t small[1] = {0x0A};
    char out2[8];
    TEST_ASSERT_EQUAL_UINT(2, uidBytesToHex(small, 1, out2, sizeof(out2)));
    TEST_ASSERT_EQUAL_STRING("0A", out2);
}

static void test_uid_bytes_to_hex_rejects_short_buffer() {
    const uint8_t bytes[4] = {1, 2, 3, 4};
    char out[4];
    TEST_ASSERT_EQUAL_UINT(0, uidBytesToHex(bytes, 4, out, sizeof(out)));
}

static void test_normalize_uid_strips_separators() {
    char out[16];
    TEST_ASSERT_EQUAL_UINT(8, normalizeUid("04:a1:b2:c3", out, sizeof(out)));
    TEST_ASSERT_EQUAL_STRING("04A1B2C3", out);
    TEST_ASSERT_EQUAL_UINT(8, normalizeUid("04 a1-b2 c3", out, sizeof(out)));
    TEST_ASSERT_EQUAL_STRING("04A1B2C3", out);
}

static void test_normalize_uid_rejects_invalid() {
    char out[16];
    TEST_ASSERT_EQUAL_UINT(0, normalizeUid("04A1B2CX", out, sizeof(out)));  // bad hex char
    TEST_ASSERT_EQUAL_UINT(0, normalizeUid("04A1B2C", out, sizeof(out)));   // odd length
    TEST_ASSERT_EQUAL_UINT(0, normalizeUid("04A1", out, sizeof(out)));      // too short
    TEST_ASSERT_EQUAL_UINT(0, normalizeUid("", out, sizeof(out)));
}

static void test_is_valid_uid() {
    TEST_ASSERT_TRUE(isValidUid("04A1B2C3"));
    TEST_ASSERT_TRUE(isValidUid("04A1B2C3D4E5F6"));  // 7-byte UID
    TEST_ASSERT_FALSE(isValidUid("04A1B2C"));
    TEST_ASSERT_FALSE(isValidUid("04A1B2CX"));
    TEST_ASSERT_FALSE(isValidUid(""));
}

// ================================================================ ScanGate

static void test_scan_gate_first_presentation_accepted() {
    ScanGate gate(8000);
    TEST_ASSERT_TRUE(gate.update("04A1B2C3", 1000));
}

static void test_scan_gate_suppresses_same_card_while_held() {
    ScanGate gate(8000);
    TEST_ASSERT_TRUE(gate.update("04A1B2C3", 1000));
    TEST_ASSERT_FALSE(gate.update("04A1B2C3", 1100));
    TEST_ASSERT_FALSE(gate.update("04A1B2C3", 2000));
}

static void test_scan_gate_allows_rescan_after_cooldown() {
    ScanGate gate(8000);
    TEST_ASSERT_TRUE(gate.update("04A1B2C3", 1000));
    TEST_ASSERT_FALSE(gate.update("04A1B2C3", 5000));
    TEST_ASSERT_TRUE(gate.update("04A1B2C3", 9001));
}

static void test_scan_gate_rearmed_after_removal() {
    ScanGate gate(8000);
    TEST_ASSERT_TRUE(gate.update("04A1B2C3", 1000));
    TEST_ASSERT_FALSE(gate.update(nullptr, 1200));
    TEST_ASSERT_TRUE(gate.update("04A1B2C3", 1300));
}

static void test_scan_gate_accepts_other_card_immediately() {
    ScanGate gate(8000);
    TEST_ASSERT_TRUE(gate.update("04A1B2C3", 1000));
    TEST_ASSERT_TRUE(gate.update("11223344", 1050));
}

static void test_scan_gate_no_card_never_accepts() {
    ScanGate gate(8000);
    TEST_ASSERT_FALSE(gate.update(nullptr, 1000));
    TEST_ASSERT_FALSE(gate.update("", 1100));
}

// ================================================================ GateFlow — entry

static void test_entry_happy_path() {
    GateFlow flow(GateRole::Entry, testConfig());
    uint32_t now = 1000;

    // Car arrives -> scan prompt, gate stays closed.
    GateFlowInputs in = inputs(now += 100);
    in.vehiclePresent = true;
    GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_TRUE(flow.state() == FlowState::WaitingCard);
    TEST_ASSERT_TRUE(out.event == FlowEvent::PromptCard);
    TEST_ASSERT_FALSE(out.openGate);

    // Card scanned -> authorizing (HTTP call happens outside the FSM).
    in = inputs(now += 100);
    in.vehiclePresent = true;
    in.cardScanned = true;
    out = flow.update(in);
    TEST_ASSERT_TRUE(flow.state() == FlowState::Authorizing);
    TEST_ASSERT_TRUE(out.event == FlowEvent::RequestAuth);

    // Backend authorization response arrives, approval command polled.
    in = inputs(now += 100);
    in.vehiclePresent = true;
    in.authorizationApproved = true;
    out = flow.update(in);
    TEST_ASSERT_TRUE(flow.state() == FlowState::Authorizing);  // waits for the command

    in = inputs(now += 100);
    in.vehiclePresent = true;
    in.gateCommandApproved = true;
    out = flow.update(in);
    TEST_ASSERT_TRUE(out.openGate);
    TEST_ASSERT_TRUE(out.event == FlowEvent::Approved);
    TEST_ASSERT_TRUE(flow.state() == FlowState::Opening);

    // Servo pulse consumed -> waiting for the car to cross the passage.
    in = inputs(now += 100);
    in.vehiclePresent = true;
    flow.update(in);
    TEST_ASSERT_TRUE(flow.state() == FlowState::OpenWaitingPass);

    // Car crosses the passage safety sensor and leaves.
    in = inputs(now += 2000);
    in.vehiclePresent = false;
    in.passageBlocked = true;
    out = flow.update(in);
    TEST_ASSERT_TRUE(flow.state() == FlowState::OpenWaitingPass);
    TEST_ASSERT_FALSE(out.closeGate);

    in = inputs(now += 1000);
    in.vehiclePresent = false;
    in.passageBlocked = false;
    out = flow.update(in);
    TEST_ASSERT_TRUE(out.closeGate);
    TEST_ASSERT_TRUE(out.event == FlowEvent::CarPassed);
    TEST_ASSERT_TRUE(flow.state() == FlowState::Closing);

    in = inputs(now += 100);
    flow.update(in);
    TEST_ASSERT_TRUE(flow.state() == FlowState::Closed);
}

static void test_entry_ultrasonic_alone_never_opens() {
    GateFlow flow(GateRole::Entry, testConfig());
    uint32_t now = 1000;
    for (int i = 0; i < 50; ++i) {
        GateFlowInputs in = inputs(now += 500);
        in.vehiclePresent = true;
        const GateFlowOutputs out = flow.update(in);
        TEST_ASSERT_FALSE(out.openGate);
    }
    TEST_ASSERT_TRUE(flow.state() == FlowState::WaitingCard);
}

static void test_entry_authorization_timeout_returns_to_prompt() {
    GateFlow flow(GateRole::Entry, testConfig());
    uint32_t now = 1000;

    GateFlowInputs in = inputs(now += 100);
    in.vehiclePresent = true;
    in.cardScanned = true;
    flow.update(in);
    TEST_ASSERT_TRUE(flow.state() == FlowState::Authorizing);

    in = inputs(now += testConfig().authTimeoutMs + 1);
    in.vehiclePresent = true;
    const GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_TRUE(out.event == FlowEvent::Timeout);
    TEST_ASSERT_TRUE(flow.state() == FlowState::WaitingCard);
    TEST_ASSERT_FALSE(out.openGate);
}

static void test_entry_denied_then_retry() {
    GateFlow flow(GateRole::Entry, testConfig());
    uint32_t now = 1000;

    GateFlowInputs in = inputs(now += 100);
    in.vehiclePresent = true;
    in.cardScanned = true;
    flow.update(in);

    in = inputs(now += 100);
    in.vehiclePresent = true;
    in.authorizationDenied = true;
    GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_TRUE(out.event == FlowEvent::Denied);
    TEST_ASSERT_TRUE(flow.state() == FlowState::Denied);

    // Car drives away during the denial window -> back to idle.
    in = inputs(now += testConfig().denialHoldMs + 1);
    in.vehiclePresent = false;
    flow.update(in);
    TEST_ASSERT_TRUE(flow.state() == FlowState::Closed);
}

static void test_entry_vehicle_leaves_while_waiting() {
    GateFlow flow(GateRole::Entry, testConfig());
    uint32_t now = 1000;

    GateFlowInputs in = inputs(now += 100);
    in.vehiclePresent = true;
    flow.update(in);
    TEST_ASSERT_TRUE(flow.state() == FlowState::WaitingCard);

    in = inputs(now += 100);
    in.vehiclePresent = false;
    flow.update(in);
    TEST_ASSERT_TRUE(flow.state() == FlowState::Closed);
}

static void test_entry_scan_before_vehicle_still_authorizes() {
    GateFlow flow(GateRole::Entry, testConfig());
    uint32_t now = 1000;

    GateFlowInputs in = inputs(now += 100);
    in.cardScanned = true;  // card tapped before the car triggered the sensor
    GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_TRUE(out.event == FlowEvent::RequestAuth);
    TEST_ASSERT_TRUE(flow.state() == FlowState::Authorizing);
}

// ================================================================ GateFlow — fail-safe

static void test_gate_holds_open_while_passage_blocked() {
    GateFlow flow(GateRole::Entry, testConfig());
    uint32_t now = 1000;
    driveToOpen(flow, now);

    // Obstruction under the gate: never close while blocked.
    GateFlowInputs in = inputs(now += 100);
    in.passageBlocked = true;
    GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_FALSE(out.closeGate);
    TEST_ASSERT_TRUE(flow.state() == FlowState::OpenWaitingPass);

    // A long blockage trips the pass timeout -> fail-safe hold open + fault.
    in = inputs(now += 60000);
    in.passageBlocked = true;
    out = flow.update(in);
    TEST_ASSERT_FALSE(out.closeGate);
    TEST_ASSERT_TRUE(flow.state() == FlowState::FaultHoldOpen);
    TEST_ASSERT_TRUE(out.event == FlowEvent::Fault);

    // Obstruction cleared -> safe to close again.
    in = inputs(now += 1000);
    in.passageBlocked = false;
    out = flow.update(in);
    TEST_ASSERT_TRUE(out.closeGate);
}

static void test_passage_sensor_fault_holds_open_until_healthy() {
    GateFlow flow(GateRole::Entry, testConfig());
    uint32_t now = 1000;
    driveToOpen(flow, now);

    GateFlowInputs in = inputs(now += 100);
    in.passageHealthy = false;
    GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_TRUE(out.event == FlowEvent::Fault);
    TEST_ASSERT_TRUE(flow.state() == FlowState::FaultHoldOpen);
    TEST_ASSERT_FALSE(out.closeGate);

    // Still faulty much later: stays open (fail-safe).
    in = inputs(now += 600000);
    in.passageHealthy = false;
    out = flow.update(in);
    TEST_ASSERT_FALSE(out.closeGate);
    TEST_ASSERT_TRUE(flow.state() == FlowState::FaultHoldOpen);

    // Sensor healthy + clear -> closes and reports recovery.
    in = inputs(now += 100);
    in.passageHealthy = true;
    in.passageBlocked = false;
    out = flow.update(in);
    TEST_ASSERT_TRUE(out.closeGate);
    TEST_ASSERT_TRUE(out.event == FlowEvent::FaultCleared);
}

static void test_pass_timeout_raises_fault_hold_open() {
    GateFlow flow(GateRole::Entry, testConfig());
    uint32_t now = 1000;
    driveToOpen(flow, now);

    GateFlowInputs in = inputs(now += testConfig().passTimeoutMs + 1);
    in.vehiclePresent = true;  // car still sitting there, never crossed
    const GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_TRUE(out.event == FlowEvent::Fault);
    TEST_ASSERT_TRUE(flow.state() == FlowState::FaultHoldOpen);
    TEST_ASSERT_FALSE(out.closeGate);
}

static void test_unhealthy_approach_detector_holds_open() {
    GateFlowConfig cfg = testConfig();
    cfg.passageSensorEnabled = false;  // closure relies on the approach sensor
    GateFlow flow(GateRole::Entry, cfg);
    uint32_t now = 1000;
    driveToOpen(flow, now);

    GateFlowInputs in = inputs(now += 2000);
    in.vehiclePresent = false;
    in.vehicleDetectorHealthy = false;
    const GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_TRUE(out.event == FlowEvent::Fault);
    TEST_ASSERT_TRUE(flow.state() == FlowState::FaultHoldOpen);
}

static void test_passage_disabled_closes_when_approach_clears() {
    GateFlowConfig cfg = testConfig();
    cfg.passageSensorEnabled = false;
    GateFlow flow(GateRole::Entry, cfg);
    uint32_t now = 1000;
    driveToOpen(flow, now);

    GateFlowInputs in = inputs(now += 2000);
    in.vehiclePresent = false;
    const GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_TRUE(out.closeGate);
    TEST_ASSERT_TRUE(out.event == FlowEvent::CarPassed);
}

// ================================================================ GateFlow — approval latch

static void test_approval_waits_for_arriving_car() {
    GateFlow flow(GateRole::Exit, testConfig());
    uint32_t now = 1000;

    // Payment completes while no car is at the gate: approval is latched.
    GateFlowInputs in = inputs(now += 100);
    in.gateCommandApproved = true;
    GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_FALSE(out.openGate);
    TEST_ASSERT_TRUE(flow.approvalLatched());

    // Car arrives -> opens without another scan.
    in = inputs(now += 5000);
    in.vehiclePresent = true;
    out = flow.update(in);
    TEST_ASSERT_TRUE(out.openGate);
    TEST_ASSERT_TRUE(out.event == FlowEvent::Approved);
    TEST_ASSERT_FALSE(flow.approvalLatched());
}

static void test_latched_approval_expires() {
    GateFlow flow(GateRole::Exit, testConfig());
    uint32_t now = 1000;

    GateFlowInputs in = inputs(now += 100);
    in.gateCommandApproved = true;
    flow.update(in);
    TEST_ASSERT_TRUE(flow.approvalLatched());

    in = inputs(now += testConfig().commandValidityMs + 1);
    GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_TRUE(out.approvalExpired);
    TEST_ASSERT_FALSE(flow.approvalLatched());
    TEST_ASSERT_FALSE(out.openGate);
}

// ================================================================ GateFlow — exit payment

static void test_exit_payment_pending_flow() {
    GateFlow flow(GateRole::Exit, testConfig());
    uint32_t now = 1000;

    GateFlowInputs in = inputs(now += 100);
    in.vehiclePresent = true;
    flow.update(in);

    in = inputs(now += 100);
    in.vehiclePresent = true;
    in.cardScanned = true;
    flow.update(in);
    TEST_ASSERT_TRUE(flow.state() == FlowState::Authorizing);

    in = inputs(now += 100);
    in.vehiclePresent = true;
    in.paymentPendingResponse = true;
    GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_TRUE(out.event == FlowEvent::PaymentDue);
    TEST_ASSERT_TRUE(flow.state() == FlowState::PaymentPending);

    // Payment completes -> backend queues EXIT_APPROVED -> gate opens.
    in = inputs(now += 30000);
    in.vehiclePresent = true;
    in.gateCommandApproved = true;
    out = flow.update(in);
    TEST_ASSERT_TRUE(out.openGate);
    TEST_ASSERT_TRUE(out.event == FlowEvent::Approved);
}

static void test_exit_payment_absence_grace() {
    GateFlow flow(GateRole::Exit, testConfig());
    uint32_t now = 1000;

    GateFlowInputs in = inputs(now += 100);
    in.vehiclePresent = true;
    in.cardScanned = true;
    flow.update(in);

    in = inputs(now += 100);
    in.vehiclePresent = true;
    in.paymentPendingResponse = true;
    flow.update(in);
    TEST_ASSERT_TRUE(flow.state() == FlowState::PaymentPending);

    // Car leaves for longer than the grace window -> idle again.
    in = inputs(now += testConfig().paymentAbsenceGraceMs + 1);
    in.vehiclePresent = false;
    flow.update(in);
    TEST_ASSERT_TRUE(flow.state() == FlowState::Closed);
}

static void test_exit_denied_command() {
    GateFlow flow(GateRole::Exit, testConfig());
    uint32_t now = 1000;

    GateFlowInputs in = inputs(now += 100);
    in.vehiclePresent = true;
    in.cardScanned = true;
    flow.update(in);

    in = inputs(now += 100);
    in.vehiclePresent = true;
    in.gateCommandDenied = true;
    const GateFlowOutputs out = flow.update(in);
    TEST_ASSERT_TRUE(out.event == FlowEvent::Denied);
    TEST_ASSERT_TRUE(flow.state() == FlowState::Denied);
}

// ================================================================ main

int main(int, char **) {
    UNITY_BEGIN();

    RUN_TEST(test_uid_bytes_to_hex);
    RUN_TEST(test_uid_bytes_to_hex_rejects_short_buffer);
    RUN_TEST(test_normalize_uid_strips_separators);
    RUN_TEST(test_normalize_uid_rejects_invalid);
    RUN_TEST(test_is_valid_uid);

    RUN_TEST(test_scan_gate_first_presentation_accepted);
    RUN_TEST(test_scan_gate_suppresses_same_card_while_held);
    RUN_TEST(test_scan_gate_allows_rescan_after_cooldown);
    RUN_TEST(test_scan_gate_rearmed_after_removal);
    RUN_TEST(test_scan_gate_accepts_other_card_immediately);
    RUN_TEST(test_scan_gate_no_card_never_accepts);

    RUN_TEST(test_entry_happy_path);
    RUN_TEST(test_entry_ultrasonic_alone_never_opens);
    RUN_TEST(test_entry_authorization_timeout_returns_to_prompt);
    RUN_TEST(test_entry_denied_then_retry);
    RUN_TEST(test_entry_vehicle_leaves_while_waiting);
    RUN_TEST(test_entry_scan_before_vehicle_still_authorizes);

    RUN_TEST(test_gate_holds_open_while_passage_blocked);
    RUN_TEST(test_passage_sensor_fault_holds_open_until_healthy);
    RUN_TEST(test_pass_timeout_raises_fault_hold_open);
    RUN_TEST(test_unhealthy_approach_detector_holds_open);
    RUN_TEST(test_passage_disabled_closes_when_approach_clears);

    RUN_TEST(test_approval_waits_for_arriving_car);
    RUN_TEST(test_latched_approval_expires);

    RUN_TEST(test_exit_payment_pending_flow);
    RUN_TEST(test_exit_payment_absence_grace);
    RUN_TEST(test_exit_denied_command);

    return UNITY_END();
}
