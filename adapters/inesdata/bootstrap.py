#!/usr/bin/env python3
"""
bootstrap.py

FASE 0 – Bootstrap del entorno INESData para PIONERA

Responsabilidades:
- Resolver correctamente el ROOT del proyecto
- Crear estructura base runtime/
- Preparar workdir/
- Clonar inesdata-deployment si no existe
- Validar herramientas CLI reales (kubectl, helm, git)

Principios:
- NO interactivo
- Idempotente
- Reproducible
- Sin lógica de negocio
"""

import subprocess
import sys
from pathlib import Path

# =============================================================================
# RESOLUCIÓN CANÓNICA DE PATHS
# =============================================================================

# adapters/inesdata/bootstrap.py
ROOT = Path(__file__).resolve().parents[2]

RUNTIME_DIR = ROOT / "runtime"
WORKDIR = RUNTIME_DIR / "workdir"
INESDATA_DIR = WORKDIR / "inesdata-deployment"

INESDATA_REPO = "https://github.com/INESData/inesdata-deployment.git"
INESDATA_BRANCH = "master"

# =============================================================================
# UTILIDADES
# =============================================================================

def header(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def run(cmd, cwd=None):
    print(f"\n▶ Ejecutando: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=cwd)

def require(cmd, args):
    try:
        subprocess.run(
            [cmd] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        print(f"✓ {cmd} disponible")
    except Exception:
        print(f"❌ Comando requerido no disponible o mal configurado: {cmd}")
        sys.exit(1)

# =============================================================================
# FASE 0.1 – PREFLIGHT REAL
# =============================================================================

def preflight():
    header("BOOTSTRAP – Verificación mínima de entorno")

    require("git", ["--version"])
    require("helm", ["version"])
    require("kubectl", ["version", "--client"])

# =============================================================================
# FASE 0.2 – ESTRUCTURA BASE
# =============================================================================

def prepare_directories():
    header("BOOTSTRAP – Preparación de estructura base")

    RUNTIME_DIR.mkdir(exist_ok=True)
    WORKDIR.mkdir(exist_ok=True)

    print(f"✓ runtime/: {RUNTIME_DIR}")
    print(f"✓ workdir/:  {WORKDIR}")

# =============================================================================
# FASE 0.3 – REPOSITORIO INESDATA
# =============================================================================

def ensure_inesdata_repo():
    header("BOOTSTRAP – Preparación de inesdata-deployment")

    if INESDATA_DIR.exists():
        print(f"✓ inesdata-deployment ya existe: {INESDATA_DIR}")
        return

    print("⏬ Clonando inesdata-deployment desde GitHub…")

    run(
        [
            "git",
            "clone",
            "--branch",
            INESDATA_BRANCH,
            INESDATA_REPO,
            str(INESDATA_DIR),
        ]
    )

    print("✓ inesdata-deployment clonado correctamente")

# =============================================================================
# MAIN
# =============================================================================

def main():
    preflight()
    prepare_directories()
    ensure_inesdata_repo()

    header("BOOTSTRAP COMPLETADO")
    print("✔ ROOT correctamente resuelto")
    print("✔ runtime/workdir preparado")
    print("✔ inesdata-deployment disponible")
    print("\n➡ Siguientes pasos:")
    print("  1. python3 adapters/inesdata/normalize/normalize-base.py")
    print("  2. python3 adapters/inesdata/install.py")

if __name__ == "__main__":
    main()
