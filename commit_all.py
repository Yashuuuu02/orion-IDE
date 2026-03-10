import subprocess
import os

files = [
    "pyproject.toml",
    ".env.example",
    "alembic.ini"
]

for root, _, filenames in os.walk("orion"):
    for f in filenames:
        if f.endswith(".py"):
            files.append(os.path.join(root, f).replace("\\", "/"))

for f in files:
    try:
        # Check if file has any changes
        status = subprocess.run(["git", "status", "--porcelain", f], capture_output=True, text=True)
        if status.stdout.strip():
            print(f"Committing {f}...")
            subprocess.run(["git", "add", f], check=True)
            subprocess.run(["git", "commit", "-m", f"Add {os.path.basename(f)}"], check=True)
            subprocess.run(["git", "push"], check=True)
        else:
            print(f"Skipping {f} (no changes)")
    except subprocess.CalledProcessError as e:
        print(f"Error on {f}: {e}")

print("Done")
