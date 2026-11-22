#!/usr/bin/env python3
"""
Convert tools.json to CSV format with columns: Server, Tool Name, Description
"""
import csv
import json


def convert_tools_to_csv(json_file, csv_file):
    """Convert tools.json to CSV format"""

    # Read the JSON file
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Open CSV file for writing
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Write header
        writer.writerow(["Server", "Tool Name", "Description"])

        # Process active servers
        if "active" in data:
            for server_name, tools in data["active"].items():
                for tool in tools:
                    writer.writerow(
                        [server_name, tool.get("name", ""), tool.get("description", "")]
                    )

        # Process deactivated servers (if they have tool data)
        # Note: Based on the JSON structure, deactivated is just a list of server names
        # So we'll add them with empty tool info
        if "deactivated" in data and isinstance(data["deactivated"], list):
            for server_name in data["deactivated"]:
                writer.writerow([server_name, "(deactivated)", "This server is deactivated"])

    print(f"✓ Successfully converted {json_file} to {csv_file}")


if __name__ == "__main__":
    convert_tools_to_csv("tools.json", "tools.csv")

# Made with Bob
