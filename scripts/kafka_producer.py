#!/usr/bin/env python3
"""
kafka_producer.py

- Pont entre le générateur de trafic (traffic_data_generator) et Kafka.
- Utilise confluent‑kafka (client performant) avec acks='all'.
- Sérialise les événements en JSON avant l'envoi.
- Envoie un message par seconde sur le topic `traffic-events`.
- Logs simples et gestion d’erreurs de connexion.
"""

import os
import json
import time
import logging
from datetime import timezone

# ---------------------------------------------------------------------------
# Configuration – surcharge possible via variables d'environnement
# ---------------------------------------------------------------------------
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9093")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "traffic-events")
SLEEP_SECONDS = float(os.getenv("PRODUCER_SLEEP", "1"))

# ---------------------------------------------------------------------------
# Logging basique (console) – format lisible pour le dev
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import du générateur – on ré‑utilise la fonction generate_event
# ---------------------------------------------------------------------------
# Le fichier traffic_data_generator.py se trouve dans le même répertoire.
# On l’ajoute au path afin que l’import fonctionne même si le script est
# exécuté depuis un autre répertoire.
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
sys.path.append(str(CURRENT_DIR))

try:
    from traffic_data_generator import generate_event, NUM_SENSORS
except Exception as e:
    logger.error("Impossible d'importer le générateur : %s", e)
    raise

# ---------------------------------------------------------------------------
# Initialise le producteur Confluent‑Kafka
# ---------------------------------------------------------------------------
try:
    from confluent_kafka import Producer  # type: ignore
except ImportError as e:
    logger.error("confluent_kafka n'est pas installé. Exécutez: pip install confluent-kafka")
    raise

def delivery_report(err, msg):
    """Callback appelé par le Producer après la tentative d'envoi.
    On loggue uniquement les erreurs, les succès sont déjà affichés.
    """
    if err is not None:
        logger.error("Échec de livraison du message %s: %s", msg.key(), err)
    # sinon, rien – le log principal indique déjà l'envoi.

producer_conf = {
    "bootstrap.servers": KAFKA_BOOTSTRAP,
    "acks": "all",
    # Le sérialiseur JSON est appliqué manuellement avant l'appel à produce.
}

producer = Producer(producer_conf)

def send_event(event: dict):
    """Envoie un événement JSON sur le topic configuré.
    Le callback `delivery_report` gère les erreurs éventuelles.
    """
    try:
        # Confluent‑Kafka attend des bytes – on encode le JSON UTF‑8.
        producer.produce(
            topic=KAFKA_TOPIC,
            value=json.dumps(event).encode("utf-8"),
            callback=delivery_report,
        )
        producer.poll(0)  # déclenche le callback si disponible
        logger.info(
            "Message envoyé au topic %s : %s - %s",
            KAFKA_TOPIC,
            event.get("sensor_id"),
            event.get("zone"),
        )
    except Exception as exc:
        logger.error("Erreur lors de l'envoi du message : %s", exc)

def main():
    """Boucle principale – génère et envoie un lot d'événements chaque seconde.
    Chaque itération crée un événement par capteur (NUM_SENSORS) et les envoie.
    """
    try:
        while True:
            for sensor_id in range(1, NUM_SENSORS + 1):
                event = generate_event(sensor_id)
                send_event(event)
            # Attente avant le prochain lot
            time.sleep(SLEEP_SECONDS)
    except KeyboardInterrupt:
        logger.info("Arrêt demandé par l'utilisateur – fermeture du producer.")
    finally:
        # Flush les messages en attente avant de quitter.
        producer.flush()
        logger.info("Producer flushé et terminé.")

if __name__ == "__main__":
    main()
