"""Default timing rules for Task Service escalation / extensions.

Tune these in one place — do not scatter magic numbers through the engine.
"""

# Standard (non-urgent) task reminders
STANDARD_MIDPOINT_FRACTION = 0.5  # reminder at 50% of created_at → due_date window
STANDARD_FINAL_WARNING_SECONDS = 4 * 60 * 60  # 4 hours before due

# Urgent task acknowledgement / check-in / reassignment
URGENT_CHECKIN_INTERVAL_SECONDS = 60 * 60  # every 60 minutes
URGENT_ACK_WINDOW_SECONDS = 60 * 60  # first reassignment if unacked after 60 min
URGENT_REASSIGN_ACK_WINDOW_SECONDS = 60 * 60  # second failure window after reassignment

# Extension rules
EXTENSION_CAP_SECONDS = 24 * 60 * 60  # 24-hour total auto-extension cap (normal only)

# Background scheduler
ESCALATION_JOB_INTERVAL_SECONDS = 5 * 60  # run checks every 5 minutes
