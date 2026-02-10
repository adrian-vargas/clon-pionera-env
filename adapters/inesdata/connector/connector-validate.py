#!/usr/bin/env python3
import subprocess
import sys

CONNECTOR = "conn-oeg-demo"
NAMESPACE = "demo"

PG_HOST_POD = "common-srvs-postgresql-0"
PG_NAMESPACE = "common-srvs"
PG_USER = "postgres"
PG_DB = "demo_rs"
PG_PASSWORD = "xxxxCHANGEMExxxx"  # coherente con entorno QA

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
            print(f"   Esperado: {expect}")
            print(f"   Real: {out}")
            sys.exit(1)

print("\n=== FASE 1 – VALIDACIÓN BÁSICA DEL CONECTOR (POST-DEPLOY) ===\n")

# -------------------------------------------------------------------
# 1. Pod del conector en estado Running
# -------------------------------------------------------------------
run(
    f"kubectl get pods -n {NAMESPACE} | grep {CONNECTOR} | grep Running",
    "Pod del conector no está en estado Running"
)

# -------------------------------------------------------------------
# 2. Verificación de InitContainers (si existen)
# -------------------------------------------------------------------
print("▶ Verificando initContainers (si existen)...")

cmd = f"""
kubectl get pod -n {NAMESPACE} \
$(kubectl get pods -n {NAMESPACE} | grep {CONNECTOR} | awk '{{print $1}}') \
-o jsonpath="{{.status.initContainerStatuses[*].state}}"
"""

r = subprocess.run(cmd, shell=True, capture_output=True, text=True)

# Si no hay initContainers, es OK
if r.stdout.strip() == "":
    print("✓ No se detectan initContainers (OK)")
else:
    # Si existen, verificamos que no haya errores
    if "Error" in r.stdout or "CrashLoopBackOff" in r.stdout:
        print("❌ InitContainer con error detectado")
        print(r.stdout)
        sys.exit(1)
    else:
        print("✓ InitContainers ejecutados correctamente")

# -------------------------------------------------------------------
# 3. Registro EDC del conector (tabla edc_participant)
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
        FROM public.edc_participant
        WHERE participant_id = '{CONNECTOR}'
      );"
""",
    "El conector no está registrado en EDC",
    expect="t"
)

# -------------------------------------------------------------------
# 4. API del conector responde (aunque sea 401/404)
# -------------------------------------------------------------------
print("▶ Verificando que la Management API responde...")
run(
    f"""
kubectl exec -n {NAMESPACE} deployment/{CONNECTOR} -- \
curl -s -o /dev/null -w "%{{http_code}}" \
http://localhost:19193/management
""",
    "La Management API no responde"
)

# -------------------------------------------------------------------
# 5. Verificación de estabilidad del conector (logs críticos)
# -------------------------------------------------------------------
print("▶ Verificando estabilidad del conector vía logs (errores críticos reales)...")

cmd = f"""
kubectl logs deployment/{CONNECTOR} -n {NAMESPACE} --tail=100 | \
grep -E "FATAL|OutOfMemory|NullPointerException|CrashLoopBackOff|BindException|Cannot start"
"""

r = subprocess.run(cmd, shell=True, capture_output=True, text=True)

if r.stdout.strip():
    print("❌ Errores críticos detectados en logs:")
    print(r.stdout)
    sys.exit(1)
else:
    print("✓ Sin errores críticos. 401/403 esperables ignorados (OK)")

print("\n✔ Conector operativo (FASE 1 – Infraestructura y Registro)\n")
print("➡ Listo para FASE 2: autenticación, CRUD y flujos funcionales\n")
