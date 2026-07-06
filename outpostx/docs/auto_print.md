# Auto Print – Design Overview

**OutpostX – Message Auto-Printing Feature**

---

## Purpose

Provide immediate, automatic printing of messages during Send/Receive operations to support served-agency workflows where timely hardcopy delivery is required.

This feature mirrors real-world packet operations where printed output may be handed off while additional traffic is still being received.

---

## Key Behavior

### 1. Receive Path (Primary Use Case)

* Each message is printed **immediately after it is stored**
* Printing is **per-message**, not batched
* Long receive sessions do **not delay earlier messages**

```
Receive → Parse → Store (repo) → Build PrintableMessage → Print
```

---

### 2. Send Path

* Messages are printed **immediately after successful send**
* Occurs after `mark_sent()` and before folder move

```
Send → mark_sent → Build PrintableMessage → Print → move_to_sent
```

---

## User Controls (Settings)

Configured via **Send/Receive Settings UI**

| Setting                 | Description                            |
| ----------------------- | -------------------------------------- |
| Print received messages | Enable auto-print on inbound messages  |
| Copies (received)       | Number of copies (1–9)                 |
| Print sent messages     | Enable auto-print on outbound messages |
| Copies (sent)           | Number of copies (1–9)                 |
| Print Receipt messages  | (future use) control receipt printing  |
| Print headers           | Include message headers in output      |

Defaults:

* All printing disabled
* Copies = 1

---

## Architecture

### Components

**1. SendReceiveSession**

* Orchestrates Auto-Print
* Determines *when* printing occurs
* Reads user settings

**2. MessageRepository**

* Source of truth for message data
* Provides message + body via `get(msgidx)`

**3. MessagePrintService**

* Handles rendering and printing
* Converts `PrintableMessage` → HTML → QTextDocument → QPrinter

**4. PrintableMessage**

* Lightweight DTO for printing
* Decouples storage model from print format

---

### Data Flow

```
msgidx
  ↓
MessageRepository.get()
  ↓
_build_printable_message_from_repo()
  ↓
PrintableMessage
  ↓
MessagePrintService.print_message_silent()
  ↓
OS Print Spooler
```

---

## Silent Printing

Auto-Print uses:

```
print_message_silent(...)
```

* No UI dialogs (no QPrintDialog)
* Sends job directly to default/system-selected printer
* Supports copy count (1–9)

---

## OS Behavior (Windows)

* Printing is **queued**, not guaranteed immediate output
* If printer is offline:

  * Job is accepted by OS spooler
  * Printed later when printer becomes available

Logging reflects this:

```
Auto-Print: queued received message for printing msgidx=XXX
```

---

## Design Decisions

### 1. Per-Message Printing

Chosen over batch printing to:

* Reduce latency to served agency
* Avoid blocking on long downloads

---

### 2. Repository-Based Mapping

Printing uses stored data:

```
repo.get(msgidx) → PrintableMessage
```

Benefits:

* Ensures printed output matches DB
* Avoids inconsistencies with transient parsed data
* Simplifies future enhancements

---

### 3. Separation of Concerns

| Component           | Responsibility       |
| ------------------- | -------------------- |
| SendReceiveSession  | When to print        |
| MessageRepository   | Data retrieval       |
| MessagePrintService | Rendering + printing |

---

### 4. OS Spooler Delegation

OutpostX does **not**:

* Track printer state
* Retry failed jobs
* Manage print queues

These are delegated to the operating system.

---

## Error Handling

* Print failures do **not interrupt** Send/Receive
* Exceptions are caught and logged:

```
WARNING: Auto-Print failed for message msgidx=...
```

---

## Future Enhancements

* Printer selection in settings
* Conditional printing (e.g., skip receipts)
* Async/background printing (if needed)
* Print formatting for ICS/forms
* Print queue status feedback (optional)

---

## Status

✔ Feature complete
✔ Tested (receive, send, multi-message, copy counts)
✔ Production-ready for initial release

---

## Summary

Auto-Print provides reliable, immediate message printing integrated into the Send/Receive workflow, with minimal complexity and strong alignment to real-world emergency communications needs.

---
