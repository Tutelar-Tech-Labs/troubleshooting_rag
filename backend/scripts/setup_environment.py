import importlib
import subprocess
import sys


REQUIRED_PACKAGES = {
    "selenium": "selenium",
    "bs4": "beautifulsoup4",
    "requests": "requests",
    "sentence_transformers": "sentence-transformers",
    "faiss": "faiss-cpu",
    "torch": "torch",
    "transformers": "transformers",
}


def ensure_package(import_name: str, pip_name: str) -> bool:
    try:
        importlib.import_module(import_name)
        print(f"[OK] Package '{import_name}' is already installed")
        return True
    except ImportError:
        print(f"[INFO] Installing missing package '{pip_name}'...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pip_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            print(f"[OK] Installed '{pip_name}'")
            return True
        else:
            print(f"[ERROR] Failed to install '{pip_name}':")
            print(result.stderr)
            return False


def check_chrome_driver() -> bool:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument("--headless=new")
        driver = webdriver.Chrome(options=options)
        driver.quit()
        print("[OK] ChromeDriver is available and working")
        return True
    except Exception as exc:
        print("[ERROR] ChromeDriver not found or failed to start.")
        print(exc)
        print(
            "Please install a matching ChromeDriver for your Chrome version and ensure it is on PATH."
        )
        return False


def main() -> None:
    environment_ok = True

    for import_name, pip_name in REQUIRED_PACKAGES.items():
        if not ensure_package(import_name, pip_name):
            environment_ok = False

    # Only attempt ChromeDriver check if selenium import succeeded
    try:
        importlib.import_module("selenium")
        if not check_chrome_driver():
            environment_ok = False
    except ImportError:
        # selenium installation already failed above
        environment_ok = False

    if environment_ok:
        print("ENVIRONMENT_STATUS: OK")
        sys.exit(0)
    else:
        print("ENVIRONMENT_STATUS: FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()

