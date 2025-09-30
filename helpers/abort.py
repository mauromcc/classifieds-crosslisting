import keyboard

from constants import ABORT_FLAG
from helpers.images import remove_temp_folder



# ---------------------------
# Abort flag / keyboard listener
# ---------------------------
ABORT_FLAG = False  # local flag, not in constants
ABORT_KEY = "esc"

def listen_for_abort():
    """Background thread that sets abort flag when ESC is pressed."""
    keyboard.add_hotkey(ABORT_KEY, lambda: set_abort())
    keyboard.wait() # Keep this thread alive

def set_abort():
    """Set global abort flag."""
    global ABORT_FLAG
    ABORT_FLAG = True
    print("\n⛔ ESC pressed. Aborting current run...")

def reset_abort():
    """Reset abort flag after a run finishes."""
    global ABORT_FLAG
    ABORT_FLAG = False

def check_abort(driver=None) -> bool:
    """Check abort flag and optionally clean up driver."""
    global ABORT_FLAG
    if ABORT_FLAG:
        if driver:
            try:
                driver.quit()
            except Exception:
                print("⚠️ Driver cleanup issue during abort")

        try:
            remove_temp_folder("temp_images")
        except Exception as e:
            print("⚠️ Error cleaning temp folder:", e)

        return True

    return False