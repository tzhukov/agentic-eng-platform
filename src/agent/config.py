import os

def load_custom_env(file_path=".env"):
    """Parses a custom .env file with [section] headers."""
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found.")
        return

    current_section = None
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                continue
            
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                
                # Map sections to env variables
                if current_section == "model.google" and key == "api_key":
                    os.environ["GOOGLE_API_KEY"] = value
                elif current_section == "model.groq" and key == "api_key":
                    os.environ["GROQ_API_KEY"] = value
                elif current_section == "model.e2b" and (key == "api_key" or key == "E2B_API_KEY"):
                    os.environ["E2B_API_KEY"] = value
                elif current_section == "observability.langfuse":
                    if key == "public_key":
                        os.environ["LANGFUSE_PUBLIC_KEY"] = value
                    elif key == "secret_key":
                        os.environ["LANGFUSE_SECRET_KEY"] = value
                    elif key == "host":
                        os.environ["LANGFUSE_HOST"] = value

if __name__ == "__main__":
    load_custom_env()
    print("Environment variables loaded:")
    print(f"GOOGLE_API_KEY: {'Set' if os.getenv('GOOGLE_API_KEY') else 'Not Set'}")
    print(f"GROQ_API_KEY: {'Set' if os.getenv('GROQ_API_KEY') else 'Not Set'}")
    print(f"E2B_API_KEY: {'Set' if os.getenv('E2B_API_KEY') else 'Not Set'}")
    print(f"LANGFUSE_PUBLIC_KEY: {'Set' if os.getenv('LANGFUSE_PUBLIC_KEY') else 'Not Set'}")
