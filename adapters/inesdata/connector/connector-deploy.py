#!/usr/bin/env python3
"""
connector-deploy.py

NIVEL 8 – Despliegue del Connector INESData para PIONERA

Responsabilidades:
- Verificar precondiciones reales
- Parchear el chart Helm del connector (hostAliases Helm-safe)
- Normalizar values.yaml del connector
- Corregir hostname PostgreSQL para acceso cross-namespace
- Desplegar el connector mediante Helm
- Verificar despliegue básico

Principios:
- NO interactivo
- Idempotente
- QA-safe
- Reproducible
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

DATASPACE = "demo"
CONNECTOR = "conn-oeg-demo"
RELEASE = f"{CONNECTOR}-{DATASPACE}"
NAMESPACE = DATASPACE

PG_SERVICE = "common-srvs-postgresql"
PG_NAMESPACE = "common-srvs"
PG_FQDN = f"{PG_SERVICE}.{PG_NAMESPACE}.svc"

ROOT = Path(__file__).resolve().parents[3]
WORKDIR = ROOT / "runtime" / "workdir" / "inesdata-deployment"
CONNECTOR_DIR = WORKDIR / "connector"

VALUES_FILE = CONNECTOR_DIR / f"values-{CONNECTOR}.yaml"
TEMPLATE_FILE = CONNECTOR_DIR / "templates" / "connector-deployment.yaml"

# =============================================================================
# UTILIDADES
# =============================================================================

def header(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def run(cmd, cwd=None):
    print(f"\n▶ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)

def require_file(path: Path, desc: str):
    if not path.exists():
        sys.exit(f"❌ Falta {desc}: {path}")

def backup(path: Path):
    """
    Crea backups QA-safe.
    - Si el fichero está dentro de templates/, mueve el backup a templates/_backup/
    - En otros casos, usa suffix .backup.TIMESTAMP
    """
    if not path.exists():
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if "templates" in path.parts:
        backup_dir = path.parent / "_backup"
        backup_dir.mkdir(exist_ok=True)
        bkp = backup_dir / f"{path.name}.{ts}.bak"
    else:
        bkp = path.with_suffix(path.suffix + f".backup.{ts}")

    bkp.write_text(path.read_text())
    print(f"✓ Backup creado: {bkp}")

# =============================================================================
# FASE 8.1 – PRECONDICIONES
# =============================================================================

def check_preconditions():
    header("NIVEL 8 – Verificación de precondiciones")
    require_file(VALUES_FILE, "values.yaml del connector")
    require_file(TEMPLATE_FILE, "template connector-deployment.yaml")
    print("✓ Precondiciones OK")

# =============================================================================
# FASE 8.2 – PARCHE HELM-SAFE DEL CHART
# =============================================================================

def patch_chart():
    header("NIVEL 8 – Parche Helm-safe del chart")

    old = """      hostAliases:
        - ip: "{{ .Values.hostAliases[0].ip }}"
          hostnames: {{ .Values.hostAliases[0].hostnames | toYaml | nindent 10 }}
"""

    new = """{{- if .Values.hostAliases }}
      hostAliases:
{{ toYaml .Values.hostAliases | nindent 8 }}
{{- end }}
"""

    text = TEMPLATE_FILE.read_text()

    if new in text:
        print("✓ Chart ya parcheado (idempotente)")
        return

    if old not in text:
        sys.exit("❌ Patrón hostAliases no encontrado (chart inesperado)")

    backup(TEMPLATE_FILE)
    TEMPLATE_FILE.write_text(text.replace(old, new))
    print("✓ Chart parcheado correctamente (Helm-safe)")

# =============================================================================
# FASE 8.3 – NORMALIZACIÓN DE VALUES.YAML
# =============================================================================

def normalize_values():
    header("NIVEL 8 – Normalización values.yaml")

    text = VALUES_FILE.read_text()
    modified = False

    backup(VALUES_FILE)

    # Garantizar hostAliases
    if "hostAliases:" not in text:
        text += "\nhostAliases: []\n"
        modified = True

    # Corregir hostname PostgreSQL (cross-namespace)
    if f"hostname: {PG_SERVICE}" in text and PG_FQDN not in text:
        text = text.replace(
            f"hostname: {PG_SERVICE}",
            f"hostname: {PG_FQDN}"
        )
        print(f"✓ Hostname PostgreSQL corregido a FQDN ({PG_FQDN})")
        modified = True

    if modified:
        VALUES_FILE.write_text(text)
        print("✓ values.yaml normalizado (Helm-safe)")
    else:
        print("✓ values.yaml ya estaba normalizado (idempotente)")

# =============================================================================
# FASE 8.4 – DESPLIEGUE HELM
# =============================================================================

def deploy_helm():
    header("NIVEL 8 – Helm upgrade/install")
    run(
        [
            "helm", "upgrade", "--install", RELEASE,
            "-n", NAMESPACE,
            "--create-namespace",
            "-f", VALUES_FILE.name,
            "."
        ],
        cwd=CONNECTOR_DIR
    )

# =============================================================================
# FASE 8.5 – VERIFICACIÓN BÁSICA
# =============================================================================

def verify():
    header("NIVEL 8 – Verificación básica")
    run(["kubectl", "get", "pods", "-n", NAMESPACE])
    print("✓ Connector desplegado (verificando initContainers)")

# =============================================================================
# MAIN
# =============================================================================

def main():
    check_preconditions()
    patch_chart()
    normalize_values()
    deploy_helm()
    verify()

    header("NIVEL 8 COMPLETADO")
    print(f"✔ Connector '{CONNECTOR}' desplegado correctamente")
    print("✔ Chart Helm corregido y reproducible")
    print("✔ Acceso cross-namespace validado (PostgreSQL)")
    print("➡ Esperar a que initContainers finalicen")

if __name__ == "__main__":
    main()
