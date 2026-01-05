#!/usr/bin/env python3
"""
Simple launcher that asks which platform to use
"""
import os
import sys

def main():
    print("=" * 60)
    print("Trading App Launcher")
    print("=" * 60)
    print()
    print("Choose your platform:")
    print("  1. TWS (Trader Workstation) - Port 7497")
    print("  2. IB Gateway - Port 4001")
    print()

    choice = input("Enter 1 or 2: ").strip()

    if choice == "1":
        os.environ['IB_USE_TWS'] = 'true'
        print("\n✓ Using TWS on port 7497")
    elif choice == "2":
        os.environ['IB_USE_TWS'] = 'false'
        print("\n✓ Using IB Gateway on port 4001")
    else:
        print("\n✗ Invalid choice. Defaulting to IB Gateway.")
        os.environ['IB_USE_TWS'] = 'false'

    print("\nStarting app...\n")

    # Import and run
    import app

if __name__ == "__main__":
    main()

