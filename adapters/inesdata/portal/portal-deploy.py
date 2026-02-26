#!/usr/bin/env python3

"""
NIVEL 9 – Portal Público (FASE DEPLOY)

Responsabilidades:
- Ejecutar Helm upgrade/install
- Aplicar post-renderer automático (elimina hostPort)
- Esperar pods Running
- Detectar CrashLoopBackOff
- Timeout controlado
- Generar evidencias runtime/
- Idempotente

NO:
- Modifica values.yaml
- Introduce lógica funcional
- Modifica templates oficiales
"""

import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

ROOT = Path(__file__).resolve().parents[3]
STEP2_DIR = ROOT / "runtime/workdir/inesdata-deployment/dataspace/step-2"
RUNTIME_DIR = ROOT / "venv"

NAMESPACE = "demo"
RELEASE = "demo-dataspace-s2"

TIMEOUT = 180  # segundos

POST_RENDERER_PATH = RUNTIME_DIR / "helm-post-renderer.sh"

# =============================================================================
# UTILIDADES
# =============================================================================

def header(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def run(cmd, cwd=None, check=True):
    print("\n▶", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check)

def run_output(cmd):
    return subprocess.check_output(cmd, text=True).strip()

def save_evidence(name, content):
    evid_dir = RUNTIME_DIR / "evidences"
    evid_dir.mkdir(exist_ok=True)
    file = evid_dir / f"{name}.txt"
    file.write_text(content)

# =============================================================================
# FASE 1 – CREAR POST-RENDERER DINÁMICO
# =============================================================================

def create_post_renderer():
    header("NIVEL 9 – Generación post-renderer dinámico")

    content = """#!/bin/bash
# Post-renderer automático para entorno single-node con Ingress
# Elimina cualquier definición de hostPort para evitar conflictos
sed '/hostPort:/d'
"""

    POST_RENDERER_PATH.write_text(content)
    POST_RENDERER_PATH.chmod(0o755)

    print(f"✓ Post-renderer generado en {POST_RENDERER_PATH}")

# =============================================================================
# FASE 2 – HELM DEPLOY
# =============================================================================

def helm_deploy():
    header("NIVEL 9 – Helm upgrade/install con post-renderer")

    run([
        "helm", "upgrade", "--install",
        RELEASE,
        "-n", NAMESPACE,
        "-f", "values-demo.yaml",
        "--post-renderer", str(POST_RENDERER_PATH),
        "."
    ], cwd=STEP2_DIR)

# =============================================================================
# FASE 3 – ESPERA CONTROLADA
# =============================================================================

def wait_for_pods():
    header("NIVEL 9 – Espera controlada de pods")

    start = time.time()

    while time.time() - start < TIMEOUT:

        pods = run_output(["kubectl", "get", "pods", "-n", NAMESPACE])
        print(pods)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_evidence(f"portal_pods_snapshot_{timestamp}", pods)

        if "CrashLoopBackOff" in pods or "Error" in pods:
            print("❌ Detectado CrashLoopBackOff o Error")
            sys.exit(1)

        # Validación específica backend + frontend
        if (
            "demo-public-portal-backend" in pods and
            "demo-public-portal-frontend" in pods and
            pods.count("1/1") >= 2
        ):
            print("✓ Portal operativo")
            return

        time.sleep(5)

    print("❌ Timeout esperando pods Running")
    sys.exit(1)

# =============================================================================
# MAIN
# =============================================================================

def main():
    create_post_renderer()
    helm_deploy()
    wait_for_pods()

    header("NIVEL 9 COMPLETADO")
    print("✔ Portal desplegado correctamente")
    print("✔ hostPort eliminado dinámicamente")
    print("✔ Sin CrashLoopBackOff")
    print("✔ Evidencias generadas en runtime/evidences")

if __name__ == "__main__":
    main()
