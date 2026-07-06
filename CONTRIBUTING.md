
# Contributing to the OutpostX Suite

Thank you for your interest in contributing to the OutpostX Suite.

The goal of this project is to provide a modern, cross-platform communications suite for Amateur Radio packet operations while preserving the proven operating workflow of the original Outpost Packet Message Manager.

Contributions of all kinds are welcome, including bug reports, testing, documentation improvements, protocol specifications, and software enhancements.

---

# Project Philosophy

The OutpostX Suite is designed around several core principles:

* Cross-platform operation (Windows, Linux, and macOS)
* Maintainable, readable source code
* Long-term architectural stability
* Backward compatibility where practical
* Modular, service-oriented design
* User-focused operation

The project favors simple, well-documented solutions over unnecessarily complex implementations. Code clarity and maintainability are generally preferred over clever or highly optimized code.

---

# Before Contributing

Before beginning work on a significant enhancement, please open a Discussion or Issue describing the proposed change.

Early discussion helps avoid duplicated effort and ensures that proposed changes are consistent with the project's long-term design goals.

---

# Types of Contributions

The following contributions are particularly appreciated:

## Bug Reports

Please include:

* Operating system and version
* OutpostX Suite version
* Steps required to reproduce the problem
* Expected behavior
* Actual behavior
* Error messages or log excerpts, if available

Whenever possible, include screenshots and session log files.

---

## Feature Requests

Feature requests should describe:

* The problem being solved
* The proposed solution
* Alternative approaches considered
* Expected benefits to Amateur Radio operators

---

## Documentation

Documentation improvements are always welcome.

Examples include:

* User guides
* Installation instructions
* Tutorials
* Architecture documentation
* Typographical corrections
* Clarifications

---

## BBS Protocol Specifications

One of the strengths of the OutpostX Suite is its file-driven protocol architecture.

Support for additional BBS implementations can often be added by creating or improving JSON protocol specification files without requiring application code changes.

Contributions of protocol specifications, test systems, and interoperability reports are encouraged.

---

## Software Development

When submitting code:

* Follow the existing project structure.
* Keep classes focused on a single responsibility.
* Prefer reusable services over duplicated logic.
* Preserve cross-platform compatibility.
* Include comments where they improve readability.
* Avoid introducing unnecessary external dependencies.

Whenever practical, new features should integrate with existing services rather than creating parallel implementations.

---

# Coding Guidelines

The project generally follows these conventions:

* Python 3.x
* Qt for Python (PySide6)
* SQLite for persistent application data
* Four-space indentation
* Descriptive variable and method names
* Meaningful comments where appropriate

Consistency with the surrounding code is generally preferred over strict adherence to external style guides.

---

# Testing

Contributors are encouraged to test changes whenever possible.

Where applicable, testing should include:

* Windows
* Linux
* macOS

If a feature affects communications, testing against multiple BBS implementations or transport types is appreciated.

Whenever possible, verify that existing functionality continues to operate correctly after changes are made.

---

# Pull Requests

Before submitting a Pull Request:

* Ensure the project builds successfully.
* Test new functionality.
* Update documentation if needed.
* Keep changes focused on a single topic whenever practical.

Small, well-defined Pull Requests are generally easier to review than large collections of unrelated changes.

---

# Design Authority

The OutpostX Suite is an actively managed project with a long-term architectural vision.

While contributions are welcomed and appreciated, acceptance of proposed changes remains at the discretion of the project maintainer to preserve architectural consistency and long-term maintainability.

---

# License

By submitting code, documentation, protocol specifications, or other project materials, you agree that your contribution may be incorporated into the OutpostX Suite under the terms of the project's LICENSE.md.

---

# Thank You

Every bug report, documentation correction, protocol specification, test report, and code contribution helps improve the OutpostX Suite for the Amateur Radio community.

Thank you for helping make the project better.

