import os
import requests

from src.backend import models
import os
import requests
from bs4 import BeautifulSoup
import os
import asyncio
from playwright.sync_api import sync_playwright

def get_image_url_from_macaulay(taxon_code):
    url = f"https://media.ebird.org/catalog?taxonCode={taxon_code}&mediaType=photo"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # browser = p.chromium.launch(headless=False, slow_mo=100)

        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_selector("img.ResultsGallery-image", timeout=15000)

        # Grab all image src attributes
        img_elements = page.query_selector_all("img.ResultsGallery-image")
        image_url = img_elements[0].get_attribute("src") if img_elements[0] else None
        browser.close()
        return image_url

    # Some are lazy-loaded, so 'data-src' or 'src' might be used
    return img_tag.get("data-src") or img_tag.get("src")

def download_image(image_url, filename, folder="bird_images"):
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)

    try:
        response = requests.get(image_url, stream=True)
        if "image" not in response.headers.get("Content-Type", ""):
            print(f"[!] Not an image: {image_url}")
            return

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print(f"[✓] Saved image to {filepath}")
    except Exception as e:
        print(f"[!] Error downloading {filename}: {e}")

def save_images_from_taxon_codes(code):
    print(f"[~] Looking up: {code}")
    image_url = get_image_url_from_macaulay(code)
    if image_url:
        filename = f"{code}.jpg"
        download_image(image_url, filename)
    else:
        print(f"[!] Skipped {code}, no image found.")
# Example list of birds (add more as needed)
if __name__ == "__main__":
    bird_list = models.get_all_birds()
    for bird in bird_list:
        if bird.image_path is None and bird is not None:
            print(bird.genus + " " +bird.species)
            print(bird.ebird_species_code)
            try:
                save_images_from_taxon_codes(bird.ebird_species_code)
                # save_images_from_taxon_codes("nezpig3")

                # models.update_bird_taxa(bird.id, species_code, taxa_info["order"], taxa_info["scientific_family"])
            except:
                "bird did not work"


