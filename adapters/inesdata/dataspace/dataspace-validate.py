#!/usr/bin/env python3
import subprocess
import sys

DATASPACE = "demo"
NAMESPACE = "demo"

# Credenciales CANÓNICAS para validación QA
# (coherentes con Nivel 7 y verificación manual)
PG_HOST_POD = "common-srvs-postgresql-0"
PG_NAMESPACE = "common-srvs"
PG_USER = "postgres"
PG_DB = "demo_rs"
PG_PASSWORD = "xxxxCHANGEMExxxx"   # se encuentra en runtime/workdir/inesdata-deployment/common/values.yaml

def run(cmd, error, expect=None):
    print(f"▶ {cmd}")
    r = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True
    )

    if r.returncode != 0:
        if r.stderr:
            print(r.stderr.strip())
        print(f"❌ {error}")
        sys.exit(1)

    if expect is not None:
        out = r.stdout.strip()
        if out != expect:
            print(f"❌ {error}")
            print(f"   Resultado esperado: {expect}")
            print(f"   Resultado real: {out}")
            sys.exit(1)

print("\n=== FASE 1 – VALIDACIÓN DATASPACE (POST-DEPLOY) ===\n")

# -------------------------------------------------------------------
# 1. Namespace del dataspace
# -------------------------------------------------------------------
run(
    f"kubectl get ns {NAMESPACE}",
    "Namespace del dataspace no existe"
)

# -------------------------------------------------------------------
# 2. Registration Service operativo
# -------------------------------------------------------------------
run(
    f"kubectl get pods -n {NAMESPACE} | grep registration-service | grep Running",
    "registration-service no está en estado Running"
)

# -------------------------------------------------------------------
# 3. Conectividad PostgreSQL (DB REAL del registration service)
# -------------------------------------------------------------------
run(
    f"""
kubectl exec -n {PG_NAMESPACE} {PG_HOST_POD} -- \
env PGPASSWORD={PG_PASSWORD} \
psql -U {PG_USER} -d {PG_DB} -c "SELECT 1;"
""",
    "DB del dataspace no accesible"
)

# -------------------------------------------------------------------
# 4. Verificación funcional del esquema EDC
#    (debe existir tras Nivel 7)
# -------------------------------------------------------------------
run(
    f"""
kubectl exec -n {PG_NAMESPACE} {PG_HOST_POD} -- \
env PGPASSWORD={PG_PASSWORD} \
psql -t -A \
  -U {PG_USER} \
  -d {PG_DB} \
  -c "SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name   = 'edc_participant'
      );"
""",
    "Esquema EDC no inicializado (tabla edc_participant no encontrada)",
    expect="t"
)

print("\n✔ Dataspace operativo y EDC inicializado (POST-DEPLOY)\n")
