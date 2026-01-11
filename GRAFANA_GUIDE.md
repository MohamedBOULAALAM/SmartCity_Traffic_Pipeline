# Guide Étape 6 : Visualisation avec Grafana

## 🎯 Objectif

Créer une API FastAPI qui expose les KPIs Spark/HDFS et les afficher dans Grafana.

---

## 📦 Partie 1 : L'API FastAPI (Docker)

### ✅ L'API est déjà dans Docker

L'API tourne automatiquement via le service `api` dans `docker-compose.yml`.

**Vérifier** :
```powershell
docker compose ps
```

Vous devez voir `api-analytics` avec le statut **Up**.

**Logs** :
```powershell
docker logs -f api-analytics
```

**Sortie attendue** :
```
🚀 Démarrage de l'API FastAPI...
📊 HDFS URL: http://namenode:9870
📁 Analytics Base Path: /data/analytics/traffic
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 🔄 Redémarrer l'API (si besoin)

```powershell
docker restart api-analytics
```

### 🧪 Tester l'API

```powershell
# Info API
Invoke-WebRequest -Uri "http://localhost:8000/" -UseBasicParsing | Select-Object -ExpandProperty Content

# Zones
Invoke-WebRequest -Uri "http://localhost:8000/traffic/zones" -UseBasicParsing | Select-Object -ExpandProperty Content

# Congestion
Invoke-WebRequest -Uri "http://localhost:8000/traffic/congestion" -UseBasicParsing | Select-Object -ExpandProperty Content

# Vitesse
Invoke-WebRequest -Uri "http://localhost:8000/traffic/speed" -UseBasicParsing | Select-Object -ExpandProperty Content

# Trends
Invoke-WebRequest -Uri "http://localhost:8000/traffic/trends" -UseBasicParsing | Select-Object -ExpandProperty Content
```

**Résultat attendu (JSON)** :
```json
[
  {"zone":"Centre-Ville","avg_occupancy":52.71,"avg_speed":48.18,"total_events":3062},
  {"zone":"Périphérie","avg_occupancy":52.53,"avg_speed":48.28,"total_events":3116},
  ...
]
```

---

## 🎨 Partie 2 : Configuration Grafana

### 1️⃣ Accéder à Grafana

URL : **http://localhost:3000**

**Identifiants par défaut** :
- Username : `admin`
- Password : `admin`

(Vous pouvez changer le mot de passe au premier login)

---

### 2️⃣ Installer le plugin JSON API

**Via Docker (recommandé)** :

```powershell
# Installer le plugin
docker exec -it grafana grafana-cli plugins install simpod-json-datasource

# Redémarrer Grafana
docker restart grafana
```

**Vérification** :
```powershell
docker logs grafana | Select-String -Pattern "simpod-json-datasource"
```

Vous devez voir : `Registered plugin simpod-json-datasource`

---

### 3️⃣ Configurer la Data Source

1. **Menu** → **Connections** → **Data sources** → **Add data source**
2. Rechercher **"JSON API"**
3. Configurer :
   - **Name** : `Traffic Analytics API`
   - **URL** : `http://host.docker.internal:8000`
   - **Auth** : Laisser vide (pas d'authentification)
4. Cliquer **Save & Test**

**Résultat attendu** : ✅ `Data source is working`

---

### 4️⃣ Créer le premier Dashboard

#### A. Créer un nouveau Dashboard

1. **Menu** → **Dashboards** → **New Dashboard**
2. Cliquer **Add visualization**
3. Sélectionner la data source **Traffic Analytics API**

---

#### B. Panel 1 - Stat : Trafic Global

**Type de visualisation** : **Stat**

**Configuration** :
1. **Query** :
   - URL : `/traffic/zones`
   - Method : `GET`

2. **Transformation** :
   - Ajouter **Extract fields** pour extraire `total_events`
   - Ajouter **Reduce** → Calculation : `Total`

3. **Options** :
   - **Title** : `Trafic Global (Événements)`
   - **Unit** : Standard → Misc → `short`
   - **Color scheme** : From threshold
   - **Thresholds** :
     - Vert : 0 - 5000
     - Jaune : 5000 - 10000
     - Rouge : > 10000  

4. **Sauvegarder** : Nom du dashboard = `SmartCity Traffic Analytics`

---

#### C. Panel 2 - Table : Zones par Occupation

1. **Add panel** → Sélectionner **Table**
2. **Query** : URL = `/traffic/congestion`  
3. **Options** :
   - **Title** : `Top Zones Congestionnées`
   - **Colonnes** : `zone`, `avg_occupancy`, `avg_speed`, `total_events`
   - Trier par `avg_occupancy` décroissant

---

#### D. Panel 3 - Bar Chart : Vitesse par Type de Route

1. **Add panel** → Sélectionner **Bar chart**
2. **Query** : URL = `/traffic/speed`
3. **Transformation** : Extraire `road_type`, `avg_speed`
4. **Options** :
   - **Title** : `Vitesse Moyenne par Type de Route`
   - **Orientation** : Horizontal
   - **Unit** : Velocity → `km/h`

---

#### E. Panel 4 - Time series : Véhicules par Heure

1. **Add panel** → Sélectionner **Time series**
2. **Query** : URL = `/traffic/trends`
3. **Transformation** : Extraire `hour`, `total_vehicles`
4. **Options** :
   - **Title** : `Évolution du Trafic par Heure` 
   - **X-Axis** : `hour`
   - **Y-Axis** : `total_vehicles`
   - **Unit** : Standard → `short`

---

## 🔧 Dépannage

| Problème                                        | Solution                                                                                              |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Grafana : "Data source is working" en rouge** | Vérifier que l'API tourne : `docker logs api-analytics`                                               |
| **API retourne 500**                            | Les fichiers Parquet n'existent pas. Relancer le job Spark.                                           |
| **Plugin JSON API introuvable**                 | Installer manuellement : `docker exec -it grafana grafana-cli plugins install simpod-json-datasource` |
| **Zone affiche "Inconnu"**                      | Bug corrigé : l'API extrait maintenant `zone` depuis le chemin de partition.                          |

---

## 📊 Résultat Final

Vous devez avoir un dashboard Grafana avec :
- ✅ **Stat** : Trafic global
- ✅ **Table** : Top zones congestionnées  
- ✅ **Bar chart** : Vitesse par road_type
- ✅ **Time series** : Véhicules par heure

**Screenshot à capturer** : Dashboard complet avec les 4 panels.

---

## 🎉 Validation Étape 6

**Checklist** :
- [x] API FastAPI démarrée dans Docker (port 8000)
- [x] Endpoints `/traffic/*` retournent du JSON valide
- [x] Plugin JSON API installé dans Grafana
- [x] Data source `Traffic Analytics API` configurée
- [x] Dashboard créé avec 4 panels
- [x] Les données s'affichent correctement

**Si tout est OK** → **Étape 6 RÉUSSIE** ✅

---

**Prochaine étape** : Orchestration Airflow (DAG quotidien pour relancer Spark automatically)
