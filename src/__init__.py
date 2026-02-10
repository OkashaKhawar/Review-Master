# Review Master - WhatsApp Review Collection System
# ===================================================
# A production-quality MVP automation system using Layered Architecture:
#
# ARCHITECTURE LAYERS:
# - Presentation:   CLI entry point (user interaction)
# - Application:    Use cases and orchestration (no business rules)
# - Domain:         Pure business logic (no external dependencies)
# - Infrastructure: External services (WhatsApp, LLM, Excel)
#
# This design allows easy replacement of infrastructure components
# (e.g., swap Excel for a database, or OpenRouter for another LLM).
