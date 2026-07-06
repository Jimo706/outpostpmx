# Send/Receive Automation – Design Document
## 1. Overview

This document describes the design and implementation of Send/Receive (S/R) Automation in OutpostX.

S/R Automation enables the system to:

- Run Send/Receive sessions manually (operator initiated)
- Run Send/Receive sessions automatically at configured time intervals
- Provide operator feedback via countdown display and audio notification

This feature is designed to be robust, thread-safe, and extensible for future notification and automation enhancements.

## 2. Goals
**Functional Goals**

- Support Manual and Interval-based Send/Receive
- Display countdown to next session (HH:MM)
- Prevent overlapping sessions
- Automatically restart scheduling after session completion
- Notify operator when messages are received

**Non-Functional Goals**

- Maintain UI responsiveness (non-modal dialog)
- Ensure thread-safe interaction between session engine and UI
- Keep session engine independent of UI implementation
- Provide clean extensibility for future features (printing, alerts)

## 3. Architecture Overview

    MainWindow (UI Thread)
        ├── Countdown Timer (QTimer, 1 second)
        ├── Status Bar (countdown + status)
        ├── Send/Receive launcher
        │
        └── SendReceiveSessionDialog (non-modal)
                └── _SendReceiveWorker (QThread)
                        └── SendReceiveSession (engine)

## 4. Core Components
### 4.1 MainWindow

**Responsibilities:**

- Own automation state
- Manage countdown timer
- Launch Send/Receive sessions
- Handle UI updates and notifications

 **Key fields:**

    self._in_session
    self._countdown_timer
    self._countdown_seconds_total
    self._countdown_seconds_left

**Key signals:**

    sessionCountdownElapsed

### 4.2 SendReceiveSessionDialog

**Responsibilities:**

- Non-modal UI for session execution
- Own worker thread lifecycle
- Bridge worker signals to UI

**Thread pattern:**

    worker.finished → thread.quit
    worker.finished → worker.deleteLater
    thread.finished → dialog.close
    thread.finished → thread.deleteLater

### 4.3 _SendReceiveWorker (QThread Worker)

**Responsibilities:**

- Execute SendReceiveSession in background thread
- Emit log, transcript, and event signals

Key signal:

    messagesReceived(object payload)

### 4.4 SendReceiveSession (Engine)

**Responsibilities:**

- Execute full Send/Receive workflow:
- connect
- login
- send outbound
- receive inbound
- logout
- Detect newly received messages
- Emit notification events (no UI logic)

**Key method:**

    _notify_messages_received(...)

## 5. Automation Modes
### 5.1 Manual Mode

- No timers active
- Sessions only start via user action

### 5.2 Interval Mode

**Configured via:**

    mode == "every_n_minutes"
    interval_minutes ∈ [1, 999]

**Behavior:**

    Initialize countdown
       ↓
    Countdown ticks every second
       ↓
    Countdown reaches zero
       ↓
    Emit sessionCountdownElapsed
       ↓
    Start Send/Receive session
       ↓
    Session completes
       ↓
    Restart countdown

## 6. Countdown Timer Design

A single QTimer is used:

    self._countdown_timer.start(1000)

**Responsibilities:**

- Decrement seconds remaining
- Update status bar display
- Emit trigger when reaching zero

**Key method:**

    def _on_countdown_tick(self):
        decrement counter
        update label
        if zero → emit sessionCountdownElapsed

## 7. Session Lifecycle

**Manual**

    User clicks Send/Receive
    → _start_send_receive_session(manual=True)
    → run session
    → finish
    → restore UI

**Interval**

    Countdown reaches zero
    → _on_auto_send_receive_timer()
    → _start_send_receive_session(manual=False)
    → run session
    → finish
    → restart countdown

## 8. Threading Model
**Principles**

- Session engine runs in worker thread
- UI updates occur only in main thread
- Communication via Qt signals

**Event Flow**

    SendReceiveSession
        ↓ (callback)
    Worker (signal emit)
        ↓
    SendReceiveSessionDialog
        ↓
    MainWindow (UI thread)

## 9. Message Receipt Detection

During inbound processing:

    received_new_count += 1

After completion:

    if received_new_count:
        _notify_messages_received(...)

Uses nonlocal for closure scope inside nested functions.

## 10. Notification System

**Design Goal**

Decouple engine from UI

**Payload Example**
    {
        "count": 2,
        "play_sound": True,
        "sound_path": "C:/.../packet1.wav"
    }

**Flow**

    Engine → Worker Signal → Dialog → MainWindow → UI Action

## 11. Audio Playback

Implemented in UI thread using:

    QSoundEffect

**Design:**

- Initialize once
- Reuse instance
- Avoid reload unless file changes

****Fallback:**

    QApplication.beep()

## 12. Settings Integration

Settings stored via QSettings.

****Key fields:**

    SendReceive/playSoundOnReceive
    SendReceive/soundFilePath
    SendReceive/mode
    SendReceive/interval_minutes

## 13. Boolean Parsing

QSettings may return strings.

****Problem:**

    bool("false") == True

**Solution:**

    _as_bool(...)

**Normalizes:**

    "true", "1", "yes" → True
    "false", "0", "no" → False

## 14. Error Handling

**Key protections:**

- _in_session prevents overlap
- Countdown stops during session
- worker thread clean shutdown
- Safe defaults for invalid settings

## 15. Known Limitations

- Slot-time scheduling not yet implemented
- Sound playback limited to .wav
- No visual notification (future)
- No printing integration (future)

## 16. Future Enhancements

- Print received/sent messages
- Desktop/tray notifications
- Configurable sound volume
- Multiple notification types
- Slot-based scheduling
- Session history logging

## 17. Summary

The Send/Receive Automation system provides:

- Reliable scheduling
- Clear operator feedback
- Thread-safe execution
- Extensible notification architecture

This design establishes a reusable pattern for future automation and event-driven features in OutpostX.