
import subprocess
import sys

def main():
    print("Starting simulation with log capture...")
    
    # Run for 1 day at high speed, capturing all output
    cmd = ["python", "main.py", "--duration-days", "1", "--speed", "5000.0"]
    
    with open("verification_log.txt", "w", encoding='utf-8') as f:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1
        )
        
        for line in process.stdout:
            # sys.stdout.write(line)  <-- Removed to avoid encoding errors
            f.write(line)
            
        process.wait()
        
    print(f"\nLog saved to verification_log.txt")

if __name__ == "__main__":
    main()
