# OutpostX — Message Creation & Identity Rules
## Overview

Message creation in OutpostX is intentionally simple for the operator, but internally follows strict rules to ensure:

- Correct station identity
- Consistent BBS routing
- Predictable Send/Receive behavior
- Compatibility with legacy Outpost workflows

This document defines how outbound messages are initialized, especially the From (callsign) field.

## 1. Default “From” Call Selection

When a new message is created, the From field is automatically populated using the active configuration.

Source of Truth

The logic is centralized in:

    SystemConfigService.get_default_from_call()

This ensures consistent behavior across:

- MessageFormWindow NEW mode
- Reply / Forward / Resend drafts
- Future automation features

### Selection Rules
    Condition	                Resulting From Call
    --------------------------  -------------------------
    No active Station	        (blank)
    Station active only	        Station legal call
    Station + Tactical active	Tactical call (preferred)

### Example
    Station	    Tactical    Result
    -------     ---------   -------
    KN6PE	    (none)	    KN6PE
    KN6PE	    CUPEOC	    CUPEOC
    (none)	    CUPEOC	    (blank)
    (none)	    (none)	    (blank)

Tactical calls never stand alone — they are only valid when a Station is active.

## 2. Why Tactical Call Overrides Legal Call

This mirrors real-world emergency communications:

- Legal call = FCC identity (who you are)
- Tactical call = Operational role (what position you are operating)

Example:

    Operator: KN6PE
    Assignment: Cupertino EOC

    Message FROM: CUPEOC

This allows:

- Role-based communication
- Operator rotation without changing message identity
- Cleaner message logs during incidents

## 3. Where This Is Applied

The default From call is applied in:

**Message Form Initialization**

    MessageFormWindow → loads defaults via MessageService

**Message Service Layer**

    SqliteMessageService.defaults()

**Adapter Layer**

    EditorAppSettings.get_default_from_call()

**Final Source**

    SystemConfigService.get_default_from_call()

## 4. Operator Override

The operator may manually edit the From field in the editor.

However:

- Send/Receive enforces safety rules:
    - Outbound messages must match the active station identity
- This prevents:
    - Accidental spoofing
    - Misrouted messages
    - Cross-station contamination

(See Send/Receive rules for details.)

## 5. Relationship to Send/Receive Eligibility

Message sending is not based solely on the From field.

Eligibility checks include:

- Message is in Outbox
- State = QUEUED
- From call matches active station
- BBS matches active BBS

These checks are enforced in:

- SendReceiveSession._send_outbound()

## 6. Design Principles

### 1. Centralized Logic

All identity decisions come from:

    SystemConfigService

This avoids:

- Duplicate logic
- UI inconsistencies
- Drift between components

### 2. Operator-Friendly Defaults
- Correct behavior without thinking
- Minimal required user input

### 3. Emergency-Comms Alignment
- Tactical calls preferred when present
- Legal call always available as fallback

### 4. Safety First
- Prevent sending under the wrong identity
- Ensure consistency across sessions

## 7. Future Enhancements

Potential improvements:

- UI indicator:

    From: CUPEOC (via KN6PE)
    
- Lock From field to active identity (optional setting)
- Multi-operator/shared station workflows
- Audit logging of identity used during send

## Summary

OutpostX message creation ensures:

- Correct identity selection (Station vs Tactical)
- Consistent behavior across UI and backend
- Safe and predictable message handling

The key rule:

    Tactical call is used when present; otherwise, the Station legal call is used.