#!/usr/bin/env python3
"""
dataspace-create.py

NIVEL 4–5 – Creación lógica de un Dataspace INESData para PIONERA

Responsabilidades:
- Verificar precondiciones (INESData + deployer.config)
- Ejecutar deployer.py dataspace create
- Normalizar artefactos DERIVADOS (values.yaml)
- Preparar inputs consistentes para Nivel 6 (Helm)

REGLAS CRÍTICAS (ANTI-REGRESIÓN):
- ❌ NUNCA tocar templates Helm (templates/*.yaml)
- ❌ NUNCA parsear templates con yaml.safe_load
- ✅ SOLO renombrar / mover values.yaml generados
- ✅ Idempotente y QA-safe
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

DATASPACE = "demo"

ROOT = Path(__file__).resolve().parents[3]   # pionera-env
WORKDIR = ROOT / "runtime" / "workdir" / "inesdata-deployment"

DEPLOYER = WORKDIR / "deployer.py"
DEPLOYER_CONFIG = WORKDIR / "deployer.config"

DATASPACE_DIR = WORKDIR / "dataspace"
STEP1_DIR = DATASPACE_DIR / "step-1"
STEP2_DIR = DATASPACE_DIR / "step-2"

RAW_STEP1 = STEP1_DIR / f"values.yaml.{DATASPACE}"
RAW_STEP2 = STEP2_DIR / f"values.yaml.{DATASPACE}"

FINAL_STEP1 = STEP1_DIR / f"values-{DATASPACE}.yaml"
FINAL_STEP2 = STEP2_DIR / f"values-{DATASPACE}.yaml"

# =============================================================================
# UTILIDADES
# =============================================================================

def header(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def run(cmd, cwd=None, check=True):
    print(f"\n▶ Ejecutando: {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check)

def require_file(path: Path, description: str):
    if not path.exists():
        print(f"❌ Falta {description}: {path}")
        sys.exit(1)

def backup(path: Path):
    if not path.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bkp = path.with_suffix(path.suffix + f".backup.{ts}")
    bkp.write_text(path.read_text())
    return bkp

# =============================================================================
# FASE 4 – PRECONDICIONES
# =============================================================================

def check_preconditions():
    header("NIVEL 4 – Verificación de precondiciones")

    require_file(DEPLOYER, "deployer.py")
    require_file(DEPLOYER_CONFIG, "deployer.config")

    print("✓ INESData preparado")
    print("✓ deployer.config presente")

# =============================================================================
# FASE 4 – CREACIÓN LÓGICA DEL DATASPACE
# =============================================================================

def create_dataspace():
    header(f"NIVEL 4 – Creación lógica del dataspace '{DATASPACE}'")

    # Puede fallar si ya existe → permitido
    result = run(
        ["python3", "deployer.py", "dataspace", "create", DATASPACE],
        cwd=WORKDIR,
        check=False
    )

    if result.returncode != 0:
        print("⚠️ Estado parcial detectado (posible ejecución previa)")
        print("➡ Limpieza controlada del dataspace")

        run(
            ["python3", "deployer.py", "dataspace", "delete", DATASPACE],
            cwd=WORKDIR,
            check=False
        )

        print("🔁 Reintentando creación (1/1)")
        run(
            ["python3", "deployer.py", "dataspace", "create", DATASPACE],
            cwd=WORKDIR,
            check=True
        )

    print("✓ Dataspace creado correctamente")

# =============================================================================
# FASE 5 – NORMALIZACIÓN DE ARTEFACTOS (SOLO VALUES)
# =============================================================================

def normalize_values():
    header("NIVEL 5 – Normalización de artefactos values.yaml")

    require_file(RAW_STEP1, f"values.yaml.{DATASPACE} (step-1)")
    require_file(RAW_STEP2, f"values.yaml.{DATASPACE} (step-2)")

    for src, dst in [
        (RAW_STEP1, FINAL_STEP1),
        (RAW_STEP2, FINAL_STEP2),
    ]:
        if dst.exists():
            print(f"✓ {dst.name} ya existe (idempotente)")
            continue

        backup(src)
        src.rename(dst)
        print(f"✓ {src.name} → {dst.name}")

# =============================================================================
# VERIFICACIÓN FINAL
# =============================================================================

def verify_outputs():
    header("VERIFICACIÓN – Artefactos generados")

    require_file(FINAL_STEP1, "values Step-1 normalizado")
    require_file(FINAL_STEP2, "values Step-2 normalizado")

    print("✓ Artefactos del dataspace listos para Helm")
    print("✓ Templates Helm NO modificados")

# =============================================================================
# MAIN
# =============================================================================

def main():
    check_preconditions()
    create_dataspace()
    normalize_values()
    verify_outputs()

    header("DATASPACE CREADO (FASE LÓGICA)")
    print(f"✔ Dataspace '{DATASPACE}' preparado")
    print("➡ Siguiente paso:")
    print("  - Nivel 6: dataspace-deploy.py (Helm + DB authority)")

if __name__ == "__main__":
    main()
