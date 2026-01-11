#!/usr/bin/env python3
"""
spark_traffic_processing.py

Traitement batch PySpark des données de trafic HDFS.
- Lecture des fichiers JSON Lines depuis HDFS
- Nettoyage et déduplications
- Calcul de KPIs (vitesse moyenne, occupation, congestion)
- Sauvegarde en Parquet partitionné
"""

import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, avg, count, hour, when, lit, to_timestamp, unix_timestamp
)
from pyspark.sql.types import StringType
from pyspark.sql.functions import udf

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SPARK_MASTER = os.getenv("SPARK_MASTER", "spark://spark-master:7077")
HDFS_NAMENODE = os.getenv("HDFS_NAMENODE", "hdfs://namenode:9000")
INPUT_PATH = os.getenv("INPUT_PATH", f"{HDFS_NAMENODE}/user/hdfs/traffic/*/*/*/*/*.jsonl")
OUTPUT_ANALYTICS_PATH = os.getenv("OUTPUT_ANALYTICS_PATH", f"{HDFS_NAMENODE}/data/analytics/traffic")
OUTPUT_PROCESSED_PATH = os.getenv("OUTPUT_PROCESSED_PATH", f"{HDFS_NAMENODE}/data/processed/traffic")

# ---------------------------------------------------------------------------
# Initialisation Spark Session
# ---------------------------------------------------------------------------
def create_spark_session():
    """Crée une SparkSession configurée pour le traitement."""
    spark = SparkSession.builder \
        .appName("SmartCityTrafficAnalysis") \
        .master(SPARK_MASTER) \
        .config("spark.sql.shuffle.partitions", "10") \
        .config("spark.executor.memory", "2g") \
        .config("spark.driver.memory", "1g") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    print(f"✅ Spark Session créée : {SPARK_MASTER}")
    return spark

# ---------------------------------------------------------------------------
# UDF : Niveau de congestion
# ---------------------------------------------------------------------------
def congestion_level(occupancy_rate, average_speed):
    """
    Calcule le niveau de congestion basé sur l'occupation et la vitesse.
    
    Règles :
    - Fluide : occupancy < 40% ET speed > 50 km/h
    - Modéré : 40% <= occupancy < 70% OU 30 < speed <= 50
    - Dense : 70% <= occupancy < 85% OU 20 < speed <= 30
    - Bloqué : occupancy >= 85% OU speed <= 20
    """
    if occupancy_rate is None or average_speed is None:
        return "Inconnu"
    
    if occupancy_rate >= 85 or average_speed <= 20:
        return "Bloqué"
    elif occupancy_rate >= 70 or average_speed <= 30:
        return "Dense"
    elif occupancy_rate >= 40 or average_speed <= 50:
        return "Modéré"
    else:
        return "Fluide"

# Enregistrer l'UDF
congestion_udf = udf(congestion_level, StringType())

# ---------------------------------------------------------------------------
# Lecture et Nettoyage des Données
# ---------------------------------------------------------------------------
def load_and_clean_data(spark):
    """
    Charge les fichiers JSON Lines depuis HDFS et applique le nettoyage.
    
    Returns:
        DataFrame nettoyé et dédupliqué
    """
    print(f"📂 Lecture depuis : {INPUT_PATH}")
    
    # Lecture des fichiers JSON Lines
    df_raw = spark.read.json(INPUT_PATH)
    
    print(f"📊 Lignes brutes lues : {df_raw.count()}")
    
    # Nettoyage : filtrer les valeurs aberrantes
    df_clean = df_raw.filter(
        (col("average_speed") >= 0) &
        (col("occupancy_rate") >= 0) &
        (col("occupancy_rate") <= 100)
    )
    
    print(f"🧹 Après nettoyage : {df_clean.count()} lignes")
    
    # Déduplications sur sensor_id + timestamp
    df_dedup = df_clean.dropDuplicates(["sensor_id", "timestamp"])
    
    print(f"🔄 Après déduplication : {df_dedup.count()} lignes")
    
    # Ajout de la colonne congestion_status via UDF
    df_transformed = df_dedup.withColumn(
        "congestion_status",
        congestion_udf(col("occupancy_rate"), col("average_speed"))
    )
    
    # Conversion du timestamp en format exploitable
    df_transformed = df_transformed.withColumn(
        "timestamp_parsed",
        to_timestamp(col("timestamp"))
    )
    
    # Cache car utilisé pour plusieurs agrégations
    df_transformed.cache()
    print("💾 DataFrame mis en cache")
    
    return df_transformed

# ---------------------------------------------------------------------------
# Agrégations KPIs
# ---------------------------------------------------------------------------
def compute_kpis(df):
    """
    Calcule les KPIs principaux.
    
    Returns:
        Tuple de DataFrames (kpi_road, kpi_zone, kpi_hourly)
    """
    print("📈 Calcul des KPIs...")
    
    # KPI 1 : Vitesse moyenne par road_type
    kpi_road = df.groupBy("road_type") \
        .agg(
            avg("average_speed").alias("avg_speed"),
            count("*").alias("total_events")
        ) \
        .orderBy(col("avg_speed").desc())
    
    print("✅ KPI 1 : Vitesse moyenne par road_type")
    kpi_road.show(5, truncate=False)
    
    # KPI 2 : Taux d'occupation moyen par zone
    kpi_zone = df.groupBy("zone") \
        .agg(
            avg("occupancy_rate").alias("avg_occupancy"),
            avg("average_speed").alias("avg_speed"),
            count("*").alias("total_events")
        ) \
        .orderBy(col("avg_occupancy").desc())
    
    print("✅ KPI 2 : Occupation moyenne par zone")
    kpi_zone.show(5, truncate=False)
    
    # KPI 3 : Nombre total de véhicules par heure
    kpi_hourly = df.withColumn("hour", hour(col("timestamp_parsed"))) \
        .groupBy("hour") \
        .agg(
            count("vehicle_count").alias("total_vehicles_counted"),
            avg("vehicle_count").alias("avg_vehicles_per_sensor")
        ) \
        .orderBy("hour")
    
    print("✅ KPI 3 : Véhicules par heure")
    kpi_hourly.show(24, truncate=False)
    
    # KPI 4 : Répartition des niveaux de congestion
    kpi_congestion = df.groupBy("congestion_status") \
        .agg(count("*").alias("count")) \
        .orderBy(col("count").desc())
    
    print("✅ KPI 4 : Répartition congestion")
    kpi_congestion.show(truncate=False)
    
    return kpi_road, kpi_zone, kpi_hourly, kpi_congestion

# ---------------------------------------------------------------------------
# Sauvegarde des Résultats
# ---------------------------------------------------------------------------
def save_results(df, kpi_road, kpi_zone, kpi_hourly, kpi_congestion):
    """
    Sauvegarde les résultats dans HDFS.
    
    - Analytics en Parquet partitionné par zone
    - Échantillon processed en CSV
    """
    print("💾 Sauvegarde des résultats...")
    
    # 1. Sauvegarder les KPIs en Parquet dans /data/analytics/traffic
    print(f"📦 Écriture Parquet (analytics) : {OUTPUT_ANALYTICS_PATH}")
    
    # KPI par road_type
    kpi_road.write.mode("overwrite").parquet(f"{OUTPUT_ANALYTICS_PATH}/kpi_road_type")
    
    # KPI par zone (partitionné par zone)
    kpi_zone.write.mode("overwrite").partitionBy("zone").parquet(f"{OUTPUT_ANALYTICS_PATH}/kpi_zone")
    
    # KPI par heure
    kpi_hourly.write.mode("overwrite").parquet(f"{OUTPUT_ANALYTICS_PATH}/kpi_hourly")
    
    # Répartition congestion
    kpi_congestion.write.mode("overwrite").parquet(f"{OUTPUT_ANALYTICS_PATH}/kpi_congestion")
    
    print("✅ Analytics sauvegardées en Parquet")
    
    # 2. Sauvegarder un échantillon processed en CSV (pour debugging)
    print(f"📄 Écriture CSV (échantillon) : {OUTPUT_PROCESSED_PATH}")
    
    sample_df = df.limit(1000).select(
        "sensor_id", "timestamp", "zone", "road_type",
        "vehicle_count", "average_speed", "occupancy_rate",
        "congestion_status"
    )
    
    sample_df.write.mode("overwrite").option("header", "true").csv(OUTPUT_PROCESSED_PATH)
    
    print("✅ Échantillon CSV sauvegardé")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    """Point d'entrée principal du job Spark."""
    print("🚀 Démarrage du job Spark : SmartCityTrafficAnalysis")
    
    # 1. Créer la session Spark
    spark = create_spark_session()
    
    try:
        # 2. Charger et nettoyer les données
        df_clean = load_and_clean_data(spark)
        
        # 3. Calculer les KPIs
        kpi_road, kpi_zone, kpi_hourly, kpi_congestion = compute_kpis(df_clean)
        
        # 4. Sauvegarder les résultats
        save_results(df_clean, kpi_road, kpi_zone, kpi_hourly, kpi_congestion)
        
        print("✅ Job Spark terminé avec succès !")
        
    except Exception as e:
        print(f"❌ Erreur lors du traitement : {e}")
        raise
    
    finally:
        # Nettoyer le cache
        spark.catalog.clearCache()
        spark.stop()
        print("🛑 Spark Session fermée")

if __name__ == "__main__":
    main()
