"""Default timing rules for Task Service escalation / extensions.

Tune these in one place — do not scatter magic numbers through the engine.

P2 standard path (locked): assign → one mid progress ask at 50% of
created_at → due window → expiry. Final warning is deferred (P2.1).
"""

# Standard (non-urgent) task reminders — mid-only + expiry (P2)
STANDARD_MIDPOINT_FRACTION = 0.5  # progress ask at 50% of created_at → due_date window

# Deferred (P2.1): optional final warning before due. Kept as a knob so we can
# re-enable without hunting magic numbers; check_standard_task does not use it.
STANDARD_FINAL_WARNING_SECONDS = 4 * 60 * 60  # 4 hours before due (unused in P2)
STANDARD_FINAL_WARNING_ENABLED = False

# Urgent task acknowledgement / check-in / reassignment
URGENT_CHECKIN_INTERVAL_SECONDS = 60 * 60  # every 60 minutes
URGENT_ACK_WINDOW_SECONDS = 60 * 60  # first reassignment if unacked after 60 min
URGENT_REASSIGN_ACK_WINDOW_SECONDS = 60 * 60  # second failure window after reassignment

# Extension rules
EXTENSION_CAP_SECONDS = 24 * 60 * 60  # 24-hour total auto-extension cap (normal only)

# Background scheduler
ESCALATION_JOB_INTERVAL_SECONDS = 5 * 60  # run checks every 5 minutes
