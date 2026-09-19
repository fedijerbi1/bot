import os
import staypresent

# Health-check endpoint for Render
staypresent.web.json({"status": "running"})

# Launch bot.py as a managed subprocess on Render's PORT
staypresent.run(
    "bot.py",
    port=int(os.getenv("PORT", 10000)),
    restart_on_crash=True,
    max_restarts=10
)