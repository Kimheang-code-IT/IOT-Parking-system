#pragma once

#include <stdint.h>

namespace parking {

// Gate roles share the same state machine; the role only changes the
// wording of prompts and which backend endpoints are used.
enum class GateRole : uint8_t { Entry = 1, Exit = 2 };

enum class FlowState : uint8_t {
    Closed,          // idle, gate down, no car
    WaitingCard,     // car present, prompting for an RFID scan
    Authorizing,     // scan sent to the backend, waiting for the approval command
    PaymentPending,  // exit only: fee due, waiting for paid status + command
    Opening,         // pulse sent to the servo this tick
    OpenWaitingPass, // gate open, waiting for the car to clear the passage
    Closing,         // pulse sent to the servo this tick
    Denied,          // backend refused access (LED feedback window)
    FaultHoldOpen,   // fail-safe: passage blocked/sensor fault -> gate stays open
};

enum class FlowEvent : uint8_t {
    None = 0,
    PromptCard,     // show "scan card"
    RequestAuth,    // send RFID scan to the backend
    Approved,       // approval command received -> gate opens
    Denied,         // access refused
    PaymentDue,     // exit: fee pending, show amount
    CarPassed,      // vehicle finished crossing -> report gate event
    Fault,          // fail-safe raised -> report gate fault
    FaultCleared,   // passage safe again
    Timeout,        // auth/payment/pass window expired
};

struct GateFlowInputs {
    bool vehiclePresent = false;         // approach sensor sees a car
    bool vehicleDetectorHealthy = true;  // approach sensor produced a valid reading
    bool passageBlocked = false;         // passage safety sensor sees an obstruction
    bool passageHealthy = true;          // passage sensor produced a valid reading
    bool cardScanned = false;            // one-shot: an RFID card was read (already de-duplicated)
    bool authorizationApproved = false;  // HTTP scan accepted, approval command queued
    bool authorizationDenied = false;    // HTTP scan refused (unknown/blocked card, etc.)
    bool authorizationIgnored = false;   // HTTP duplicate — quietly rescan
    bool paymentPendingResponse = false; // exit: backend returned fee due
    bool gateCommandApproved = false;    // ENTRY_APPROVED / EXIT_APPROVED polled from the backend
    bool gateCommandDenied = false;      // EXIT_DENIED polled from the backend
    uint32_t nowMs = 0;
};

struct GateFlowOutputs {
    bool openGate = false;          // one-shot pulse: drive the servo open
    bool closeGate = false;         // one-shot pulse: drive the servo closed
    bool approvalExpired = false;   // latched approval lapsed before a car arrived (ack failed)
    FlowEvent event = FlowEvent::None;  // one-shot notification for logging / backend gate events
    FlowState state = FlowState::Closed;
    const char *message = "";       // LCD hint for the current state
};

struct GateFlowConfig {
    uint32_t authTimeoutMs = 15000;          // scan -> approval command
    uint32_t denialHoldMs = 4000;            // how long "access denied" is shown
    uint32_t passTimeoutMs = 20000;          // gate open too long without a pass
    uint32_t minOpenMs = 1500;               // minimum open time before closing
    uint32_t paymentTimeoutMs = 300000;      // exit fee waiting window (0 = forever)
    uint32_t paymentAbsenceGraceMs = 10000;  // exit: car may leave before paying
    uint32_t commandValidityMs = 180000;     // approval held for an arriving car
    bool passageSensorEnabled = true;        // false -> close when approach clears
};

class GateFlow {
public:
    GateFlow(GateRole role, const GateFlowConfig &config);

    void reset(uint32_t nowMs);

    GateFlowOutputs update(const GateFlowInputs &in);

    FlowState state() const { return state_; }

    // True while an approval for a not-yet-arrived car is held.
    bool approvalLatched() const { return latchValid_; }

    const char *message() const;

    static const char *stateName(FlowState state);

private:
    void enter(FlowState next, uint32_t nowMs);
    bool latchUsable(uint32_t nowMs) const;

    GateRole role_;
    GateFlowConfig config_;
    FlowState state_;
    uint32_t stateEnteredMs_;
    uint32_t latchUntilMs_;
    bool latchValid_;
    bool latchExpiredPending_;
    bool sawCarInPassage_;
    bool faultReported_;
    const char *message_;
};

}  // namespace parking
