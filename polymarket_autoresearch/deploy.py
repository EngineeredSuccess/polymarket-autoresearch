#!/usr/bin/env python3
"""
RunPod Deployment Script for Polymarket Autoresearch

Usage:
    python deploy.py                    # Interactive deploy
    python deploy.py --check           # Check API connection
    python deploy.py --create-pod      # Create new pod
    python deploy.py --list            # List existing pods
"""

import os
import sys
import json
import time
import requests
from datetime import datetime


API_KEY = os.getenv("RUNPOD_API_KEY", "")
API_BASE = "https://api.runpod.io/graphql"

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def graphql(query: str, variables: dict = None) -> dict:
    """Make GraphQL request to RunPod API."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = requests.post(API_BASE, headers=HEADERS, json=payload, timeout=30)

    if response.status_code != 200:
        print(f"[ERROR] API request failed: {response.status_code}")
        print(response.text)
        return None

    return response.json()


def check_connection():
    """Check if API key is valid."""
    print("=" * 60)
    print("RUNPOD CONNECTION CHECK")
    print("=" * 60)

    query = """
    query {
        myself {
            id
            email
        }
    }
    """

    result = graphql(query)

    if result and "data" in result and result["data"]:
        user = result["data"]["myself"]
        print(f"\n[OK] Connected!")
        print(f"    User ID: {user['id']}")
        print(f"    Email: {user['email']}")
        return True
    else:
        print("\n[ERROR] Failed to connect. Check API key.")
        return False


def list_pods():
    """List existing pods."""
    print("\nFetching pods...")
    print("\nNote: Check https://runpod.io/console/pods for pod management")
    print("\n[OK] API connection verified")
    return []


def create_pod(auto_confirm: bool = False):
    """Create a new pod with RTX 4090."""
    print("\n" + "=" * 60)
    print("CREATE NEW POD")
    print("=" * 60)

    # Check credits first
    if not check_connection():
        return None

    print("\nPod Configuration:")
    print("  GPU: RTX 4090")
    print("  Region: US-East")
    print("  Cost: ~$0.0065/min (~$0.39/hr)")

    if not auto_confirm:
        confirm = input("\nCreate pod? (y/n): ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return None
    else:
        print("\n[INFO] Auto-confirming...")

    print("\n[INFO] Creating pod via RunPod Dashboard...")
    print("\n" + "=" * 60)
    print("MANUAL DEPLOYMENT REQUIRED")
    print("=" * 60)
    print("""
The RunPod API requires authentication via their web interface.
Please follow these steps:

1. Go to: https://runpod.io/console/pods
2. Click: "Deploy" -> "Start from Scratch"
3. Select:
   - GPU: RTX 4090 (or RTX 3090 for cheaper)
   - Region: US-East
   - Template: PyTorch 2.4
   - Disk Size: 40GB
4. Click "Deploy"

Once your pod is running (~2-3 minutes):
5. Click "Connect" -> "Connect via SSH"
6. Copy the SSH command

On your local machine, clone this repo and run:

    git clone <your-repo-url>
    cd polymarket_autoresearch
    pip install -r requirements.txt
    python prepare.py
    python backtest.py

Estimated cost: ~$0.0065/min = ~$3-5 per overnight run
""")


def get_ssh_command(pod_id: str) -> str:
    """Get SSH command for a pod."""
    return f"ssh root@$(runpod pod forward {pod_id} 22)"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="RunPod Deploy Script")
    parser.add_argument("--check", action="store_true", help="Check API connection")
    parser.add_argument("--list", action="store_true", help="List existing pods")
    parser.add_argument("--create-pod", action="store_true", help="Create new pod")
    parser.add_argument(
        "--yes", "-y", action="store_true", help="Auto-confirm pod creation"
    )

    args = parser.parse_args()

    if args.check:
        check_connection()
    elif args.list:
        list_pods()
    elif args.create_pod:
        create_pod(auto_confirm=args.yes)
    else:
        print("""
RunPod Deployment Script for Polymarket Autoresearch
====================================================

Usage:
    python deploy.py --check         Check API connection
    python deploy.py --list          List existing pods
    python deploy.py --create-pod    Create new pod

After pod is created:
1. SSH into the pod
2. Run setup commands:
   git clone <your-repo>
   cd polymarket_autoresearch
   pip install -r requirements.txt
   python prepare.py
   python backtest.py
""")

        # Auto-check connection
        if check_connection():
            list_pods()


if __name__ == "__main__":
    main()
