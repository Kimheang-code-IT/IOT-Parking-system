#include "gate_flow.h"

namespace parking {

namespace {

uint32_t elapsed(uint32_t nowMs, uint32_t sinceMs) {
    return static_cast<uint32_t>(nowMs - sinceMs);
}

// Wraparound-safe "now >= deadline" comparison.
bool timeReached(uint32_t nowMs, uint32_t deadlineMs) {
    return static_cast<int32_t>(nowMs - deadlineMs) >= 0;
}

}  // namespace

GateFlow::GateFlow(GateRole role, const GateFlowConfig &config)
    : role_(role),
      config_(config),
      state_(FlowState::Closed),
      stateEnteredMs_(0),
      latchUntilMs_(0),
      latchValid_(false),
      latchExpiredPending_(false),
      sawCarInPassage_(false),
      faultReported_(false),
      message_("") {}

void GateFlow::reset(uint32_t nowMs) {
    state_ = FlowState::Closed;
    stateEnteredMs_ = nowMs;
    latchValid_ = false;
    latchExpiredPending_ = false;
    sawCarInPassage_ = false;
    faultReported_ = false;
}

void GateFlow::enter(FlowState next, uint32_t nowMs) {
    state_ = next;
    stateEnteredMs_ = nowMs;
    if (next == FlowState::OpenWaitingPass) {
        sawCarInPassage_ = false;
    }
    if (next == FlowState::FaultHoldOpen) {
        faultReported_ = true;
    }
}

bool GateFlow::latchUsable(uint32_t nowMs) const {
    return latchValid_ && !timeReached(nowMs, latchUntilMs_);
}

GateFlowOutputs GateFlow::update(const GateFlowInputs &in) {
    GateFlowOutputs out;

    // A held approval lapses if the car never arrives in time.
    if (latchValid_ && timeReached(in.nowMs, latchUntilMs_)) {
        latchValid_ = false;
        out.approvalExpired = true;
    }

    switch (state_) {
        case FlowState::Closed:
            if (!in.vehiclePresent) {
                if (in.gateCommandApproved) {
                    latchValid_ = true;
                    latchUntilMs_ = in.nowMs + config_.commandValidityMs;
                } else if (in.cardScanned) {
                    // Card first, car second (or a broken approach sensor):
                    // the backend still decides, the command opens the gate.
                    enter(FlowState::Authorizing, in.nowMs);
                    out.event = FlowEvent::RequestAuth;
                }
                break;
            }
            if (latchUsable(in.nowMs) || in.gateCommandApproved) {
                latchValid_ = false;
                enter(FlowState::Opening, in.nowMs);
                out.openGate = true;
                out.event = FlowEvent::Approved;
            } else if (in.cardScanned) {
                enter(FlowState::Authorizing, in.nowMs);
                out.event = FlowEvent::RequestAuth;
            } else {
                enter(FlowState::WaitingCard, in.nowMs);
                out.event = FlowEvent::PromptCard;
            }
            break;

        case FlowState::WaitingCard:
            if (!in.vehiclePresent && in.vehicleDetectorHealthy) {
                enter(FlowState::Closed, in.nowMs);
            } else if (latchUsable(in.nowMs) || in.gateCommandApproved) {
                if (in.vehiclePresent || !in.vehicleDetectorHealthy) {
                    latchValid_ = false;
                    enter(FlowState::Opening, in.nowMs);
                    out.openGate = true;
                    out.event = FlowEvent::Approved;
                } else {
                    latchValid_ = true;
                    latchUntilMs_ = in.nowMs + config_.commandValidityMs;
                }
            } else if (in.cardScanned) {
                enter(FlowState::Authorizing, in.nowMs);
                out.event = FlowEvent::RequestAuth;
            }
            break;

        case FlowState::Authorizing:
            if (in.gateCommandApproved) {
                enter(FlowState::Opening, in.nowMs);
                out.openGate = true;
                out.event = FlowEvent::Approved;
            } else if (in.paymentPendingResponse) {
                enter(FlowState::PaymentPending, in.nowMs);
                out.event = FlowEvent::PaymentDue;
            } else if (in.gateCommandDenied || in.authorizationDenied) {
                enter(FlowState::Denied, in.nowMs);
                out.event = FlowEvent::Denied;
            } else if (in.authorizationIgnored) {
                enter(in.vehiclePresent ? FlowState::WaitingCard : FlowState::Closed, in.nowMs);
            } else if (!in.vehiclePresent) {
                enter(FlowState::Closed, in.nowMs);
            } else if (elapsed(in.nowMs, stateEnteredMs_) >= config_.authTimeoutMs) {
                enter(in.vehiclePresent ? FlowState::WaitingCard : FlowState::Closed, in.nowMs);
                out.event = FlowEvent::Timeout;
            }
            break;

        case FlowState::PaymentPending:
            if (in.gateCommandApproved) {
                enter(FlowState::Opening, in.nowMs);
                out.openGate = true;
                out.event = FlowEvent::Approved;
            } else if (in.gateCommandDenied || in.authorizationDenied) {
                enter(FlowState::Denied, in.nowMs);
                out.event = FlowEvent::Denied;
            } else if (in.cardScanned) {
                enter(FlowState::Authorizing, in.nowMs);
                out.event = FlowEvent::RequestAuth;
            } else if (!in.vehiclePresent &&
                       elapsed(in.nowMs, stateEnteredMs_) >= config_.paymentAbsenceGraceMs) {
                enter(FlowState::Closed, in.nowMs);
            } else if (config_.paymentTimeoutMs > 0 &&
                       elapsed(in.nowMs, stateEnteredMs_) >= config_.paymentTimeoutMs) {
                enter(in.vehiclePresent ? FlowState::WaitingCard : FlowState::Closed, in.nowMs);
                out.event = FlowEvent::Timeout;
            }
            break;

        case FlowState::Opening:
            // The open pulse was emitted when Opening was entered.
            enter(FlowState::OpenWaitingPass, in.nowMs);
            break;

        case FlowState::OpenWaitingPass: {
            if (config_.passageSensorEnabled && !in.passageHealthy) {
                enter(FlowState::FaultHoldOpen, in.nowMs);
                out.event = FlowEvent::Fault;
                break;
            }
            if (in.passageBlocked) {
                sawCarInPassage_ = true;
            }
            bool passed = false;
            if (config_.passageSensorEnabled) {
                passed = sawCarInPassage_ && !in.passageBlocked;
            } else if (!in.vehicleDetectorHealthy) {
                // Cannot prove the lane is clear -> fail-safe hold open.
                enter(FlowState::FaultHoldOpen, in.nowMs);
                out.event = FlowEvent::Fault;
                break;
            } else {
                passed = !in.vehiclePresent;
            }
            if (passed && elapsed(in.nowMs, stateEnteredMs_) >= config_.minOpenMs) {
                enter(FlowState::Closing, in.nowMs);
                out.closeGate = true;
                out.event = FlowEvent::CarPassed;
                break;
            }
            if (elapsed(in.nowMs, stateEnteredMs_) >= config_.passTimeoutMs) {
                enter(FlowState::FaultHoldOpen, in.nowMs);
                out.event = FlowEvent::Fault;
            }
            break;
        }

        case FlowState::Closing:
            enter(FlowState::Closed, in.nowMs);
            break;

        case FlowState::Denied:
            if (elapsed(in.nowMs, stateEnteredMs_) >= config_.denialHoldMs) {
                const bool stay = in.vehiclePresent || !in.vehicleDetectorHealthy;
                enter(stay ? FlowState::WaitingCard : FlowState::Closed, in.nowMs);
            }
            break;

        case FlowState::FaultHoldOpen:
            // Fail-safe: only leave this state once the passage is provably safe.
            if (config_.passageSensorEnabled) {
                if (in.passageHealthy && !in.passageBlocked) {
                    enter(FlowState::Closing, in.nowMs);
                    out.closeGate = true;
                    out.event = FlowEvent::FaultCleared;
                }
            } else if (!in.vehiclePresent && in.vehicleDetectorHealthy) {
                enter(FlowState::Closing, in.nowMs);
                out.closeGate = true;
                out.event = FlowEvent::FaultCleared;
            }
            break;
    }

    out.state = state_;
    out.message = message();
    return out;
}

const char *GateFlow::message() const {
    switch (state_) {
        case FlowState::Closed:
            return latchValid_ ? "Approved - drive in" : "Gate closed";
        case FlowState::WaitingCard:
            if (latchValid_) {
                return "Approved - drive in";
            }
            return role_ == GateRole::Exit ? "Scan card to exit" : "Scan card to enter";
        case FlowState::Authorizing:
            return "Checking card...";
        case FlowState::PaymentPending:
            return "Pay at kiosk";
        case FlowState::Opening:
        case FlowState::OpenWaitingPass:
            return "Gate open";
        case FlowState::Closing:
            return "Closing...";
        case FlowState::Denied:
            return "Access denied";
        case FlowState::FaultHoldOpen:
            return "FAILSAFE: passage";
    }
    return "";
}

const char *GateFlow::stateName(FlowState state) {
    switch (state) {
        case FlowState::Closed: return "Closed";
        case FlowState::WaitingCard: return "WaitingCard";
        case FlowState::Authorizing: return "Authorizing";
        case FlowState::PaymentPending: return "PaymentPending";
        case FlowState::Opening: return "Opening";
        case FlowState::OpenWaitingPass: return "OpenWaitingPass";
        case FlowState::Closing: return "Closing";
        case FlowState::Denied: return "Denied";
        case FlowState::FaultHoldOpen: return "FaultHoldOpen";
    }
    return "?";
}

}  // namespace parking
