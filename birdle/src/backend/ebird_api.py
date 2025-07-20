import os
import models
import requests
import csv
import io

EBIRD_API_TOKEN = os.getenv("EBIRD_API_KEY")

def get_taxonomy_info(species_code: str, version="2021"):
    print(species_code)
    url = f"https://api.ebird.org/v2/ref/taxonomy/ebird?species={species_code}&version={version}"
    headers = {
        "X-eBirdApiToken": EBIRD_API_TOKEN
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        f = io.StringIO(response.text)  # CSV comes as raw text
        reader = csv.DictReader(f)      # Parse it as CSV
        results = list(reader)

        if results:
            bird = results[0]
            return {
                "order": bird.get("ORDER"),
                "scientific_family": bird.get("FAMILY_SCI_NAME")
            }
    else:
        print(f"Failed for {species_code}: {response.status_code}")
        return None
    



def get_all_taxa():
    url = f"https://api.ebird.org/v2/ref/taxonomy/ebird?fmt=json&version=2021"
    headers = {
        "X-eBirdApiToken": EBIRD_API_TOKEN,
        "Accept-Language": "en"
    }

    species_map = {}  # key: (genus, species) → value: speciesCode


    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        results = response.json()
        if results:
            for item in results:
                name_parts = item["sciName"].split()
                if len(name_parts) < 2:
                    continue  # skip malformed names

                genus = name_parts[0]
                species = name_parts[1]  # just the species epithet, not subspecies

                species_map[(genus.lower(), species.lower())] = item["speciesCode"]
    else:
        return None
    
    return species_map
    
species_map = get_all_taxa()

def get_species_code(genus: str, species: str, species_map: dict) -> str | None:
    return species_map.get((genus.lower(), species.lower()))



bird_list = models.get_all_birds()

print(len(bird_list))

for bird in bird_list:
    if bird.ebird_species_code is None and bird is not None:
        print(bird.common_name)
        try:
            species_code =  get_species_code(bird.genus, bird.species, species_map)
            # taxa_info = get_taxonomy_info(species_code)
            # print(taxa_info)
            models.update_bird_species_code(bird.id, species_code)
        except:
            "bird did not work"

# print(species_map)