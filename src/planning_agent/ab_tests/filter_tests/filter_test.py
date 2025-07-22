import subprocess
import shlex
import time
import json
import os

from dotenv import load_dotenv
from typing import Dict, Any, List

from planning_agent.ab_tests.constants import TestOptions 

load_dotenv()
def evaluate_results(approaches: int, answers: List[List[str]], input_path: str, output_path: str): 

    lines = None 
    with open(input_path, "r") as f:
        lines = [line.rstrip("\n") for line in f]
    
    n = len(answers) 
    expected_lines = approaches * (n + 2) # one extra line for the name and the avg time
    if len(lines) < expected_lines:
        raise ValueError("Unexpected number of lines in file.")
    
    idx = 0
    results: List[Dict[str, Any]] = []
    for _ in range(approaches): 
        name = lines[idx].strip()
        idx += 1

        correct = 0 
        for q, true_tokens in enumerate(answers, start = 1): 
            pred_line = lines[idx].strip().lower()
            idx += 1
            if all(tok.lower() in pred_line for tok in true_tokens): 
                correct += 1

        accuracy = correct/n
        try: 
            avg_time = float(lines[idx].strip())
        except: 
            raise ValueError("Unexpected line format. Avg time should be a number")
        idx += 1

        results.append(
            {"name": name, "accuracy": accuracy, "avg_time": avg_time}
        )
    
    ranked = sorted(
        results, 
        key = lambda d: (-d["accuracy"], d["avg_time"]),
    )

    with open(output_path, "a") as f:
        json.dump(ranked, f, indent = 2)
    
    return ranked

if __name__ == "__main__":

    '''
    questions = [ "Show top erroneous calls handled by 'Robot Shop - EP' application since yesterday", 
    "Show performance overview of all hup calls in the past 2 hours group by call name", 
    "What is the average response time of promo HTTP calls handled by Kubernetes cluster demo-us-cluster?",
    "What is the average response time of readiness calls handled by service app of application zone in last 1 day?",
    "Show count of erroneous HTTP calls by call.tag.Errorcode handled by AdService application",
    "Show top erroneous calls handled by AdService service since last 10 minutes",
    "Show performance overview of outbound HTTP calls from kubernetes cluster kub8-names to AC-test application order by calls",
    "What are the slowest API endpoints in my environment and their contributing factors (CPU, memory, dependencies) - use local tool only"
    ]

    answers = [
        ['getCallGroup'], 
        ['getCallGroup'], 
        ['getCallGroup'], 
        ['getCallGroup'], 
        ['getCallGroup'], 
        ['getCallGroup'], 
        ['getCallGroup'], 
        ['getCallGroup', 'getServicesMetrics'], 
    ]
    '''
    questions = ["give me an overview of my watsonx instance", "give me data about credit cards using my watsonx instance", "Compare transaction values to credit limits using my watsonx instance"]
    answers = ["", "", "",]

    TEST_RESULTS_PATH = os.getenv("TEST_RESULTS_PATH")
    EVAL_RESULTS_PATH = os.getenv("EVAL_RESULTS_PATH")

    options = TestOptions.tests_in_commission
    test_dict = TestOptions.test_options

    # Define the command base
    command_base = "uv run src/planning_agent/filter_test_client.py"

    
    for option in options: 
        with open(TEST_RESULTS_PATH, "a") as f:
                f.write(f"{test_dict[option]}\n")
        
        time_for_option = 0

        for question in questions:
            full_command = f'{command_base} {option} {question}'
            try:
                # Use shlex.split to correctly handle spaces and quotes in the command
                # Remove capture_output=True, text=True, stdout, and stderr
                start_time = time.time()
                process = subprocess.run(shlex.split(full_command), check=True)
                end_time = time.time()
                elapsed_time_seconds = end_time - start_time  # Time in seconds (float)
                elapsed_time_ms = elapsed_time_seconds
                time_for_option += elapsed_time_ms
                # The output from uv run and filter_test_client.py will go directly to the console
                # You will not see 'Output:' or 'Error Output:' from this script anymore.
            except subprocess.CalledProcessError as e:
                # This will still catch if uv run itself returns a non-zero exit code
                print(f"Error running command: {e}")
                print("Command:", e.cmd)
                print("Return Code:", e.returncode)
                # You can't print e.stdout or e.stderr here anymore because they were not captured
                # You might need to check the file where filter_test_client.py writes for details
            print("-----------------------------------")

        time_for_option /= len(questions)
        with open(TEST_RESULTS_PATH, "a") as f:
                f.write(f"{time_for_option}\n")
    
    

    evaluate_results(approaches = len(options), answers = answers, input_path = TEST_RESULTS_PATH, output_path = EVAL_RESULTS_PATH)