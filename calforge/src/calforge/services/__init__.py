"""Application services — the only API the UI and plugins are allowed to use.

Services own transaction boundaries, map ORM models to DTOs and publish
domain events on the bus. They are thread-safe: each call opens its own
short-lived session, so they can be invoked from UI worker threads directly.
"""
