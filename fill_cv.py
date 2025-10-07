import json

def fill_missing_fields(data, prefix=""):
    """
    Recursively traverses a JSON structure and asks the user 
    for missing values (empty strings, empty lists).
    Inputs are prompted in German, but code comments/docstrings are in English.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}{key}"
            if isinstance(value, str) and value.strip() == "":
                user_input = input(f"Bitte geben Sie {full_key} ein: ")
                data[key] = user_input
            elif isinstance(value, list):
                if not value:  # empty list
                    user_input = input(f"{full_key} (durch Komma getrennt, Enter = überspringen): ")
                    if user_input.strip():
                        data[key] = [x.strip() for x in user_input.split(",")]
                else:
                    for i, item in enumerate(value):
                        fill_missing_fields(item, prefix=f"{full_key}[{i}].")
            elif isinstance(value, dict):
                fill_missing_fields(value, prefix=f"{full_key}.")
    return data


if __name__ == "__main__":
    pass

