# OutpostX Identity Model

## Overview

OutpostX separates operator identity into two related but different concepts:

- **Station identity** — the licensed/legal identity of the operator or station.
- **Tactical identity** — the operational role or location being used during an event.

This separation supports both normal amateur radio operation and emergency communications workflows where operators may rotate through assigned positions such as an EOC, shelter, command post, or field team.

---

## 1. Station Identity

A Station profile represents the legal/operator identity.

Primary field:

    station_profiles.legal_call_sign

Examples:

    KN6PE
    K6ABC
    W1XSC

If no active Station is selected, OutpostX should not perform operations that require station identity, including:

- Creating a new message with a valid From value
- Setting TNC MYCALL
- Registering with AGWPE
- Sending tactical station identification before disconnect

## 2. Tactical Identity

A Tactical profile represents the operational role or assignment.

Primary fields:
    tactical_profiles.tactical_call_sign
    tactical_profiles.tactical_location

Examples:

    CUPEOC
    CITYEOC
    SHELTER1
    FIELD3

The tactical call is used when an operator is working under an assigned role rather than using their personal call as the visible message identity.

The tactical location is used for legal station identification before disconnecting from the BBS.

Example:

    # this is KN6PE, Cupertino EOC

## 3. Active Configuration

OutpostX uses SystemConfigService as the source of truth for active identity selection.

Relevant methods:

    get_active_station()
    get_active_tactical()
    get_default_from_call()
    get_signature_context()

The active Station and active Tactical profiles are selected in Preferences / Setup.

The active Tactical profile does not replace the Station profile; instead it supplements it.

## 4. Identity Resolution Rules
**Legal Call Requirement**

The legal call sign is always required for identity-sensitive operations.

    if legal_call_sign is empty:
        error

**Tactical Override Rule**

When a tactical call is **active**, it becomes the visible operating identity.

    if tactical_call_sign is present:
        use tactical_call_sign
    else:
        use legal_call_sign

This rule applies to:

- New message From field
- TNC MYCALL
- AGWPE registration callsign
- BBS login identity where appropriate
- legal station identification when tactical call is used

## 5. Message Creation Identity

When a new outbound message is created, the default From field is resolved as follows:

    legal_call_sign required

    if tactical_call_sign exists:
        From = tactical_call_sign
    else:
        From = legal_call_sign

Example:

    Station legal call: KN6PE
    Tactical call:      CUPEOC

    New message From:   CUPEOC

This lets messages represent the operating position rather than the individual operator.

## 6. Send/Receive Identity

During Send/Receive, OutpostX uses the same identity model.

### TNC MYCALL

Before connecting to a BBS through a TNC, OutpostX sets MYCALL using the effective operating call.

    MYCALL CUPEOC

or, if no tactical call is active:

    MYCALL KN6PE

### AGWPE Registration

For AGWPE sessions, the same effective callsign is used when registering with AGWPE.

    register CUPEOC

or 

    register KN6PE

## 7. Station Identification Before Bye

When a tactical call is active, OutpostX sends a station identification line before leaving the BBS.

This happens before the BBS **B** / bye command.

Format:

    # this is <legal_call_sign>, <tactical_location>

Example:

    # this is KN6PE, Cupertino EOC
    B

This provides the legal station identity while preserving the tactical callsign during operational message handling.

If no tactical call is active, this additional station ID line is not required.

## 8. Why Legal and Tactical Identities Are Separate

This design supports emergency communications practice:

    Concept	            Meaning	                            Example
    ------------------  ----------------------------------- -------------
    Legal call	        Licensed station/operator identity	KN6PE
    Tactical call       Operational role or assignment      CUPEOC
    Tactical location	Human-readable location or function Cupertino EOC

The tactical call provides operational continuity.

For example, if several operators rotate through the Cupertino EOC position, messages can continue to come from:

    CUPEOC

while the legal station ID can still identify the licensed operator currently responsible:

    # this is KN6PE, Cupertino EOC

## 9. Design Principles

One Source of Truth

Identity rules should be centralized in:

    SystemConfigService

UI components should not independently decide whether to use the legal call or tactical call.

**Tactical Call Does Not Stand Alone**

A tactical call is only valid when a Station profile is active.

The Station profile provides the legal identity anchor.

**Operator-Friendly Defaults**

The operator should not need to manually enter the correct From call for every message.

OutpostX should prefill the safest, most operationally useful value.

**Safety Over Convenience**

If legal identity is missing, OutpostX should fail clearly rather than silently sending under an ambiguous identity.

## 10. Recommended Flow

    Identity Resolution
    -------------------

    [Active Station Profile]
            |
            | legal_call_sign required
            v
    [SystemConfigService]
            |
            | check active Tactical Profile
            v
    +-----------------------------+
    | Tactical call configured?   |
    +-----------------------------+
            | yes                         | no
            v                             v
    [Use tactical_call_sign]       [Use legal_call_sign]
            |                             |
            +-------------+---------------+
                        v
            [Effective Operating Call]

## 11. Related Message From Flow

    Step | Component                | Action
    -----|--------------------------|-------------------------------------------
    1    | MessageFormWindow        | Calls defaults()
    2    | SqliteMessageService     | Requests default_from_call
    3    | EditorAppSettings        | Delegates request
    4    | SystemConfigService      | Applies Tactical vs Legal rule
    5    | EditorAppSettings        | Returns resolved callsign
    6    | SqliteMessageService     | Passes value back
    7    | MessageFormWindow        | Populates From field


    Message "From" Resolution Flow
    --------------------------------

    [MessageFormWindow (QMainWindow host)]
                |
                | defaults()
                v
    [SqliteMessageService]
                |
                | get_default_from_call()
                v
    [EditorAppSettings (Adapter)]
                |
                | delegate
                v
    [SystemConfigService]
                |
                | resolve:
                |   - tactical_call if present
                |   - else legal_call
                v
    [EditorAppSettings]
                |
                v
    [SqliteMessageService]
                |
                v
    [MessageFormWindow]
                |
                v
    [MessageEditorWidget.edFrom]



## 12. Future Enhancements

Possible future improvements:

- Display both identities in the message editor:

        From: CUPEOC
        Operator: KN6PE

- Show status bar identity as:

        KN6PE as CUPEOC

- Add audit fields to outbound messages:

    station_profile_id
    tactical_profile_id
    operator_legal_call
    effective_from_call

- Add a setting to lock the From field to the effective identity.
- Add clearer warnings when a queued message no longer matches the active identity.
- Add tactical-call-aware message filtering and inbox views.

## Summary

OutpostX uses a two-layer identity model:

    Legal identity   = who is legally responsible
    Tactical identity = what role/location is operating

The core rule is:

    Use tactical_call_sign when active;
    otherwise use legal_call_sign.

The legal call remains required as the identity anchor for safe, accountable operation.