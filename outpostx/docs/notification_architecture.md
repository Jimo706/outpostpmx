# Notification Architecture – Design Document
## 1. Overview

This document defines the notification architecture used in OutpostX.

The goal of this architecture is to provide a clean, thread-safe, and extensible mechanism for delivering events from background processing (e.g., Send/Receive sessions) to the user interface.

This design was first implemented for:

- “Messages received” notifications (sound)

It is intended to be reused for:

- Printing
- Status updates
- Alerts
- Future automation features

## 2. Design Goals
**Functional Goals**

- Deliver event notifications from background tasks to UI
- Support multiple notification types (sound, print, UI)
- Allow payload-based extensibility

**Non-Functional Goals**
- Strict separation of concerns (engine vs UI)
- Thread-safe communication
- Minimal coupling between layers
- Easy to extend without modifying core session logic

## 3. Architectural Principles

### 3.1 Separation of Concerns

    Layer	                            Responsibility
    ----------------------------------  -------------------------------
    Engine (SendReceiveSession)	        Detect events
    Worker (_SendReceiveWorker)	        Transport events across thread
    Dialog (SendReceiveSessionDialog)   Bridge worker → UI
    UI (MainWindow)	                    Execute user-visible actions

### 3.2 Thread Safety
- Background processing runs in a QThread
- UI updates occur only in the main thread
- Communication is exclusively via Qt signals

### 3.3 Event-Based Design

Notifications are event-driven, not polling-based.

Example:

    Message received → event emitted → UI reacts

## 4. End-to-End Flow
    SendReceiveSession (engine)
        ↓
    _callback(payload)
        ↓
    _SendReceiveWorker.messagesReceived.emit(payload)
        ↓
    SendReceiveSessionDialog.messagesReceived.emit(payload)
        ↓
    MainWindow._on_messages_received_notification(payload)
        ↓
    UI action (sound / print / etc.)

## 5. Core Components

### 5.1 SendReceiveSession (Engine Layer)

**Responsible for:**

- Detecting events (e.g., inbound messages)
- Emitting notification payloads

**Example:**

    self._messages_received({
        "count": count,
        "play_sound": True,
        "sound_path": sound_path,
    })

**Important:**

- Contains no UI code
- Uses injected callback

### 5.2 _SendReceiveWorker (Thread Layer)

**Defines signal:**

    messagesReceived = QtCore.Signal(object)

Bridges engine callback to Qt signal:

    messages_received=self.messagesReceived.emit

### 5.3 SendReceiveSessionDialog (Bridge Layer)

**Re-emits worker signal:**

    self._worker.messagesReceived.connect(self.messagesReceived.emit)

**Purpose:**

- Keeps worker isolated
- Provides stable UI-facing signal interface

### 5.4 MainWindow (UI Layer)

**Handles notifications:**

    def _on_messages_received_notification(self, payload):
        ...

**Executes UI actions:**

- Play sound
- Update status
- Trigger printing

## 6. Notification Payload Design
### 6.1 Structure

**Payload is a dictionary:**

    {
        "count": int,
        "play_sound": bool,
        "sound_path": str,
    }

### 6.2 Design Principles
- Lightweight
- Self-contained
- Extensible

### 6.3 Future Extensions

**Possible additions:**

    {
        "print_received": True,
        "print_copies": 2,
        "show_popup": True,
        "message_ids": [...],
    }

## 7. Audio Notification Implementation
**UI Thread Execution**

Uses:

    QSoundEffect

Design:

- Single reusable instance
- Load-on-change
- Low latency playback

Fallback:

    QApplication.beep()

## 8. Example Flow (Message Received)
    Receive inbound messages
        ↓
    Count new messages
        ↓
    Call _notify_messages_received()
        ↓
    Emit payload via callback
        ↓
    Worker emits Qt signal
        ↓
    Dialog forwards signal
        ↓
    MainWindow receives payload
        ↓
    Play sound

## 9. Error Handling

- Missing callback → no-op
- Invalid payload → ignored safely
- Invalid sound path → fallback beep
- Exceptions contained within UI handler

## 10. Extensibility
- Adding New Notification Types
- Extend payload in engine
- Pass through existing signal pipeline
- Add handling in MainWindow

No changes required in:

- Worker
- Dialog

## 11. Advantages of This Architecture
**Clean Layering**
- Engine independent of UI
- UI independent of protocol logic

**Thread Safety**

No direct UI calls from worker thread

**Reusability**
**Same pipeline supports:**
- Sound
- Printing
- Alerts
- Logging

**Maintainability**
- Changes localized to appropriate layer

## 12. Future Enhancements
- Notification manager abstraction
- User-configurable notification types
- Queueing / batching notifications
- System tray integration
- Visual popups
- Logging integration

## 13. Summary

The notification architecture provides:

- A clean, event-driven pipeline
- Strong separation between engine and UI
- Safe cross-thread communication
- A scalable foundation for future features

This pattern is now a core architectural building block in OutpostX.