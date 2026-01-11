#!/usr/bin/env python3
"""
api_analytics.py

API FastAPI exposant les KPIs Spark/HDFS à Grafana.
- Lecture des fichiers Parquet depuis HDFS
- Cache 5 minutes
- Endpoints compatibles Grafana JSON API
"""

import os
import io
from datetime import datetime, timedelta
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import pyarrow.parquet as pq
from hdfs import InsecureClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HDFS_URL = os.getenv("HDFS_URL", "http://localhost:9870")
HDFS_USER = os.getenv("HDFS_USER", "root")
ANALYTICS_BASE_PATH = "/data/analytics/traffic"

# Cache global (5 minutes)
CACHE_DURATION = timedelta(minutes=5)
cache = {
    "zones": {"data": None, "timestamp": None},
    "congestion": {"data": None, "timestamp": None},
    "speed": {"data": None, "timestamp": None},
    "trends": {"data": None, "timestamp": None},
}

# ---------------------------------------------------------------------------
# Initialisation FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SmartCity Traffic Analytics API",
    description="API exposant les KPIs de trafic urbain calculés par Spark",
    version="1.0.0"
)

# CORS (permettre Grafana de requêter l'API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En prod, restreindre au domaine Grafana
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Client HDFS global
hdfs_client = InsecureClient(HDFS_URL, user=HDFS_USER)

# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------
def read_parquet_from_hdfs(path: str) -> pd.DataFrame:
    """
    Lit un fichier Parquet depuis HDFS et retourne un DataFrame pandas.
    Gère les partitions Spark (ex: zone=Centre-Ville/).
    
    Args:
        path: Chemin HDFS du fichier/dossier Parquet
    
    Returns:
        DataFrame pandas
    """
    try:
        # Vérifier si le chemin existe
        if not hdfs_client.status(path, strict=False):
            raise FileNotFoundError(f"Chemin HDFS introuvable: {path}")
        
        dataframes = []
        
        # Fonction récursive pour lire tous les .parquet
        def read_recursive(current_path, partition_values=None):
            if partition_values is None:
                partition_values = {}
            
            try:
                items = hdfs_client.list(current_path)
            except Exception:
                return
            
            for item in items:
                item_path = f"{current_path}/{item}"
                
                # Ignorer les fichiers _SUCCESS et _committed
                if item.startswith("_"):
                    continue
                
                # Détecter si c'est une partition (ex: zone=Centre-Ville)
                if "=" in item and hdfs_client.status(item_path, strict=False)['type'] == 'DIRECTORY':
                    # Extraire le nom de la partition et sa valeur
                    partition_key, partition_value = item.split("=", 1)
                    new_partition_values = partition_values.copy()
                    new_partition_values[partition_key] = partition_value
                    read_recursive(item_path, new_partition_values)
                    continue
                
                # Si c'est un fichier .parquet, le lire
                if item.endswith('.parquet'):
                    try:
                        # Lire le fichier en mémoire (BytesIO pour être seekable)
                        with hdfs_client.read(item_path) as reader:
                            buffer = io.BytesIO(reader.read())
                        
                        # Parser avec pyarrow
                        table = pq.read_table(buffer)
                        df = table.to_pandas()
                        
                        # Ajouter les colonnes de partition
                        for key, value in partition_values.items():
                            df[key] = value
                        
                        dataframes.append(df)
                    except Exception as e:
                        print(f"⚠️  Erreur lecture {item_path}: {e}")
                
                # Si c'est un dossier (non-partition), explorer récursivement
                elif hdfs_client.status(item_path, strict=False)['type'] == 'DIRECTORY':
                    read_recursive(item_path, partition_values)
        
        # Démarrer la lecture récursive
        read_recursive(path)
        
        if not dataframes:
            raise FileNotFoundError(f"Aucun fichier Parquet trouvé dans {path}")
        
        # Fusionner tous les DataFrames
        if len(dataframes) == 1:
            return dataframes[0]
        else:
            return pd.concat(dataframes, ignore_index=True)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lecture HDFS: {str(e)}")

def is_cache_valid(cache_key: str) -> bool:
    """Vérifie si le cache est encore valide (< 5 min)."""
    if cache[cache_key]["timestamp"] is None:
        return False
    
    elapsed = datetime.now() - cache[cache_key]["timestamp"]
    return elapsed < CACHE_DURATION

def get_cached_or_fetch(cache_key: str, fetch_func):
    """Retourne les données du cache ou les récupère si expiré."""
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]
    
    # Cache expiré, recharger
    data = fetch_func()
    cache[cache_key]["data"] = data
    cache[cache_key]["timestamp"] = datetime.now()
    return data

# ---------------------------------------------------------------------------
# Endpoints racine
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    """Endpoint racine pour vérifier que l'API est en ligne."""
    return {
        "service": "SmartCity Traffic Analytics API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": [
            "/traffic/zones",
            "/traffic/congestion",
            "/traffic/speed",
            "/traffic/trends"
        ]
    }

@app.get("/health")
def health():
    """Health check pour monitoring."""
    try:
        # Tester la connexion HDFS
        hdfs_client.status("/")
        return {"status": "healthy", "hdfs": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "hdfs": str(e)}

# ---------------------------------------------------------------------------
# Endpoints Analytics
# ---------------------------------------------------------------------------
@app.get("/traffic/zones")
def get_traffic_zones():
    """
    Volume de trafic agrégé par zone.
    
    Returns:
        Liste de zones avec avg_occupancy, avg_speed, total_events
    """
    def fetch():
        df = read_parquet_from_hdfs(f"{ANALYTICS_BASE_PATH}/kpi_zone")
        
        # Convertir en format JSON
        result = []
        for _, row in df.iterrows():
            result.append({
                "zone": row.get("zone", "Inconnu"),
                "avg_occupancy": round(float(row.get("avg_occupancy", 0)), 2),
                "avg_speed": round(float(row.get("avg_speed", 0)), 2),
                "total_events": int(row.get("total_events", 0))
            })
        
        return result
    
    return get_cached_or_fetch("zones", fetch)

@app.get("/traffic/congestion")
def get_traffic_congestion():
    """
    Top 5 zones avec le plus haut taux d'occupation.
    
    Returns:
        Liste des zones les plus congestionnées
    """
    def fetch():
        df = read_parquet_from_hdfs(f"{ANALYTICS_BASE_PATH}/kpi_zone")
        
        # Trier par avg_occupancy décroissant
        df_sorted = df.sort_values("avg_occupancy", ascending=False).head(5)
        
        result = []
        for _, row in df_sorted.iterrows():
            result.append({
                "zone": row.get("zone", "Inconnu"),
                "avg_occupancy": round(float(row.get("avg_occupancy", 0)), 2),
                "avg_speed": round(float(row.get("avg_speed", 0)), 2),
                "total_events": int(row.get("total_events", 0))
            })
        
        return result
    
    return get_cached_or_fetch("congestion", fetch)

@app.get("/traffic/speed")
def get_traffic_speed():
    """
    Vitesse moyenne par type de route.
    
    Returns:
        Liste des road_type avec avg_speed
    """
    def fetch():
        df = read_parquet_from_hdfs(f"{ANALYTICS_BASE_PATH}/kpi_road_type")
        
        # Trier par avg_speed décroissant
        df_sorted = df.sort_values("avg_speed", ascending=False)
        
        result = []
        for _, row in df_sorted.iterrows():
            result.append({
                "road_type": row.get("road_type", "Inconnu"),
                "avg_speed": round(float(row.get("avg_speed", 0)), 2),
                "total_events": int(row.get("total_events", 0))
            })
        
        return result
    
    return get_cached_or_fetch("speed", fetch)

@app.get("/traffic/trends")
def get_traffic_trends():
    """
    Évolution du nombre de véhicules par heure.
    
    Returns:
        Liste des heures avec total_vehicles_counted
    """
    def fetch():
        df = read_parquet_from_hdfs(f"{ANALYTICS_BASE_PATH}/kpi_hourly")
        
        # Trier par heure
        df_sorted = df.sort_values("hour")
        
        result = []
        for _, row in df_sorted.iterrows():
            result.append({
                "hour": int(row.get("hour", 0)),
                "total_vehicles": int(row.get("total_vehicles_counted", 0)),
                "avg_vehicles_per_sensor": round(float(row.get("avg_vehicles_per_sensor", 0)), 2)
            })
        
        return result
    
    return get_cached_or_fetch("trends", fetch)

# ---------------------------------------------------------------------------
# Endpoint compatible Grafana JSON API (optionnel)
# ---------------------------------------------------------------------------
@app.post("/search")
def grafana_search():
    """
    Endpoint pour Grafana JSON API : liste des métriques disponibles.
    """
    return [
        "traffic.zones",
        "traffic.congestion",
        "traffic.speed",
        "traffic.trends"
    ]

@app.post("/query")
def grafana_query(payload: Dict[str, Any]):
    """
    Endpoint pour Grafana JSON API : récupérer les données d'une métrique.
    
    Payload exemple :
    {
        "targets": [{"target": "traffic.zones"}],
        "range": {...}
    }
    """
    targets = payload.get("targets", [])
    results = []
    
    for target in targets:
        metric = target.get("target", "")
        
        if metric == "traffic.zones":
            data = get_traffic_zones()
            results.append({
                "target": metric,
                "datapoints": [[row["total_events"], row["zone"]] for row in data]
            })
        elif metric == "traffic.congestion":
            data = get_traffic_congestion()
            results.append({
                "target": metric,
                "datapoints": [[row["avg_occupancy"], row["zone"]] for row in data]
            })
        elif metric == "traffic.speed":
            data = get_traffic_speed()
            results.append({
                "target": metric,
                "datapoints": [[row["avg_speed"], row["road_type"]] for row in data]
            })
        elif metric == "traffic.trends":
            data = get_traffic_trends()
            results.append({
                "target": metric,
                "datapoints": [[row["total_vehicles"], row["hour"]] for row in data]
            })
    
    return results

# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Démarrage de l'API FastAPI...")
    print(f"📊 HDFS URL: {HDFS_URL}")
    print(f"📁 Analytics Base Path: {ANALYTICS_BASE_PATH}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
