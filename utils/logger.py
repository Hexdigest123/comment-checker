from typing import Text
import sys

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"


def info(text: Text):
    print(f"{GREEN}[INFO]: {text}{RESET}")


def warning(text: Text):
    print(f"{YELLOW}[WARN]: {text}{RESET}")


def error(text: Text):
    print(f"{RED}[ERROR]: {text}{RESET}")


def fatal(text: Text):
    print(f"{RED}[FATAL]: {text}{RESET}")
    sys.exit(1)
