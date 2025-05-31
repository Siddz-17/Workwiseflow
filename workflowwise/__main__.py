# This file allows running the CLI using 'python -m workflowwise' from the project root.
from .cli import run_cli

if __name__ == "__main__":
    print("Starting WorkflowWise CLI via __main__.py...")
    run_cli()
