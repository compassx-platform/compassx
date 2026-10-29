"""Build Studio services split by responsibility.

Sandbox command execution is the only place that knows which runtime
is attached. Workspace files depend on that port, not on a concrete driver.
"""
