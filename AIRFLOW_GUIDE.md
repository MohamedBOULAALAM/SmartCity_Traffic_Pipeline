# Guide Étape 7 : Orchestration Airflow

## 🎯 Objectif

Automatiser l'exécution du pipeline Big Data de bout en bout avec Apache Airflow.

---

## 📦 DAGs Créés

### 1️⃣ DAG Principal : `traffic_pipeline`

**Fréquence** : `@hourly` (toutes les heures)

| Task                        | Type           | Description                                |
| --------------------------- | -------------- | ------------------------------------------ |
| `check_kafka_health`      | BashOperator   | Vérifie connectivité Kafka via `nc -z` |
| `trigger_data_generation` | PythonOperator | Génère 100 événements de trafic        |
| `spark_processing`        | BashOperator   | Exécute le job Spark (KPIs)               |
| `validate_output`         | PythonOperator | Vérifie les Parquet dans HDFS             |
| `archive_raw_data`        | BashOperator   | Archive/nettoie les données brutes        |

**Flux d'exécution** :

```
check_kafka_health → trigger_data_generation → spark_processing → validate_output → archive_raw_data
```

### 2️⃣ DAG Monitoring : `traffic_pipeline_monitor`

**Fréquence** : `*/15 * * * *` (toutes les 15 minutes)

- Vérifie la santé de Kafka, HDFS, Spark et l'API

---

## 🚀 Accès à l'Interface Airflow

### URL

**http://localhost:8085**

### Créer l'utilisateur admin (première fois)

Si vous ne pouvez pas vous connecter, créez l'utilisateur :

```powershell
docker exec airflow-webserver airflow users create `
    --username admin `
    --firstname Admin `
    --lastname User `
    --role Admin `
    --email admin@example.com `
    --password admin
```

### Identifiants

- **Username** : `admin`
- **Password** : `admin`

---

## 🔧 Commandes Utiles

### Vérifier les DAGs

```powershell
# Lister tous les DAGs
docker exec -it airflow-webserver airflow dags list

# Vérifier un DAG spécifique
docker exec -it airflow-webserver airflow dags show traffic_pipeline
```

### Tester un DAG (sans l'exécuter réellement)

```powershell
docker exec -it airflow-webserver airflow dags test traffic_pipeline 2026-01-11
```

### Activer le DAG

```powershell
docker exec airflow-webserver airflow dags unpause traffic_pipeline
```

### Déclencher manuellement

```powershell
docker exec -it airflow-webserver airflow dags trigger traffic_pipeline
```

### Voir l'état des tâches

```powershell
docker exec -it airflow-webserver airflow tasks list traffic_pipeline
```

### Exécuter une tâche spécifique

```powershell
docker exec -it airflow-webserver airflow tasks run traffic_pipeline check_kafka_health 2026-01-11
```

---

## ⚙️ Modifications du DAG

### Simplification des dépendances Python

Le DAG a été simplifié pour **ne pas nécessiter** l'installation de packages Python supplémentaires (`confluent_kafka`, `hdfs`) dans le conteneur Airflow.

**Changements** :

- `trigger_data_generation` : Simule la génération (le producteur Kafka tourne déjà en continu)
- `validate_output` : Utilise `subprocess` avec `docker exec` au lieu du client HDFS Python

**Avantage** : Le DAG fonctionne immédiatement sans configuration supplémentaire.

---

## 📊 Utilisation de l'Interface Web

### 1️⃣ Activer le DAG

1. Ouvrir **http://localhost:8085**
2. Se connecter (admin/admin)
3. Dans la liste des DAGs, trouver `traffic_pipeline`
4. Cliquer sur le **toggle** à gauche pour activer le DAG (passer de Off à On)

### 2️⃣ Déclencher manuellement

1. Cliquer sur le DAG `traffic_pipeline`
2. Cliquer sur le bouton **▶ Trigger DAG** en haut à droite
3. Confirmer

### 3️⃣ Voir l'exécution

1. Cliquer sur le DAG
2. Onglet **Graph** : visualiser le flux des tâches
3. Onglet **Grid** : voir l'historique des exécutions
4. Cliquer sur une tâche pour voir les logs

### 4️⃣ Consulter les logs

1. Cliquer sur une tâche (carré coloré)
2. Cliquer sur **Log**
3. Les logs s'affichent avec les messages INFO, WARNING, ERROR

---

## ⚙️ Configuration du DAG

### Fichier : `dags/traffic_pipeline_dag.py`

**Paramètres principaux** :

```python
default_args = {
    'owner': 'smartcity-team',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': True,
    'email': ['alertes@smartcity.local'],
}

with DAG(
    dag_id='traffic_pipeline',
    schedule_interval='@hourly',
    start_date=datetime(2026, 1, 7),
    catchup=False,
    ...
)
```

### Modifier la fréquence

| Schedule        | Description                      |
| --------------- | -------------------------------- |
| `@hourly`     | Toutes les heures                |
| `@daily`      | Tous les jours à minuit         |
| `0 */6 * * *` | Toutes les 6 heures              |
| `0 8 * * *`   | Tous les jours à 8h             |
| `None`        | Déclenchement manuel uniquement |

---

## 🛠️ Dépannage

| Problème                      | Solution                                                                     |
| ------------------------------ | ---------------------------------------------------------------------------- |
| **DAG non visible**      | Vérifier les erreurs :`docker exec airflow-webserver airflow dags list`   |
| **Import Error**         | Vérifier la syntaxe Python du fichier DAG                                   |
| **Task échoue**         | Consulter les logs dans l'interface ou via `docker logs airflow-webserver` |
| **Kafka non accessible** | Vérifier que Kafka est running :`docker compose ps kafka`                 |
| **Spark job échoue**    | Vérifier les logs Spark :`docker logs spark-master`                       |

### Voir les erreurs de parsing

```powershell
docker exec -it airflow-webserver airflow dags report
```

### Recharger les DAGs

```powershell
docker exec -it airflow-scheduler airflow dags reserialize
```

---

## 📈 Monitoring

### Métriques disponibles

Dans l'interface Airflow :

- **Nombre d'exécutions** : succès, échecs, en cours
- **Durée moyenne** de chaque tâche
- **Dernière exécution** réussie

### Alertes email

Configuré avec `email_on_failure=True` dans `default_args`.

Pour activer les emails, configurer SMTP dans `airflow.cfg` ou variables d'environnement :

```yaml
# Dans docker-compose.yml (service airflow-webserver)
environment:
  - AIRFLOW__SMTP__SMTP_HOST=smtp.gmail.com
  - AIRFLOW__SMTP__SMTP_PORT=587
  - AIRFLOW__SMTP__SMTP_USER=votre@email.com
  - AIRFLOW__SMTP__SMTP_PASSWORD=votre_password
```

---

## 🎉 Validation Étape 7

### Checklist

- [X] DAG `traffic_pipeline` créé
- [X] DAG `traffic_pipeline_monitor` créé
- [X] 5 tâches définies avec dépendances
- [X] Configuration `@hourly` avec `catchup=False`
- [X] Email on failure configuré
- [X] Documentation des tâches (doc_md)
- [X] DAGs détectés par Airflow

### Commandes de validation

```powershell
# Vérifier que les DAGs sont chargés
docker exec -it airflow-webserver airflow dags list | Select-String "traffic"

# Tester le DAG (simulation)
docker exec -it airflow-webserver airflow dags test traffic_pipeline 2026-01-11
```

### Résultat attendu

Dans l'interface Airflow (http://localhost:8085) :

- ✅ DAG `traffic_pipeline` visible
- ✅ DAG `traffic_pipeline_monitor` visible
- ✅ Toggle pour activer/désactiver
- ✅ Historique des exécutions

---

## 🎯 Pipeline Complet

```
┌─────────────┐
│   Airflow   │ ← Orchestration @hourly
│    (DAG)    │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  1. Check Kafka → 2. Generate Data → 3. Spark Job →     │
│                                                          │
│  4. Validate Output → 5. Archive Raw Data               │
│                                                          │
└──────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    HDFS     │───>│   FastAPI   │───>│   Grafana   │
│  (Parquet)  │    │    (API)    │    │ (Dashboard) │
└─────────────┘    └─────────────┘    └─────────────┘
```

---

**Si tout est OK** → **Étape 7 RÉUSSIE** ✅

**Pipeline SmartCity Traffic Analytics COMPLET !** 🎉
