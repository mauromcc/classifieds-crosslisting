import os, hashlib, requests, io, shutil, time
try:
    from PIL import Image
except Exception:
    Image = None
try:
    import imagehash
    HAVE_IMAGEHASH = True
except Exception:
    HAVE_IMAGEHASH = False

from constants import SCRIPT_DIR, HEADERS



# ---------------------------
# Image downloading / hashing
# ---------------------------
def download_image(url, folder="temp_images"):
    folder_path = os.path.join(SCRIPT_DIR, folder)
    os.makedirs(folder_path, exist_ok=True)
    url_hash = hashlib.md5(url.encode()).hexdigest()
    ext = url.split(".")[-1].split("?")[0]
    filename = f"{url_hash}.{ext}"
    path = os.path.join(folder_path, filename)
    if not os.path.exists(path):
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        with open(path, "wb") as f:
            f.write(response.content)
    return path

# small in-memory cache to avoid repeated downloads of the same URL
_IMAGE_HASH_CACHE: dict[str, tuple[str | None, str | None]] = {}

def compute_image_hashes(url: str) -> tuple[str | None, str | None]:
    """
    Download image bytes and return (md5_hex, phash_hex_or_none).
    Uses imagehash.phash when available, otherwise falls back to a simple average-hash
    implemented with PIL. Returns (None, None) on failure.
    """
    if not url:
        return None, None

    # quick cache check
    if url in _IMAGE_HASH_CACHE:
        return _IMAGE_HASH_CACHE[url]

    try:
        # strip common tracking/query params as a first attempt (but keep fallback)
        tried_urls = [url]
        if "?" in url:
            tried_urls.insert(0, url.split("?", 1)[0])  # try without query first

        for u in tried_urls:
            try:
                resp = requests.get(u, timeout=10, headers=HEADERS)
                resp.raise_for_status()
                b = resp.content
                md5 = hashlib.md5(b).hexdigest()

                phash_hex = None
                if Image is not None:
                    try:
                        img = Image.open(io.BytesIO(b)).convert("RGB")
                        if HAVE_IMAGEHASH:
                            phash_hex = str(imagehash.phash(img))
                        else:
                            # fallback aHash (64-bit) using PIL only
                            small = img.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
                            pixels = list(small.getdata())
                            avg = sum(pixels) / len(pixels)
                            bits = "".join("1" if p > avg else "0" for p in pixels)
                            phash_hex = hex(int(bits, 2))[2:].rjust(16, "0")
                    except Exception:
                        phash_hex = None

                _IMAGE_HASH_CACHE[url] = (md5, phash_hex)
                return md5, phash_hex
            except Exception:
                # try next candidate (e.g. stripped query)
                continue

    except Exception:
        pass

    _IMAGE_HASH_CACHE[url] = (None, None)
    return None, None

def hamming_distance_hex(h1: str | None, h2: str | None) -> int:
    if not h1 or not h2:
        return 9999
    try:
        i1 = int(h1, 16)
        i2 = int(h2, 16)
        return (i1 ^ i2).bit_count()  # Python 3.8+: .bit_count() is fast
    except Exception:
        return 9999

def remove_temp_folder(folder="temp_images", retries=5, delay=0.25):
    """
    Remove the temp images folder and its contents. On Windows a file can be briefly
    locked, so we retry a few times. Returns True if removed, False otherwise.
    """
    path = os.path.join(SCRIPT_DIR, folder)
    if not os.path.exists(path):
        return True  # already gone

    last_exc = None
    for attempt in range(retries):
        try:
            shutil.rmtree(path)
            # optionally recreate empty folder if you prefer:
            # os.makedirs(path, exist_ok=True)
            print(f"🧹 Cleaned temp folder: {path}")
            return True
        except Exception as e:
            last_exc = e
            time.sleep(delay)
    print(f"⚠️ Could not remove temp folder {path} after {retries} attempts. Error: {last_exc}")
    return False
    


