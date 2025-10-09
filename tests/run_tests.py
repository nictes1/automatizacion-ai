#!/usr/bin/env python3
"""
Script de ejecución de tests para CI/CD
Maneja diferentes tipos de tests y reportes
"""

import sys
import subprocess
import argparse
import os
from pathlib import Path


def run_command(cmd: list, description: str) -> bool:
    """Ejecuta comando y retorna True si exitoso"""
    print(f"\n🔄 {description}")
    print(f"   Comando: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ {description} - EXITOSO")
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
        return True
    else:
        print(f"❌ {description} - FALLÓ")
        if result.stderr:
            print(f"   Error: {result.stderr.strip()}")
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
        return False


def run_unit_tests() -> bool:
    """Ejecuta tests unitarios"""
    cmd = [
        "python", "-m", "pytest", "tests/",
        "--cov=services",
        "--cov-report=xml",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-fail-under=85",
        "--junitxml=test-results.xml",
        "-v",
        "--tb=short"
    ]
    return run_command(cmd, "Tests unitarios con coverage")


def run_smoke_tests() -> bool:
    """Ejecuta smoke tests E2E"""
    cmd = [
        "python", "-m", "pytest", "tests/smoke/",
        "--tb=short",
        "-v",
        "--maxfail=3"
    ]
    return run_command(cmd, "Smoke tests E2E")


def run_integration_tests() -> bool:
    """Ejecuta tests de integración"""
    cmd = [
        "python", "-m", "pytest", "tests/",
        "-m", "integration",
        "--tb=short",
        "-v"
    ]
    return run_command(cmd, "Tests de integración")


def run_linting() -> bool:
    """Ejecuta linting y formateo"""
    commands = [
        (["python", "-m", "black", "--check", "--diff", "."], "Black (formateo)"),
        (["python", "-m", "isort", "--check-only", "--diff", "."], "isort (imports)"),
        (["python", "-m", "flake8", "."], "Flake8 (linting)"),
        (["python", "-m", "mypy", "services/", "--ignore-missing-imports"], "MyPy (tipos)"),
        (["python", "-m", "bandit", "-r", "services/", "-f", "json", "-o", "bandit-report.json"], "Bandit (seguridad)")
    ]
    
    all_passed = True
    for cmd, description in commands:
        if not run_command(cmd, description):
            all_passed = False
    
    return all_passed


def run_security_scan() -> bool:
    """Ejecuta escaneo de seguridad"""
    commands = [
        (["python", "-m", "bandit", "-r", "services/", "-ll"], "Bandit security scan"),
        (["python", "-m", "safety", "check", "--json", "--output", "safety-report.json"], "Safety check")
    ]
    
    all_passed = True
    for cmd, description in commands:
        if not run_command(cmd, description):
            all_passed = False
    
    return all_passed


def run_import_tests() -> bool:
    """Verifica que todos los módulos se importen correctamente"""
    modules_to_test = [
        "services.tool_broker",
        "services.state_reducer", 
        "services.policy_engine",
        "services.tool_manifest",
        "services.canonical_slots",
        "services.observability",
        "config.canary_config",
        "api.metrics"
    ]
    
    print("\n🔄 Verificando imports de módulos")
    
    for module in modules_to_test:
        cmd = ["python", "-c", f"import {module}"]
        if not run_command(cmd, f"Import {module}"):
            return False
    
    print("✅ Todos los imports exitosos")
    return True


def run_performance_tests() -> bool:
    """Ejecuta tests de performance básicos"""
    cmd = [
        "python", "-m", "pytest", "tests/",
        "-m", "performance",
        "--tb=short",
        "-v"
    ]
    return run_command(cmd, "Tests de performance")


def generate_reports() -> bool:
    """Genera reportes de tests"""
    print("\n📊 Generando reportes...")
    
    # Verificar que existan los archivos de reporte
    report_files = [
        "test-results.xml",
        "coverage.xml", 
        "htmlcov/index.html",
        "bandit-report.json",
        "safety-report.json"
    ]
    
    all_exist = True
    for file_path in report_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path} - Generado")
        else:
            print(f"⚠️  {file_path} - No encontrado")
            all_exist = False
    
    return all_exist


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description="Ejecutor de tests para PulpoAI")
    parser.add_argument(
        "test_type",
        choices=["all", "unit", "smoke", "integration", "lint", "security", "imports", "performance"],
        help="Tipo de tests a ejecutar"
    )
    parser.add_argument(
        "--no-reports",
        action="store_true",
        help="No generar reportes"
    )
    
    args = parser.parse_args()
    
    print("🚀 PulpoAI Test Runner")
    print("=" * 50)
    
    success = True
    
    if args.test_type == "all":
        # Ejecutar todos los tests en orden
        test_functions = [
            ("imports", run_import_tests),
            ("lint", run_linting),
            ("unit", run_unit_tests),
            ("smoke", run_smoke_tests),
            ("integration", run_integration_tests),
            ("security", run_security_scan),
            ("performance", run_performance_tests)
        ]
        
        for test_name, test_func in test_functions:
            if not test_func():
                print(f"\n❌ {test_name.upper()} tests fallaron")
                success = False
                break
            else:
                print(f"\n✅ {test_name.upper()} tests exitosos")
    
    elif args.test_type == "unit":
        success = run_unit_tests()
    elif args.test_type == "smoke":
        success = run_smoke_tests()
    elif args.test_type == "integration":
        success = run_integration_tests()
    elif args.test_type == "lint":
        success = run_linting()
    elif args.test_type == "security":
        success = run_security_scan()
    elif args.test_type == "imports":
        success = run_import_tests()
    elif args.test_type == "performance":
        success = run_performance_tests()
    
    # Generar reportes si no se especifica --no-reports
    if not args.no_reports and success:
        generate_reports()
    
    # Resultado final
    print("\n" + "=" * 50)
    if success:
        print("🎉 TODOS LOS TESTS EXITOSOS")
        sys.exit(0)
    else:
        print("💥 ALGUNOS TESTS FALLARON")
        sys.exit(1)


if __name__ == "__main__":
    main()