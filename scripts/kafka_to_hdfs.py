#!/usr/bin/env python3
"""
kafka_to_hdfs.py

- Consomme les messages du topic `traffic-events` via confluent‑kafka.
- Regroupe les messages (max 50 ou 30 s) puis les écrit en JSON‑Lines sur HDFS.
- Partitionnement dynamique : /data/raw/traffic/year=YYYY/month=MM/day=DD/zone={zone}/
- Utilise la bibliothèque `hdfs` (WebHDFS) sur http://localhost:9870.
- Gestion basique des erreurs et logs console.
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from collections import defaultdict

# ---------------------------------------------------------------------------
# Configuration (peut être surchargée via variables d'environnement)
# ---------------------------------------------------------------------------
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9093")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "traffic-events")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "hdfs-consumer-group")
HDFS_URL = os.getenv("HDFS_URL", "http://localhost:9870")
HDFS_USER = os.getenv("HDFS_USER", "hdfs")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))          # max messages per file
BATCH_TIMEOUT = int(os.getenv("BATCH_TIMEOUT", "30"))    # seconds max before write
BASE_HDFS_PATH = os.getenv("BASE_HDFS_PATH", "/data/raw/traffic")

# ---------------------------------------------------------------------------
# Logging simple
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Initialise le client HDFS (WebHDFS)
# ---------------------------------------------------------------------------
try:
    from hdfs import InsecureClient  # type: ignore
except ImportError as e:
    logger.error("hdfs client not installed. Run: pip install hdfs")
    raise

hdfs_client = InsecureClient(HDFS_URL, user=HDFS_USER)

# ---------------------------------------------------------------------------
# Initialise le consumer Kafka (confluent_kafka)
# ---------------------------------------------------------------------------
try:
    from confluent_kafka import Consumer  # type: ignore
except ImportError as e:
    logger.error("confluent_kafka not installed. Run: pip install confluent-kafka")
    raise

consumer_conf = {
    "bootstrap.servers": KAFKA_BOOTSTRAP,
    "group.id": KAFKA_GROUP_ID,
    "auto.offset.reset": "earliest",
    "enable.auto.commit": True,
}
consumer = Consumer(consumer_conf)
consumer.subscribe([KAFKA_TOPIC])

def build_hdfs_path(event: dict) -> str:
    """Construit le chemin HDFS dynamique basé sur la date et la zone.
    Exemple : /data/raw/traffic/year=2026/month=01/day=08/zone=Centre-Ville/
    """
    ts = datetime.fromisoformat(event["timestamp"]).astimezone(timezone.utc)
    year = ts.strftime("%Y")
    month = ts.strftime("%m")
    day = ts.strftime("%d")
    zone = event["zone"].replace(" ", "_")  # éviter espaces dans le chemin
    return f"{BASE_HDFS_PATH}/year={year}/month={month}/day={day}/zone={zone}/"

def write_batch_to_hdfs(batch: list[dict]):
    """Écrit un lot de messages au format JSON‑Lines dans le répertoire HDFS.
    Un fichier unique est créé par zone (les messages du même lot partagent la même zone).
    """
    if not batch:
        return
    # Regrouper par zone pour créer un fichier par zone (évite trop de petits fichiers)
    zones_groups = defaultdict(list)
    for ev in batch:
        zones_groups[ev["zone"]].append(ev)

    for zone, events in zones_groups.items():
        # Chemin du répertoire (sans le nom de fichier)
        hdfs_dir = build_hdfs_path(events[0])
        # Crée le répertoire s'il n'existe pas – gestion d’erreurs robuste
        try:
            if not hdfs_client.status(hdfs_dir, strict=False):
                hdfs_client.makedirs(hdfs_dir)
                logger.info("Créé répertoire HDFS %s", hdfs_dir)
        except Exception as e:
            logger.warning("Impossible de vérifier/créer le répertoire %s : %s", hdfs_dir, e)
            # On continue avec le prochain groupe de zone pour éviter l’arrêt complet
            continue
        # Nom du fichier : timestamp du premier événement + .jsonl
        first_ts = datetime.fromisoformat(events[0]["timestamp"]).strftime("%Y%m%d%H%M%S")
        filename = f"traffic_{first_ts}.jsonl"
        hdfs_path = os.path.join(hdfs_dir, filename)
        # Sérialiser en JSON‑Lines
        data = "\n".join(json.dumps(ev) for ev in events) + "\n"
        # Écriture atomique via hdfs_client.write (mode='append' n'est pas nécessaire ici)
        with hdfs_client.write(hdfs_path, encoding="utf-8", overwrite=True) as writer:
            writer.write(data)
        logger.info("Écrit %d messages dans %s", len(events), hdfs_path)

def main():
    """Boucle principale : consomme, batch, écrit sur HDFS.
    Le batch se déclenche quand il atteint BATCH_SIZE ou que BATCH_TIMEOUT s'écoule.
    """
    batch = []
    batch_start = time.time()
    try:
        while True:
            msg = consumer.poll(1.0)  # timeout 1 s
            if msg is None:
                # Aucun message, vérifier le timeout
                if batch and (time.time() - batch_start) >= BATCH_TIMEOUT:
                    write_batch_to_hdfs(batch)
                    batch.clear()
                    batch_start = time.time()
                continue
            if msg.error():
                logger.error("Kafka error: %s", msg.error())
                continue
            # Décoder le payload JSON
            try:
                event = json.loads(msg.value().decode("utf-8"))
            except Exception as e:
                logger.error("Impossible de décoder le message : %s", e)
                continue
            batch.append(event)
            # Si le batch est plein, on écrit immédiatement
            if len(batch) >= BATCH_SIZE:
                write_batch_to_hdfs(batch)
                batch.clear()
                batch_start = time.time()
    except KeyboardInterrupt:
        logger.info("Arrêt demandé – écriture du batch restant avant fermeture.")
        if batch:
            write_batch_to_hdfs(batch)
    finally:
        consumer.close()
        logger.info("Consumer Kafka fermé.")

if __name__ == "__main__":
    main()
