# SmartCity Traffic Analytics – Pipeline Big Data End-to-End

## 🎯 Objectif du Projet

Pipeline Big Data complet pour analyser le trafic urbain en temps réel :
1. **Génération** de données de trafic réalistes
2. **Ingestion** via Kafka
3. **Stockage** partitionné dans HDFS (Data Lake)
4. **Traitement** avec Spark (KPIs de congestion)
5. **Visualisation** avec Grafana

**État actuel** : ✅ **Étapes 1-4 complètes** (Génération → Kafka → HDFS)

---

## 🛠️ Stack Technique (Docker)

| Service           | Version | Port       | Rôle                      |
| ----------------- | ------- | ---------- | ------------------------- |
| **Kafka**         | 7.5.0   | 9093       | Broker de messages        |
| **Zookeeper**     | 7.5.0   | 2181       | Coordination Kafka        |
| **HDFS Namenode** | 3.2.1   | 9870       | Métadonnées HDFS          |
| **HDFS Datanode** | 3.2.1   | -          | Stockage blocs HDFS       |
| **Spark Master**  | 3.5.1   | 8080, 7077 | Orchestration traitements |
| **Spark Worker**  | 3.5.1   | 8081       | Exécution jobs Spark      |
| **Airflow**       | 2.9.3   | 8085       | Orchestration DAGs        |
| **PostgreSQL**    | 13      | 5432       | Métadonnées Airflow       |
| **Grafana**       | latest  | 3000       | Visualisation             |

---

## 📂 Architecture du Projet

```
SmartCity_Traffic_Pipeline/
├── docker-compose.yml          # Stack complète
├── .env                        # Variables d'environnement
├── scripts/
│   ├── traffic_data_generator.py   # Génération d'événements
│   ├── kafka_producer.py           # Producteur Kafka
│   └── kafka_to_hdfs.py            # Consommateur → HDFS
├── dags/                       # DAGs Airflow (à venir)
├── logs/                       # Logs Airflow
└── README.md
```

---

## 🚀 Démarrage Rapide

### 1️⃣ Prérequis
- Docker Desktop + Docker Compose
- Python 3.8+

### 2️⃣ Lancer la stack Docker
```powershell
docker compose up -d
```

**Attendre ~60s** que tous les services soient **healthy** :
```powershell
docker compose ps
```

### 3️⃣ Créer le répertoire HDFS de base
```powershell
docker exec -it namenode hdfs dfs -mkdir -p /user/hdfs/traffic
docker exec -it namenode hdfs dfs -chown -R hdfs:hdfs /user/hdfs/traffic
```

### 4️⃣ Lancer le producteur (génère des événements)
```powershell
python scripts/kafka_producer.py
```

### 5️⃣ Vérifier que le consumer écrit dans HDFS
```powershell
docker logs -f consumer
```

**Logs attendus** :
```
Consumer Kafka initialisé avec bootstrap.servers=kafka:9093
Écrit 50 messages dans /user/hdfs/traffic/year=2026/month=01/day=11/zone=Centre-Ville/traffic_*.jsonl
```

### 6️⃣ Vérifier les fichiers HDFS
```powershell
# Lister les fichiers
docker exec -it namenode hdfs dfs -ls /user/hdfs/traffic/year=2026/month=01/day=11/zone=Centre-Ville

# Afficher le contenu
docker exec -it namenode hdfs dfs -cat /user/hdfs/traffic/year=2026/month=01/day=11/zone=Centre-Ville/traffic_*.jsonl
```

**Résultat attendu** : lignes JSON avec `sensor_id`, `timestamp`, `zone`, `vehicle_count`, etc.

---

## 📊 Étapes Réalisées

### ✅ Étape 1 – Génération de Données Réalistes
**Fichier** : `scripts/traffic_data_generator.py`

Génère des événements JSON simulant le trafic urbain avec :
- 20 capteurs (IDs 1-20)
- 4 zones : Centre-Ville, Périphérie, Quartier-Résidentiel, Zone-Industrielle
- Patterns temporels : heures de pointe (7h-9h, 17h-20h), normales, nuit
- Anomalies : accidents (5% probabilité) avec baisse de vitesse et hausse d'occupation

**Format JSON** :
```json
{
  "sensor_id": 12,
  "timestamp": "2026-01-11T15:17:32.123456+00:00",
  "zone": "Centre-Ville",
  "road_type": "avenue",
  "vehicle_count": 87,
  "average_speed": 42,
  "occupancy_rate": 58
}
```

---

### ✅ Étape 2 – Ingestion Kafka
**Fichier** : `scripts/kafka_producer.py`

- Producteur Kafka avec `confluent-kafka`
- Topic : `traffic-events`
- `acks='all'` : garantit la livraison
- Logs : `Message envoyé au topic traffic-events : 12 - Centre-Ville`

---

### ✅ Étape 3 – Consommation Kafka
**Fichier** : `kafka_to_hdfs.py`

- Consumer Group : `hdfs-consumer-group`
- Auto-offset : `earliest` (relit depuis le début si nouveau groupe)

---

### ✅ Étape 4 – Stockage HDFS Partitionné
**Fichier** : `scripts/kafka_to_hdfs.py`

**Caractéristiques** :
- **Micro-batching** : 50 messages OU 30 secondes
- **Format** : JSON Lines (`.jsonl`)
- **Partitionnement dynamique** :
  ```
  /user/hdfs/traffic/
    year=2026/
      month=01/
        day=11/
          zone=Centre-Ville/
            traffic_20260111151732.jsonl
          zone=Périphérie/
            traffic_20260111151755.jsonl
  ```
- **Un fichier par zone et par batch** (évite les "petits fichiers")

---

## 🛠️ Problèmes Résolus

| Problème                                                         | Cause                                                                       | Solution                                                         |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| **Permission denied HDFS**                                       | Le répertoire `/data/raw/traffic` appartenait à `root`.                     | Utiliser `/user/hdfs/traffic` (propriétaire : `hdfs`).           |
| **`socket.gaierror` DataNode**                                   | Le consumer Windows ne résolvait pas le hostname du DataNode Docker.        | Exécuter le consumer **dans Docker** (service `consumer`).       |
| **`Connection refused localhost:9093`**                          | Kafka annonçait `localhost:9093` au lieu de `kafka:9093`.                   | Corriger `KAFKA_ADVERTISED_LISTENERS` dans `docker-compose.yml`. |
| **Consumer lit `localhost` malgré `KAFKA_BOOTSTRAP=kafka:9093`** | Le consumer Kafka était créé au niveau module (avant lecture des env vars). | Déplacer la création du consumer **dans `main()`**.              |

---

## 📋 Fichiers Clés Modifiés

### `docker-compose.yml`
- **Kafka** : `KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://kafka:9093`
- **Service `consumer`** : conteneur Python qui exécute `kafka_to_hdfs.py` automatiquement au démarrage

### `scripts/kafka_to_hdfs.py`
- Variables d'environnement lues correctement
- Consumer créé **dans `main()`** (pas au niveau module)
- Gestion d'erreurs robuste pour la création de répertoires HDFS

---

## 🔧 Commandes Utiles

```powershell
# Redémarrer la stack complète
docker compose down
docker compose up -d

# Voir les logs d'un service
docker logs -f consumer
docker logs -f kafka
docker logs -f namenode

# Vérifier l'état des services
docker compose ps

# Supprimer les données HDFS (pour repartir de zéro)
docker exec -it namenode hdfs dfs -rm -r -skipTrash /user/hdfs/traffic
docker exec -it namenode hdfs dfs -mkdir -p /user/hdfs/traffic
docker exec -it namenode hdfs dfs -chown -R hdfs:hdfs /user/hdfs/traffic

# Lister les topics Kafka
docker exec -it kafka kafka-topics --bootstrap-server localhost:9093 --list

# Consommer le topic manuellement
docker exec -it kafka kafka-console-consumer \
    --bootstrap-server localhost:9093 \
    --topic traffic-events \
    --from-beginning \
    --max-messages 5
```

---

## 🎯 Prochaines Étapes

### Étape 5 – Traitement Spark
- Lire les fichiers `.jsonl` depuis HDFS
- Calculer des KPIs :
  - Débit moyen par zone
  - Vitesse moyenne par heure
  - Détection de congestion (occupancy > 80%, speed < 20 km/h)
- Écrire les résultats dans une base SQL ou HDFS

### Étape 6 – Visualisation Grafana
- API Python (Flask/FastAPI) exposant les KPIs
- Dashboard Grafana affichant :
  - Trafic en temps réel par zone
  - Heatmap de congestion
  - Alertes (accidents, embouteillages)

### Étape 7 – Orchestration Airflow
- DAG quotidien : traitement batch Spark
- DAG de monitoring : vérification santé du pipeline

---

## 📌 Règles de Développement

1. **Code** : clair, simple, directement utilisable
2. **Dépendances** : uniquement la stack définie (pas d'ajouts non validés)
3. **Sécurité** : variables d'environnement (pas de secrets en dur)
4. **Exceptions** : gestion propre avec logs explicites
5. **Commentaires** : expliquer le "Pourquoi", pas le "Quoi"

---

## 🎉 Validation Étape 4

**Checklist** :
- [x] Stack Docker fonctionnelle
- [x] Producteur Kafka envoie des événements
- [x] Consumer Docker consomme et écrit dans HDFS
- [x] Répertoires HDFS créés dynamiquement (`year/month/day/zone`)
- [x] Fichiers `.jsonl` présents et lisibles
- [x] Partitionnement optimisé (un fichier par zone et par batch)

**Commande de validation finale** :
```powershell
docker exec -it namenode hdfs dfs -cat /user/hdfs/traffic/year=2026/month=01/day=11/zone=Centre-Ville/traffic_*.jsonl | head -n 5
```

Si vous voyez du JSON valide → **Étape 4 RÉUSSIE** ✅

---

**Projet réalisé par** : Mohamed BOULAA LAM  
**Contact** : [GitHub](https://github.com/MohamedBOULAALAM/SmartCity_Traffic_Pipeline)  
**Date** : Janvier 2026
