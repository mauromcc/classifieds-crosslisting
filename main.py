import time, threading, traceback

import marketplaces.vinted
import marketplaces.wallapop

from helpers.images import remove_temp_folder
from helpers.abort import listen_for_abort, reset_abort, check_abort
from helpers.parsing import detect_marketplace, check_required, choose_destination, collect_listing, check_existing_in_other_marketplaces, upload_listing



# ---------------------------
# Main loop
# ---------------------------

def main():
    print("=== Cross-Marketplace Tool ===")
    threading.Thread(target=listen_for_abort, daemon=True).start()
    
    while True:
        driver = None
        try:
            if check_abort(): 
                continue  

            # Step 1: Collect listing info
            source_url = input("\n👉 Enter a listing URL to collect: ").strip()
            source = detect_marketplace(source_url)
            if not source:
                print("❌ Could not detect marketplace from URL.")
                continue

            listing = collect_listing(source_url, source)
            if not check_required(listing): # Validate required fields, if missing, goes back to again step
                continue

            if check_abort(): 
                continue

            # Step 1.5: Check if it already exists in other marketplaces
            listing["exists_in"] = {}
            check_existing_in_other_marketplaces(listing)

            if check_abort(): 
                continue

            # Step 2: Choose upload destination (exclude source and marketplaces where it exists already)
            destination = choose_destination(listing)
            if not destination:
                continue

            if check_abort(): 
                continue

            # Step 3: Upload to destination
            driver = upload_listing(listing, destination)

        except Exception as e:
            print("\n❌ An error occurred:", e)
            traceback.print_exc()
        
        finally:
            reset_abort()

            again = input("\nDo you want to submit another listing? (y/n): ").strip().lower()
                
            # Close driver
            try:
                if driver:
                    driver.quit()
            except NameError:
                print("Driver was never created")
                pass
            except Exception:
                print("Driver exists but is already closed or invalid")
                pass

            # Cleanup temp images
            try:
                remove_temp_folder("temp_images")
            except Exception as e:
                print("⚠️ Error while cleaning temp folder:", e)

            if again != "y":
                break       


if __name__ == "__main__":
    main()