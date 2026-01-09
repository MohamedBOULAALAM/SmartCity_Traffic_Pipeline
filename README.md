# SmartCity Traffic Pipeline – Guide de démarrage et de test

## 🎯 Objectif
Ce dépôt implémente un pipeline **Big Data** complet pour analyser le trafic urbain :
1. **Génération de données** réalistes (`traffic_data_generator.py`).
2. **Ingestion** dans Kafka (`kafka_producer.py`).
3. **Consommation** et stockage dans HDFS (`kafka_to_hdfs.py`).
4. (À venir) traitement Spark, visualisation Grafana, etc.

Le présent guide vous montre comment **démarrer** la stack Docker, **générer** des événements, **les consommer** et **vérifier** qu’ils sont bien écrits dans HDFS.

---

## 📦 Prérequis
| Outil | Version recommandée |
|-------|--------------------|
| Docker & Docker‑Compose | >= 24.0 |
| Python | 3.8+ (utilisez le virtualenv fourni) |
| `docker` doit être accessible depuis le terminal PowerShell (ou CMD) |

> **Note** : le projet utilise un environnement virtuel (`.venv`).

---

## 🗂️ Structure du projet
```
SmartCity_Traffic_Pipeline/
├─ docker-compose.yml          # stack complète (Kafka, Zookeeper, HDFS, Spark, Airflow, Grafana)
├─ .env                       # variables d’environnement pour Docker
├─ scripts/
│   ├─ traffic_data_generator.py   # génération d’événements JSON
│   ├─ kafka_producer.py           # producteur Kafka
│   └─ kafka_to_hdfs.py            # consommateur → HDFS
└─ README.md                    # <‑‑ vous êtes ici
```

---

## 🚀 Démarrage de la stack Docker
```powershell
# 1️⃣ Cloner / ouvrir le répertoire du projet
cd C:\Users\Admin\Desktop\SmartCity_Traffic_Pipeline

# 2️⃣ Créer/activer l’environnement virtuel (si ce n’est pas déjà fait)
python -m venv .venv
& .venv\Scripts\Activate.ps1   # PowerShell
# (ou `source .venv/Scripts/activate` sous Git‑Bash)

# 3️⃣ Installer les dépendances Python
pip install -r requirements.txt   # (confluent‑kafka, hdfs, etc.)

# 4️⃣ Lancer les services Docker
docker compose up -d   # démarre Kafka, Zookeeper, HDFS (namenode & datanode), Spark, Airflow, Grafana

# 5️⃣ Vérifier que les conteneurs sont en cours d’exécution
docker ps   # vous devez voir au moins `namenode`, `kafka`, `zookeeper`
```

> **Astuce** : si le service `pgadmin` pose problème, il a été commenté dans `docker‑compose.yml` – il n’est pas requis pour le pipeline.

---

## 📂 Préparer HDFS
Le compte `hdfs` ne possède les droits d’écriture que sous `/user/hdfs`. Créez le répertoire de base :
```powershell
docker exec -it namenode hdfs dfs -mkdir -p /user/hdfs/traffic
```
> Cette commande ne produit aucune sortie lorsqu’elle réussit.

---

## ▶️ Étape 1 – Générer et publier des événements Kafka
Ouvrez **un terminal** et lancez le producteur :
```powershell
python scripts/kafka_producer.py
```
Vous verrez des lignes du type :
```
2026-01-09 01:06:09 INFO Message envoyé au topic traffic-events : 11 - Zone-Industrielle
```
Le producteur tourne en boucle (ou pendant le temps défini par `GEN_SLEEP`). Laissez‑le actif pendant le test.

---

## ▶️ Étape 2 – Consommer et écrire dans HDFS
Dans **un second terminal**, démarrez le consommateur :
```powershell
python scripts/kafka_to_hdfs.py
```
Logs attendus :
```
2026-01-09 01:02:23 INFO Fetching status for '/user/hdfs/traffic/year=2026/month=01/day=09/zone=Quartier-Résidentiel/'
2026-01-09 01:02:23 INFO Creating directories to '/user/hdfs/traffic/year=2026/month=01/day=09/zone=Quartier-Résidentiel/'
2026-01-09 01:02:23 INFO Écrit 50 messages dans /user/hdfs/traffic/.../traffic_20260109010223.jsonl
```
Le script crée les dossiers **year / month / day / zone** et écrit les fichiers au format **JSON‑Lines**.

---

## 🔎 Vérifier le résultat dans HDFS
Après quelques secondes (ou après le batch de 50 msg), listez le répertoire :
```powershell
# Exemple pour le jour 09/01/2026 et la zone "Centre-Ville"
docker exec -it namenode hdfs dfs -ls /user/hdfs/traffic/year=2026/month=01/day=09/zone=Centre-Ville
```
Vous devriez voir un ou plusieurs fichiers `traffic_*.jsonl`.

Pour afficher le contenu :
```powershell
docker exec -it namenode hdfs dfs -cat /user/hdfs/traffic/year=2026/month=01/day=09/zone=Centre-Ville/traffic_*.jsonl
```
Chaque ligne ressemble à :
```json
{"sensor_id":12,"timestamp":"2026-01-09T01:06:10.123456+00:00","zone":"Centre-Ville","road_type":"avenue","vehicle_count":87,"average_speed":42,"occupancy_rate":58}
```

---

## 🛠️ Dépannage fréquent
| Symptom | Cause probable | Solution |
|---------|----------------|----------|
| `Permission denied: user=hdfs, access=WRITE` | Le répertoire de base n’est pas sous `/user/hdfs` ou n’existe pas. | Créez‑le avec `docker exec -it namenode hdfs dfs -mkdir -p /user/hdfs/traffic`.
| Aucun log du consommateur | Le producteur n’est pas en cours d’exécution ou le topic est vide. | Lancez `kafka_producer.py` puis vérifiez le topic avec `docker exec -it kafka kafka-console-consumer …`.
| `docker exec … hdfs dfs -ls` renvoie “No such file or directory” | Le batch n’a pas encore atteint `BATCH_SIZE` ou `BATCH_TIMEOUT`. | Attendez 30 s ou augmentez le débit du producteur.
| `docker exec … kafka-console-consumer` échoue sous PowerShell | Utilisation de `\` pour la continuation de ligne. | Remplacez les `\` par le back‑tick `` ` `` ou écrivez la commande sur une seule ligne.

---

## 📦 Nettoyage (optionnel)
Pour repartir d’un état vierge :
```powershell
# Supprimer les dossiers HDFS créés
docker exec -it namenode hdfs dfs -rm -r -skipTrash /user/hdfs/traffic
# Redémarrer la stack (si vous avez modifié des images)
docker compose down -v && docker compose up -d
```

---

## 🎉 Vous êtes prêts !
Vous avez maintenant :
- Une stack Docker fonctionnelle (Kafka, HDFS, …).
- Un producteur qui génère des événements de trafic réalistes.
- Un consommateur qui les écrit dans HDFS avec partitionnement dynamique.

Les prochaines étapes du projet consisteront à **traiter** ces données avec Spark et à **visualiser** les KPI dans Grafana.

---

*Ce guide a été rédigé par l’assistant *Antigravity* dans le cadre du projet SmartCity Traffic Pipeline.*
