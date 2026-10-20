"""Minimal JSON-command Cyber-Grid bot; customize strategy inside get_action."""


def get_action(state):
    """Receive the team's fog-filtered JSON state and return zero or more commands."""
    return {"commands": []}
