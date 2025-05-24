import os
import sys
import subprocess

# Define paths
DIR = os.path.dirname(__file__)
ANTLR_JAR = 'C:\\antlr\\antlr4-4.9.2-complete.jar'  # Update to your ANTLR JAR path
CPL_Dest = os.path.join(DIR, 'CompiledFiles')
SRC = os.path.join(DIR, 'Finance.g4')

def generate_antlr_files():
    """Generate ANTLR parser files from Finance.g4."""
    if not os.path.exists(CPL_Dest):
        os.makedirs(CPL_Dest)
    
    # Run ANTLR to generate parser files
    cmd = [
        'java', '-jar', ANTLR_JAR, '-Dlanguage=Python3',
        '-o', CPL_Dest, SRC
    ]
    try:
        subprocess.run(cmd, check=True)
        print("ANTLR files generated successfully in CompiledFiles/")
    except subprocess.CalledProcessError as e:
        print(f"Error generating ANTLR files: {e}")
        sys.exit(1)

def run_chatbot():
    """Run the chatbot program."""
    from chatbot import run
    run()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run.py [gen|test]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    if command == "gen":
        generate_antlr_files()
    elif command == "test":
        # Ensure ANTLR files are generated before running
        if not os.path.exists(CPL_Dest):
            print("CompiledFiles not found. Run 'python run.py gen' first.")
            sys.exit(1)
        run_chatbot()
    else:
        print("Invalid command. Use 'gen' or 'test'.")
        sys.exit(1)