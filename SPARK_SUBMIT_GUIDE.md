# Guide d'Exécution : Job Spark sur le Cluster

## 🎯 Objectif

Soumettre le job PySpark `spark_traffic_processing.py` au cluster Spark Master via `spark-submit`.

---

## 📋 Prérequis

1. **Stack Docker en cours** :

   ```powershell
   docker compose ps
   ```

   Vérifiez que `spark-master` et `spark-worker` sont **Up**.
2. **Données HDFS présentes** :

   ```powershell
   docker exec -it namenode hdfs dfs -ls /user/hdfs/traffic/year=2026/month=01/day=11
   ```

   Vous devez voir des fichiers `.jsonl`.

---

## 🚀 Méthode 1 : Soumission depuis l'hôte (Windows)

### 1️⃣ Copier le script dans le conteneur Spark Master

```powershell
docker cp scripts/spark_traffic_processing.py spark-master:/tmp/
```

### 2️⃣ Soumettre le job avec `spark-submit`

```powershell
docker exec -it spark-master /opt/spark/bin/spark-submit `
    --master spark://spark-master:7077 `
    --deploy-mode client `
    --executor-memory 2g `
    --total-executor-cores 2 `
    /tmp/spark_traffic_processing.py
```

**Explications des options** :

- `--master` : URL du cluster Spark Master
- `--deploy-mode client` : le driver tourne dans le conteneur master (pas sur un worker)
- `--executor-memory` : mémoire allouée par executor
- `--total-executor-cores` : nombre total de cœurs utilisés

---

## 🚀 Méthode 2 : Soumission depuis le conteneur Spark Master

### 1️⃣ Entrer dans le conteneur

```powershell
docker exec -it spark-master bash
```

### 2️⃣ Copier le script (si pas déjà fait)

```bash
# Depuis l'hôte Windows (PowerShell)
docker cp scripts/spark_traffic_processing.py spark-master:/opt/spark/work-dir/
```

### 3️⃣ Soumettre le job

```bash
cd /opt/spark/work-dir
/opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --executor-memory 2g \
    --total-executor-cores 2 \
    spark_traffic_processing.py
```

---

## 📊 Vérification des Résultats

###### 1️⃣ Vérifier les fichiers Parquet (analytics)

```powershell
# KPI par road_type
docker exec -it namenode hdfs dfs -ls /data/analytics/traffic/kpi_road_type

# KPI par zone (partitionné)
docker exec -it namenode hdfs dfs -ls /data/analytics/traffic/kpi_zone

# KPI par heure
docker exec -it namenode hdfs dfs -ls /data/analytics/traffic/kpi_hourly

# Répartition congestion
docker exec -it namenode hdfs dfs -ls /data/analytics/traffic/kpi_congestion
```

### 2️⃣ Lire un fichier Parquet (exemple)

```powershell
docker exec -it spark-master /opt/spark/bin/pyspark --master local[*]
```

Puis dans le shell PySpark :

```python
df = spark.read.parquet("hdfs://namenode:9000/data/analytics/traffic/kpi_road_type")
df.show()
```

### 3️⃣ Vérifier l'échantillon CSV

```powershell
docker exec -it namenode hdfs dfs -ls /data/processed/traffic

# PowerShell (lire les 20 premières lignes)
docker exec namenode hdfs dfs -cat /data/processed/traffic/part-00000-*.csv > results.csv
Get-Content results.csv -Head 20
```

---

## 🛠️ Dépannage

| Problème                             | Solution                                                                                |
| ------------------------------------ | --------------------------------------------------------------------------------------- |
| **`Connection refused` au namenode** | Vérifiez que le namenode est**healthy** : `docker compose ps`                           |
| **`No such file or directory` HDFS** | Vérifiez le chemin d'entrée :`docker exec -it namenode hdfs dfs -ls /user/hdfs/traffic` |
| **Job Spark bloqué**                 | Vérifiez les logs du worker :`docker logs spark-worker`                                 |
| **Mémoire insuffisante**             | Réduire `--executor-memory` à `1g` ou augmenter la RAM Docker                           |

---

## 📦 Variables d'Environnement (optionnelles)

Si vous voulez personnaliser les chemins sans modifier le script :

```powershell
docker exec -it spark-master /opt/spark/bin/spark-submit `
    --master spark://spark-master:7077 `
    --deploy-mode client `
    --conf "spark.executorEnv.INPUT_PATH=hdfs://namenode:9000/user/hdfs/traffic/*/*/*/*/*.jsonl" `
    --conf "spark.executorEnv.OUTPUT_ANALYTICS_PATH=hdfs://namenode:9000/data/analytics/traffic" `
    /tmp/spark_traffic_processing.py
```

---

## 🎯 Résultat Attendu

À la fin du job :

```
✅ Spark Session créée : spark://spark-master:7077
📂 Lecture depuis : hdfs://namenode:9000/user/hdfs/traffic/*/*/*/*/*.jsonl
📊 Lignes brutes lues : 1234
🧹 Après nettoyage : 1234 lignes
🔄 Après déduplication : 1230 lignes
💾 DataFrame mis en cache
📈 Calcul des KPIs...
✅ KPI 1 : Vitesse moyenne par road_type
+-------------+------------------+------------+
|road_type    |avg_speed         |total_events|
+-------------+------------------+------------+
|autoroute    |85.3              |120         |
|avenue       |42.1              |450         |
|rue          |28.7              |660         |
+-------------+------------------+------------+
...
💾 Sauvegarde des résultats...
✅ Analytics sauvegardées en Parquet
✅ Échantillon CSV sauvegardé
✅ Job Spark terminé avec succès !
```

---

## 🔗 Liens Utiles

- **Spark Master UI** : http://localhost:8080
- **Spark Worker UI** : http://localhost:8081
- **HDFS NameNode UI** : http://localhost:9870

**Prêt à lancer le job ?** 🚀
