#!/usr/bin/env python3
"""
traffic_data_generator.py

- Génère des événements de trafic réalistes pour 20 capteurs.
- Chaque événement est un dictionnaire JSON contenant :
    sensor_id, timestamp (ISO‑8601), zone, road_type,
    vehicle_count, average_speed (km/h), occupancy_rate (%).
- La logique dépend de l'heure du jour (pic, normal, nuit) et inclut
  une petite probabilité d'accident qui modifie la vitesse et l'occupancy.
- Aucun envoi Kafka ici – uniquement la génération de données.
"""

import os
import random
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration (peut être surchargée via variables d'environnement)
# ---------------------------------------------------------------------------
NUM_SENSORS = int(os.getenv("NUM_SENSORS", "20"))
SLEEP_SECONDS = float(os.getenv("GEN_SLEEP", "1"))

ZONES = [
    "Centre-Ville",
    "Zone-Industrielle",
    "Quartier-Résidentiel",
    "Périphérie",
]

ROAD_TYPES = ["autoroute", "avenue", "rue", "boulevard"]

ACCIDENT_PROB = 0.05  # 5 % de chance d'accident par événement

# ---------------------------------------------------------------------------
# Helper : déterminer le profil de trafic en fonction de l'heure locale
# ---------------------------------------------------------------------------
def traffic_profile(now: datetime) -> dict:
    """Retourne les bornes de génération selon le créneau horaire.
    - Pic (07‑09, 17‑19)   → trafic élevé, vitesse basse, occupancy élevée.
    - Normal (10‑17)       → trafic moyen, vitesse stable.
    - Nuit (20‑05)         → trafic faible, vitesse fluide.
    """
    hour = now.hour
    if (7 <= hour < 9) or (17 <= hour < 19):
        # Heures de pointe
        return {
            "vehicle_min": 150,
            "vehicle_max": 350,
            "speed_min": 15,
            "speed_max": 30,
            "occupancy_min": 70,
            "occupancy_max": 100,
        }
    elif 10 <= hour < 17:
        # Période normale
        return {
            "vehicle_min": 80,
            "vehicle_max": 150,
            "speed_min": 40,
            "speed_max": 60,
            "occupancy_min": 30,
            "occupancy_max": 70,
        }
    else:
        # Nuit (20‑05) – couvre aussi les heures <7
        return {
            "vehicle_min": 10,
            "vehicle_max": 40,
            "speed_min": 70,
            "speed_max": 80,
            "occupancy_min": 5,
            "occupancy_max": 30,
        }

# ---------------------------------------------------------------------------
# Génération d'un événement unique
# ---------------------------------------------------------------------------
def generate_event(sensor_id: int) -> dict:
    now = datetime.now(timezone.utc)
    profile = traffic_profile(now)

    vehicle_count = random.randint(profile["vehicle_min"], profile["vehicle_max"])
    average_speed = random.randint(profile["speed_min"], profile["speed_max"])
    occupancy_rate = random.randint(profile["occupancy_min"], profile["occupancy_max"])

    # Anomalie accident – 5 % de chance
    if random.random() < ACCIDENT_PROB:
        average_speed = max(1, average_speed // 4)  # vitesse fortement réduite
        occupancy_rate = 100
        # On peut ajouter un flag d'accident si besoin futur
        accident = True
    else:
        accident = False

    event = {
        "sensor_id": sensor_id,
        "timestamp": now.isoformat(),
        "zone": random.choice(ZONES),
        "road_type": random.choice(ROAD_TYPES),
        "vehicle_count": vehicle_count,
        "average_speed": average_speed,
        "occupancy_rate": occupancy_rate,
    }

    if accident:
        event["event"] = "accident"
    return event

# ---------------------------------------------------------------------------
# Boucle principale – génération continue
# ---------------------------------------------------------------------------
def run_generator(limit: int | None = None):
    """Génère indéfiniment (ou jusqu'à *limit*) des événements.
    Chaque seconde, un événement par capteur est produit.
    """
    count = 0
    while limit is None or count < limit:
        batch = [generate_event(sensor_id=i + 1) for i in range(NUM_SENSORS)]
        for ev in batch:
            print(ev)  # sortie console – peut être redirigée vers un fichier ou Kafka
        count += 1
        time.sleep(SLEEP_SECONDS)

# ---------------------------------------------------------------------------
# Validation rapide – afficher les 5 premiers messages
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Affiche uniquement les 5 premiers événements puis s’arrête
    run_generator(limit=5)
