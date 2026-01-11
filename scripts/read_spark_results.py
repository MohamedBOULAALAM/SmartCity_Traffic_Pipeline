#!/usr/bin/env python3
"""Lire les résultats Parquet depuis HDFS"""

from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("ReadResults") \
    .master("local[*]") \
    .getOrCreate()

# KPI Congestion
print("=" * 80)
print("📊 KPI CONGESTION")
print("=" * 80)
df_cong = spark.read.parquet("hdfs://namenode:9000/data/analytics/traffic/kpi_congestion")
df_cong.show(truncate=False)

# KPI Hourly
print("\n" + "=" * 80)
print("📊 KPI HOURLY")
print("=" * 80)
df_hourly = spark.read.parquet("hdfs://namenode:9000/data/analytics/traffic/kpi_hourly")
df_hourly.orderBy("hour").show(24, truncate=False)

# KPI Zone
print("\n" + "=" * 80)
print("📊 KPI ZONE")
print("=" * 80)
df_zone = spark.read.parquet("hdfs://namenode:9000/data/analytics/traffic/kpi_zone")
df_zone.show(truncate=False)

spark.stop()
