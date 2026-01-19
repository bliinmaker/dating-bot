#!/usr/bin/env python3
import subprocess
import sys
import os

def run_tests():
    try:
        print("Устанавливаем зависимости для тестов...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        
        print("Запускаем тесты...")
        cmd = [
            sys.executable, "-m", "pytest",
            "tests/",
            "-v",
            "--cov=.",
            "--cov-report=term-missing",
            "--cov-report=html",
            "--cov-exclude=tests/*",
            "--cov-exclude=alembic/*",
            "--cov-exclude=__pycache__/*"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        print("STDOUT:")
        print(result.stdout)
        print("STDERR:")
        print(result.stderr)
        
        if result.returncode == 0:
            print("✅ Все тесты прошли успешно!")
        else:
            print(f"❌ Тесты завершились с ошибкой. Код возврата: {result.returncode}")
        
        return result.returncode
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при выполнении команды: {e}")
        return 1
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return 1

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)